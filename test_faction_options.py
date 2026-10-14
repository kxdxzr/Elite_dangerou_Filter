import unittest
from unittest.mock import patch

import faction_options as names


class FactionOptionsTests(unittest.TestCase):
    def test_short_acronym_does_not_match_arbitrary_single_letters(self):
        self.assertEqual(names.rank_names(['The Code', 'Taco Corp', 'TerraCorp', 'Stock Corporation', 'TOC'], 'T.O.C.'), ['TOC'])
        with patch.object(names, '_fetch', side_effect=[[], ['TOC']]) as fetch:
            self.assertEqual(names.suggest_factions('T.O.C.'), ['TOC'])
            self.assertEqual(fetch.call_args_list[1].args, ('toc',))

    def test_server_query_preserves_real_name_punctuation(self):
        for query in ("People's Party", 'T.O.C.', 'NJ-D5-6 Workers'):
            with self.subTest(query=query), patch.object(names, '_fetch', return_value=[query]) as fetch:
                self.assertEqual(names.suggest_factions(query)[0], query)
                fetch.assert_called_once_with(query.casefold())

    def setUp(self):
        names._known.clear()
        names._queries.clear()

    def test_short_query_no_request(self):
        with patch.object(names, '_fetch') as fetch:
            for query in ('', ' ', 'a', ' - '):
                self.assertEqual(names.suggest_factions(query), [])
            fetch.assert_not_called()

    def test_exact_prefix_words_and_case_preserved(self):
        values = ['Union of Gliese 868 Green Party', 'Gliese 868 Services', 'gliese 868 services', 'Gliese 868']
        self.assertEqual(names.rank_names(values, 'GLIESE-868')[0], 'Gliese 868')
        result = names.rank_names(values, '868 gliese')
        self.assertIn('Gliese 868 Services', result)
        self.assertNotIn('gliese 868 services', result)

    def test_typo_broadens_search_without_replacing_input(self):
        query = 'Izmo Heavy Industries Ltd'
        with patch.object(names, '_fetch', side_effect=[[], ['Izumo Heavy Industries Ltd', 'Unrelated Party']]) as fetch:
            self.assertEqual(names.suggest_factions(query)[0], 'Izumo Heavy Industries Ltd')
            self.assertEqual(fetch.call_args_list[1].args, ('iz',))
        self.assertEqual(query, 'Izmo Heavy Industries Ltd')

    def test_cache_supports_larger_subsequent_limit(self):
        with patch.object(names, '_fetch', return_value=['Gliese 868 Services', 'Gliese 868 Industries']) as fetch:
            self.assertEqual(len(names.suggest_factions('Gliese 868', limit=1)), 1)
            self.assertEqual(len(names.suggest_factions('Gliese 868', limit=20)), 2)
            fetch.assert_called_once()

    def test_network_failure_known_names_or_explicit_failure(self):
        with patch.object(names, '_fetch', side_effect=OSError('network down')):
            with self.assertRaises(OSError):
                names.suggest_factions('Izumo')
            names.remember(['Izumo Heavy Industries Ltd'])
            self.assertEqual(names.suggest_factions('Izumo'), ['Izumo Heavy Industries Ltd'])

    def test_response_schema_and_correct_endpoint(self):
        with patch.object(names.eng, '_http_json', return_value={'values': ['Mother Gaia', {'name': 'Sol Workers'}]}) as get:
            self.assertEqual(names._fetch('Mother Gaia'), ['Mother Gaia', 'Sol Workers'])
            self.assertIn('/minor_factions?q=Mother%20Gaia', get.call_args.args[0])
        with patch.object(names.eng, '_http_json', return_value={'values': None}):
            with self.assertRaises(ValueError):
                names._fetch('Mother')
