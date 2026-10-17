"""Parse exported ship builds into Spansh's explicit physical routing parameters.

Module facts: EDCD/coriolis-data, pinned revision below (data copyright Frontier;
Coriolis code is MIT, not its JSON data). Unknown FSDs
are rejected rather than assigned a guessed jump range. No Spansh JS is executed.
"""
import json
import math
import re

import session_store
from runtime_paths import data_file

DATA_REVISION = '0db9234b5b9ce8c939ea84133d7ce336eea88e27'
FSD_URL = f'https://raw.githubusercontent.com/EDCD/coriolis-data/{DATA_REVISION}/modules/standard/frame_shift_drive.json'
MAX_BUILD_BYTES = 4 * 1024 * 1024
# Auxiliary fuel reservoirs, in tonnes (Coriolis exports omit this field).
RESERVOIRS = {
    'Adder': .36, 'Alliance Challenger': .77, 'Alliance Chieftain': .77,
    'Alliance Crusader': .77, 'Anaconda': 1.07, 'Asp Explorer': .63, 'Asp Scout': .47,
    'Beluga Liner': .81, 'Caspian Explorer': 1.14, 'Diamondback Explorer': .49,
    'Diamondback Scout': .49, 'Dolphin': .5, 'Eagle': .34, 'Federal Assault Ship': .72,
    'Federal Corvette': 1.13, 'Federal Dropship': .83, 'Federal Gunship': .82,
    'Fer-de-Lance': .67, 'Hauler': .25, 'Imperial Clipper': .74, 'Imperial Courier': .41,
    'Imperial Cutter': 1.16, 'Imperial Eagle': .37, 'Keelback': .39, 'Krait Mk II': .63,
    'Krait Phantom': .63, 'Lynx Highliner': .75, 'Mamba': .5, 'Mandalay': .5,
    'Orca': .79, 'Panther Clipper Mk II': 1.11, 'Python Mk II': .83, 'Python': .83,
    'Sidewinder': .3, 'Type-10 Defender': .77, 'Type-11 Prospector': .6,
    'Type-6 Transporter': .39, 'Type-7 Transporter': .52, 'Type-8 Transporter': .52,
    'Type-9 Heavy': .77, 'Viper Mk IV': .46, 'Viper': .41, 'Vulture': .57,
}


def numeric(value, label, positive=False):
    if isinstance(value, bool):
        raise ValueError(f'{label}: invalid number')
    try:
        result = float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{label}: invalid number') from None
    if not math.isfinite(result) or result < 0 or positive and result == 0:
        raise ValueError(f'{label}: invalid number')
    return result


def decode_build(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BUILD_BYTES:
        raise ValueError('Ship JSON is missing or too large (maximum 4 MiB).')
    try:
        build = json.loads(text)
    except ValueError:
        raise ValueError('Invalid ship JSON. Export a Coriolis build or EDSY SLEF.') from None
    if isinstance(build, list):
        if len(build) != 1:
            raise ValueError('Import exactly one ship at a time.')
        build = build[0]
    if not isinstance(build, dict):
        raise ValueError('Expected a ship JSON object.')
    if isinstance(build.get('data'), dict) and isinstance(build['data'].get('Modules'), list):
        return build, 'SLEF'
    if isinstance(build.get('components'), dict) and isinstance(build.get('stats'), dict):
        return build, 'Coriolis'
    raise ValueError('Unsupported ship export. Use Coriolis JSON or EDSY SLEF, not a URL.')


def catalog(http):
    path = data_file('route_module_cache.json')
    cached = session_store.load(path)
    if cached.get('revision') == DATA_REVISION and isinstance(cached.get('fsd'), list):
        return cached['fsd']
    data = http(FSD_URL)
    rows = data.get('fsd') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
        raise ValueError('Invalid FSD catalogue; cannot determine ship parameters.')
    session_store.save(path, dict(revision=DATA_REVISION, fsd=rows))
    return rows


def booster(symbol):
    match = re.fullmatch(r'int_guardianfsdbooster_size([1-5])', symbol, re.I)
    if not match:
        raise ValueError(f'Unsupported Guardian FSD booster: {symbol}')
    return {1: 4, 2: 6, 3: 7.75, 4: 9.25, 5: 10.5}[int(match[1])]


def ship_identity(text):
    """Keep player-provided ship names/identifiers intact; label known Journal IDs."""
    build, kind = decode_build(text)
    if kind == 'Coriolis':
        return dict(model=str(build.get('ship') or ''), name=str(build.get('name') or ''), ident='')
    data = build['data']
    model = str(data.get('Ship') or '')
    normalise = lambda value: re.sub(r'[^a-z0-9]', '', value.casefold())
    models = {normalise(name): name for name in RESERVOIRS}
    models.update(asp='Asp Explorer', viper='Viper Mk III', eagle='Eagle Mk II',
                  cobramkiii='Cobra Mk III', cobramkiv='Cobra Mk IV', cobramkv='Cobra Mk V',
                  empiretrader='Imperial Clipper', empirecourier='Imperial Courier',
                  cutter='Imperial Cutter', federationcorvette='Federal Corvette',
                  federationdropship='Federal Dropship', federationdropshipmkii='Federal Assault Ship',
                  federationgunship='Federal Gunship', independanttrader='Keelback',
                  type6='Type-6 Transporter', type7='Type-7 Transporter', type8='Type-8 Transporter',
                  type9='Type-9 Heavy', type9military='Type-10 Defender',
                  diamondback='Diamondback Scout', diamondbackxl='Diamondback Explorer',
                  kraitmkii='Krait Mk II', typex='Alliance Chieftain',
                  typex2='Alliance Crusader', typex3='Alliance Challenger')
    return dict(model=models.get(normalise(model), model), name=str(data.get('ShipName') or ''),
                ident=str(data.get('ShipIdent') or ''))


def jump_attributes(params, cargo=0):
    """Theoretical single-jump ranges: full main + auxiliary tanks, no injection.

    Guardian range is included before the drive's neutron multiplier (normally
    4x, 6x for the supported supercharge-optimised Mk II drive). This does not
    claim a neutron star is available or that the drive is currently charged.
    """
    cargo = numeric(cargo, 'Cargo')
    tank = numeric(params['tank_size'], 'Tank size', True)
    mass = numeric(params['base_mass'], 'Base mass', True) + tank + cargo
    fuel = min(tank, numeric(params['max_fuel_per_jump'], 'Fuel per jump', True))
    optimal = numeric(params['optimal_mass'], 'Optimal mass', True)
    multiplier = numeric(params['fuel_multiplier'], 'Fuel multiplier', True)
    power = numeric(params['fuel_power'], 'Fuel power', True)
    boost = numeric(params['range_boost'], 'Guardian boost')
    neutron = numeric(params['supercharge_multiplier'], 'Neutron multiplier', True)
    try:
        normal = optimal / mass * (fuel / multiplier) ** (1 / power) + boost
        charged = normal * neutron
    except (OverflowError, ZeroDivisionError):
        raise ValueError('Invalid jump range parameters.') from None
    numeric(normal, 'Jump range', True)
    numeric(charged, 'Neutron jump range', True)
    return dict(cargo=cargo, total_mass=mass, fuel_per_jump=fuel, normal_range=normal,
                neutron_range=charged, neutron_multiplier=neutron)


def parse_ship(text, fsds):
    build, kind = decode_build(text)
    boost, symbol = 0, ''
    if kind == 'SLEF':
        data = build['data']
        modules = data['Modules']
        if any(not isinstance(m, dict) for m in modules):
            raise ValueError('Invalid ship module record.')
        drives = [m for m in modules if str(m.get('Slot', '')).casefold() == 'frameshiftdrive']
        if len(drives) != 1:
            raise ValueError('Exactly one Frame Shift Drive is required.')
        drive = drives[0]
        symbol = str(drive.get('Item', '')).casefold()
        match = next((f for f in fsds if str(f.get('symbol', '')).casefold() == symbol), None)
        if match is None:
            raise ValueError(f'Unsupported Frame Shift Drive: {symbol}')
        optimal, maxfuel = match['optmass'], match['maxfuel']
        for mod in drive.get('Engineering', {}).get('Modifiers', []):
            if str(mod.get('Label', '')).casefold() == 'fsdoptimalmass':
                optimal = mod.get('Value')
            elif str(mod.get('Label', '')).casefold() == 'maxfuelperjump':
                maxfuel = mod.get('Value')
        fuel = data.get('FuelCapacity', {})
        tank, reservoir = fuel.get('Main'), fuel.get('Reserve')
        mass = data.get('UnladenMass')
        for module in modules:
            item = str(module.get('Item', ''))
            if item.casefold().startswith('int_guardianfsdbooster'):
                boost = max(boost, booster(item))
    else:
        drive = build['components'].get('standard', {}).get('frameShiftDrive', {})
        symbol = str(drive.get('symbol', '')).casefold()
        def matches(f):
            if symbol:
                return str(f.get('symbol', '')).casefold() == symbol
            return (f.get('class') == drive.get('class') and f.get('rating') == drive.get('rating')
                    and (not drive.get('name') and not f.get('name') or f.get('name') == drive.get('name')))
        match = next((f for f in fsds if matches(f)), None)
        if match is None:
            raise ValueError('Unsupported Coriolis Frame Shift Drive.')
        symbol = str(match['symbol']).casefold()
        optimal, maxfuel = match['optmass'], match['maxfuel']
        modifications = drive.get('modifications', {})
        if 'optmass' in modifications:
            if isinstance(modifications['optmass'], bool):
                raise ValueError('Invalid optimal mass modification.')
            change = float(modifications['optmass'])
            if not math.isfinite(change):
                raise ValueError('Invalid optimal mass modification.')
            optimal *= 1 + change / 10000
        if 'maxfuel' in modifications and modifications['maxfuel']:
            # This is not covered by the website's Coriolis conversion. Do not guess.
            raise ValueError('Export this modified FSD as EDSY SLEF for exact fuel parameters.')
        effect = drive.get('blueprint', {}).get('special', {}).get('edname', '')
        if effect == 'special_fsd_heavy':
            optimal *= 1.04
        elif effect == 'special_fsd_fuelcapacity':
            maxfuel *= 1.1
        elif effect not in ('', 'special_fsd_toughened', 'special_fsd_lightweight', 'special_fsd_cooled'):
            raise ValueError('Unsupported FSD experimental effect. Export EDSY SLEF instead.')
        stats = build['stats']
        tank, mass = stats.get('fuelCapacity'), stats.get('unladenMass')
        reservoir = RESERVOIRS.get(build.get('ship'))
        if reservoir is None:
            raise ValueError('Unknown ship reservoir size. Export EDSY SLEF instead.')
        for module in build['components'].get('internal', []):
            if module and module.get('group') == 'Guardian Frame Shift Drive Booster':
                boost = max(boost, booster(f"int_guardianfsdbooster_size{module.get('class')}"))
    params = dict(base_mass=numeric(mass, 'Unladen mass', True) + numeric(reservoir, 'Reservoir'),
                  tank_size=numeric(tank, 'Tank size', True), internal_tank_size=numeric(reservoir, 'Reservoir'),
                  optimal_mass=numeric(optimal, 'Optimal mass', True), max_fuel_per_jump=numeric(maxfuel, 'Fuel per jump', True),
                  fuel_multiplier=numeric(match.get('fuelmul'), 'Fuel multiplier', True),
                  fuel_power=numeric(match.get('fuelpower'), 'Fuel power', True), range_boost=boost,
                  supercharge_multiplier=6 if symbol.endswith('overchargebooster_mkii') else 4,
                  injection_multiplier=2)
    return params
