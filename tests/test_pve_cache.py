import tempfile
import time
import threading
import io
import gzip
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pve_cache as cache
import pve_tool as pve
from test_pve_tool import candidate, page, DETAILS


class CacheTests(unittest.TestCase):
    def test_power_transport_gzip_and_uncompressed_server_response(self):
        for encoding, body in (('gzip', gzip.compress(b'{"results": []}')), ('', b'{"results": []}')):
            response = io.BytesIO(body)
            response.headers = {'Content-Encoding': encoding}
            with patch.object(pve.eng.urllib.request, 'urlopen', return_value=response) as get:
                self.assertEqual(pve.eng._http_json('https://example.test/api', {}, compressed=True), {'results': []})
                self.assertEqual(get.call_args.args[0].get_header('Accept-encoding'), 'gzip')

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(cache, 'data_file', side_effect=lambda name: Path(self.folder.name) / name)
        self.path_patch.start()
        cache.clear_memory()

    def tearDown(self):
        cache.clear_memory()
        self.path_patch.stop()
        self.folder.cleanup()

    def test_memory_disk_refresh_expiry_and_future_stamp(self):
        loader = Mock(return_value={'public': 'data'})
        with patch.object(cache.time, 'time', return_value=1000):
            self.assertFalse(cache.cached('test', loader, 60)[1]['hit'])
            self.assertTrue(cache.cached('test', loader, 60)[1]['hit'])
            cache.clear_memory()
            self.assertTrue(cache.cached('test', loader, 60)[1]['hit'])
            self.assertFalse(cache.cached('test', loader, 60, force=True)[1]['hit'])
        with patch.object(cache.time, 'time', return_value=1060):
            self.assertFalse(cache.cached('test', loader, 60)[1]['hit'])
        with patch.object(cache.time, 'time', return_value=999):
            self.assertFalse(cache.cached('test', loader, 60)[1]['hit'])
        self.assertEqual(loader.call_count, 4)

    def test_failed_refresh_never_returns_stale_or_persists_failure(self):
        loader = Mock(return_value={'ok': True})
        cache.cached('test', loader, 60)
        with self.assertRaises(OSError):
            cache.cached('test', Mock(side_effect=OSError('offline')), 60, force=True)
        # The previously successful entry remains intact, not an exception.
        self.assertEqual(cache.cached('test', loader, 60)[0], {'ok': True})

    def test_corrupt_timestamp_and_write_failure_do_not_break_success(self):
        with patch.object(cache.session_store, 'load', return_value=dict(version=1, fetched_at='bad', value={})), \
                patch.object(cache.session_store, 'save', side_effect=OSError('read only')):
            value, meta = cache.cached('test', lambda: {'ok': True}, 60)
        self.assertEqual(value, {'ok': True})
        self.assertFalse(meta['hit'])

    def test_controller_pagination_exact_match_and_cache(self):
        first = [dict(name=f'System {i}', controlling_minor_faction='Skyline Monopoly') for i in range(500)]
        last = [dict(name='Last', controlling_minor_faction='Skyline Monopoly'),
                dict(name='Not exact', controlling_minor_faction='Other')]
        with patch.object(pve.eng, '_http_json', side_effect=[{'results': first, 'count': 1}, {'results': last}]) as http:
            result = pve.controller_systems('Skyline Monopoly')
            self.assertEqual(len(result), 501)
            self.assertNotIn('not exact', result)
            self.assertEqual(pve.controller_systems('Skyline Monopoly'), result)
            self.assertEqual([call.args[1]['page'] for call in http.call_args_list], [0, 1])

    def test_repeated_controller_pages_fail_and_are_not_cached(self):
        rows = [dict(name=f'System {i}', controlling_minor_faction='Faction') for i in range(500)]
        with patch.object(pve.eng, '_http_json', side_effect=[{'results': rows}, {'results': rows}]):
            with self.assertRaisesRegex(ValueError, 'repeated'):
                pve.controller_systems('Faction')
        with patch.object(pve.eng, '_http_json', return_value={'results': []}) as http, \
                patch.object(pve, '_canonical_controller_name', return_value=None):
            self.assertEqual(pve.controller_systems('Faction'), {})
            http.assert_called_once()

    def test_controller_casing_fallback_only_accepts_exact_full_name(self):
        import faction_options
        with patch.object(faction_options, '_fetch', return_value=['Skyline Other', 'Skyline Monopoly']):
            self.assertEqual(pve._canonical_controller_name('skyline monopoly'), 'Skyline Monopoly')
            self.assertIsNone(pve._canonical_controller_name('skyline'))
            with patch.object(pve.eng, '_http_json', side_effect=[{'results': []}, {'results': [
                    dict(name='System', controlling_minor_faction='Skyline Monopoly')]}]) as http:
                self.assertIn('system', pve.controller_systems('skyline monopoly', refresh=True))
                self.assertEqual(http.call_args_list[1].args[1]['filters']['controlling_minor_faction']['value'],
                                 ['Skyline Monopoly'])

    def test_power_pages_ignore_capped_count_use_control_and_share_cache(self):
        first = [dict(name=f'System {i}', controlling_power='Yuri Grom', power=['Other']) for i in range(500)]
        last = [dict(name='Last', controlling_power='Yuri Grom'),
                dict(name='Associated only', controlling_power='Other', power=['Yuri Grom'])]
        with patch.object(pve.eng, '_http_json', side_effect=[{'count': 1, 'results': first}, {'results': last}]) as http:
            result = pve.power_systems('yuri grom', workers=1)
            self.assertEqual(len(result), 501)
            self.assertNotIn('associated only', result)
            self.assertEqual(pve.power_systems('Yuri Grom', workers=1), result)
            self.assertEqual(http.call_count, 2)
            self.assertEqual(http.call_args.args[1]['filters'], {'controlling_power': {'value': ['Yuri Grom']}})
        cache.clear_memory()
        with patch.object(pve.eng, '_http_json', side_effect=AssertionError('must use disk cache')):
            self.assertEqual(pve.power_systems('Yuri Grom', workers=1), result)

    def test_power_invalid_response_failure_is_not_cached(self):
        for response in ({}, {'results': [dict(name='Unknown', power=['Yuri Grom'])]}):
            with patch.object(pve.eng, '_http_json', return_value=response), self.assertRaises(ValueError):
                pve.power_systems('Yuri Grom', workers=1)
        with patch.object(pve.eng, '_http_json', return_value={'results': []}) as http:
            self.assertEqual(pve.power_systems('Yuri Grom', workers=1), {})
            http.assert_called_once()

    def test_power_repeated_pages_and_cancellation_are_not_complete(self):
        rows = [dict(name=f'System {i}', controlling_power='Yuri Grom') for i in range(500)]
        with patch.object(pve.eng, '_http_json', side_effect=[{'results': rows}, {'results': rows}]):
            with self.assertRaisesRegex(ValueError, 'repeated'):
                pve.power_systems('Yuri Grom', workers=1)
        stop = threading.Event()
        def response(*args, **kw):
            stop.set()
            return {'results': rows}
        with patch.object(pve.eng, '_http_json', side_effect=response) as http:
            with self.assertRaises(pve._Cancelled):
                pve.power_systems('Yuri Grom', stop=stop, workers=1)
            http.assert_called_once()

    def test_power_force_refresh_requests_new_control_records(self):
        with patch.object(pve.eng, '_http_json', return_value={'results': []}) as http:
            pve.power_systems('Yuri Grom', workers=1)
            pve.power_systems('Yuri Grom', workers=1)
            pve.power_systems('Yuri Grom', refresh=True, workers=1)
            self.assertEqual(http.call_count, 2)

    def test_power_pages_are_bounded_parallel_and_consumed_in_page_order(self):
        lock = threading.Lock()
        active = peak = 0
        pages = []
        def response(url, payload, **kw):
            nonlocal active, peak
            page = payload['page']
            with lock:
                pages.append(page)
                active += 1
                peak = max(peak, active)
            time.sleep(0.04 if page == 0 else 0.01)
            with lock:
                active -= 1
            count = 500 if page == 0 else 2 if page == 1 else 0
            return {'count': 1, 'results': [dict(name=f'{page}-{n}', controlling_power='Yuri Grom') for n in range(count)]}
        with patch.object(pve.eng, '_http_json', side_effect=response):
            result = pve.power_systems('Yuri Grom')
        self.assertEqual(len(result), 502)
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 4)
        self.assertEqual(sorted(pages), [0, 1, 2, 3])

    def test_bounded_concurrent_details_and_cancellation(self):
        lock, stop = threading.Lock(), threading.Event()
        active = peak = calls = 0
        def load(name):
            nonlocal active, peak, calls
            with lock:
                active += 1
                calls += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return DETAILS['Alpha']
        data = page(*(candidate(f'Source {n}') for n in range(12)))
        info, rows = pve.search(pve.Criteria(min_factions=3), page=data, details_loader=load, workers=4)
        self.assertTrue(info['complete'])
        self.assertEqual(len(rows), 12)
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 4)
        calls = 0
        def cancel_load(name):
            stop.set()
            return load(name)
        info, rows = pve.search(pve.Criteria(min_factions=3), page=data, details_loader=cancel_load, workers=4, stop=stop)
        self.assertFalse(info['complete'])
        self.assertEqual(rows, [])
        self.assertLessEqual(calls, 4)

    def test_controller_cancel_between_pages_issues_no_more_requests(self):
        stop = threading.Event()
        rows = [dict(name=f'System {i}', controlling_minor_faction='Faction') for i in range(500)]
        def response(*args, **kw):
            stop.set()
            return {'results': rows}
        with patch.object(pve.eng, '_http_json', side_effect=response) as http:
            with self.assertRaises(pve._Cancelled):
                pve.controller_systems('Faction', stop=stop)
            http.assert_called_once()


if __name__ == '__main__':
    unittest.main()
