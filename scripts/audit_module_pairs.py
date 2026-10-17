"""Developer-only audit: collect real class/rating pairs, never their product.

Prints a Python data table for review. Does not change application/user caches.
Run from the repository root: python scripts/audit_module_pairs.py
"""
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import sys
import tarfile
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import field_options as fo
import filter_engine as eng


def main():
    pairs = {name: set() for name in fo.BUNDLED_MODULE_SPECS}
    symbols = {}

    def collect(rows):
        for row in rows:
            for module in row.get('modules', []):
                name = module.get('name')
                if name not in pairs:
                    continue
                cls, rating = module.get('class'), module.get('rating')
                if isinstance(cls, int) and rating in fo.BUNDLED_MODULE_RATINGS:
                    pairs[name].add((cls, rating))
                    if module.get('ed_symbol'):
                        symbols[module['ed_symbol'].casefold()] = name

    def fetch(filters):
        return eng._http_json('https://spansh.co.uk/api/stations/search',
                              dict(filters=filters, size=3, page=0)).get('results', [])

    for station in ('Jameson Memorial', 'I Sola Prospect'):
        collect(fetch({'name': {'value': station}}))
    missing = [name for name, values in pairs.items() if not values]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for rows in pool.map(lambda name: fetch({'modules': [{'name': {'value': [name]}}]}), missing):
            collect(rows)

    # Supplement standard modules from a pinned, developer-time catalogue.
    # This is NOT a runtime price download and no prices are retained.
    revision = '0db9234b5b9ce8c939ea84133d7ce336eea88e27'
    url = f'https://codeload.github.com/EDCD/coriolis-data/tar.gz/{revision}'
    with urllib.request.urlopen(url, timeout=60) as response:
        archive = tarfile.open(fileobj=io.BytesIO(response.read()), mode='r:gz')
    aliases = {'rail_gun': 'Rail Gun', 'cargo_rack': 'Cargo Rack',
               'power_distributor': 'Power Distributor', 'shield_generator': 'Shield Generator',
               'frame_shift_drive': 'Frame Shift Drive', 'surface_scanner': 'Detailed Surface Scanner',
               'fragment_cannon': 'Fragment Cannon', 'seeker_missile_rack': 'Seeker Missile Rack'}
    for member in archive.getmembers():
        if '/modules/' not in member.name or not member.name.endswith('.json'):
            continue
        data = json.load(archive.extractfile(member))
        for modules in data.values():
            if not isinstance(modules, list):
                continue
            for module in modules:
                if not isinstance(module, dict):
                    continue
                name = symbols.get(str(module.get('symbol', '')).casefold())
                if name is None and not module.get('special') and not module.get('name'):
                    name = aliases.get(Path(member.name).stem)
                if name in pairs and isinstance(module.get('class'), int) and module.get('rating') in fo.BUNDLED_MODULE_RATINGS:
                    pairs[name].add((module['class'], module['rating']))
    archive.close()
    print('# Spansh stock + pinned Coriolis specification audit, 2026-10-17')
    print('PAIR_CODES = {')
    for name, values in pairs.items():
        print(f'    {name!r}: {" ".join(str(c) + r for c, r in sorted(values))!r},')
    print('}')
    print('# Missing:', [name for name, values in pairs.items() if not values])


if __name__ == '__main__':
    main()
