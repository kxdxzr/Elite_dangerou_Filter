"""Conservative public station/Power discount rules; no price downloads.

Sources checked 2026-10-17:
https://elite-dangerous.fandom.com/wiki/Discounts
https://elite-dangerous.fandom.com/wiki/Li_Yong-Rui
Personal rank/pledge bonuses and expired CG discounts are intentionally excluded.
"""
import re


def key(value):
    return re.sub(r'[^a-z0-9]', '', str(value).casefold())


IMPERIAL_SHIPS = {key(n) for n in ('Imperial Eagle', 'Imperial Courier', 'Imperial Clipper', 'Imperial Cutter')}
LAKON_SHIPS = {key(n) for n in ('Asp Explorer', 'Asp Scout', 'Diamondback Explorer', 'Diamondback Scout',
    'Type-6 Transporter', 'Type-7 Transporter', 'Type-8 Transporter', 'Type-9 Heavy', 'Type-10 Defender',
    'Type-11 Prospector', 'Keelback', 'Alliance Chieftain', 'Alliance Challenger', 'Alliance Crusader')}
ATTILIUS_SHIPS = {key(n) for n in ('Sidewinder', 'Sidewinder MkI', 'Eagle', 'Eagle MkII', 'Viper MkIII',
    'Cobra MkIII', 'Diamondback Scout', 'Diamondback Explorer', 'Vulture', 'Fer-de-Lance')}
ATTILIUS_MODULES = {key(n) for n in ('Pulse Laser', 'Burst Laser', 'Beam Laser', 'Cannon', 'Multi-Cannon',
    'Rail Gun', 'Railgun', 'Chaff Launcher', 'Heat Sink Launcher', 'Heatsink Launcher')}
CONTROLLED_STATES = {'exploited', 'fortified', 'stronghold'}


def discount_info(row, item, field):
    """Return the strongest known applicable rule, never sum overlapping rules.

    No rule match means unknown, not proof of full price. Missing item details
    cannot qualify for product-specific rules. Fleet carriers are not retailers.
    """
    unknown = dict(discounted=None, percent=None, source='')
    if 'carrier' in str(row.get('type', '')).casefold() or not isinstance(item, dict):
        return unknown
    name = key(item.get('name', ''))
    if not name:
        return unknown
    system, station = key(row.get('system_name', '')), key(row.get('name', ''))
    power = key(row.get('system_controlling_power', ''))
    state = key(row.get('system_power_state', ''))
    rules = []

    def add(percent, source):
        rules.append(dict(discounted=True, percent=percent, source=source))

    if (system, station) == (key('Shinrarta Dezhra'), key('Jameson Memorial')):
        add(10, 'Jameson Memorial')
    if power == key('Li Yong-Rui') and state in ('fortified', 'stronghold'):
        add(15, 'Li Yong-Rui')
    if field == 'ships':
        if power == key('Denton Patreus') and state in CONTROLLED_STATES and name in IMPERIAL_SHIPS:
            add(10, 'Denton Patreus')
        if system == key('Alioth') and name in LAKON_SHIPS:
            add(5, 'Alioth / Lakon Spaceways')
        if (system, station) == (key('Alioth'), key('Irkutsk')) and name in {key('Asp Explorer'), key('Orca')}:
            add(20, 'Irkutsk')
        if (system, station) == (key('Wolf 406'), key('Hamilton Gateway')) and name == key('Diamondback Explorer'):
            add(20, 'Hamilton Gateway')
        if (system, station) == (key('Summerland'), key("Henry O'Hare's Hangar")) and name in IMPERIAL_SHIPS:
            add(10, "Henry O'Hare's Hangar")
        if (system, station) == (key('Sol'), key('Daedalus')):
            if name in {key('Federal Dropship'), key('Vulture')}:
                add(10, 'Daedalus')
            if name in {key('Eagle'), key('Eagle MkII')}:
                add(20, 'Daedalus')
        if (system, station) == (key('Beta Hydri'), key('Edmondson High')) and name in {key('Eagle'), key('Eagle MkII')}:
            add(10, 'Edmondson High')
        if (system, station) == (key('CD-43 11917'), key('Attilius Orbital')) and name in ATTILIUS_SHIPS:
            add(20, 'Attilius Orbital')
    elif field == 'modules':
        if power == key('Edmund Mahon') and state in CONTROLLED_STATES and name in {key('Cargo Rack'), key('Hull Reinforcement Package')}:
            add(20, 'Edmund Mahon')
        # Weapons only; mining/utility hardpoints are not combat weapons.
        if (power == key('Jerome Archer') and state in CONTROLLED_STATES
                and item.get('category') == 'hardpoint' and item.get('weapon_mode')
                and name not in {key('Mining Laser'), key('Abrasion Blaster'), key('Seismic Charge Launcher'),
                                 key('Sub-Surface Displacement Missile'), key('Sub-Surface Extraction Missile')}):
            add(20 if state == 'stronghold' else 10, 'Jerome Archer')
        if (system, station) == (key('CD-43 11917'), key('Attilius Orbital')) and name in ATTILIUS_MODULES:
            try:
                size = int(item.get('class'))
            except (ValueError, TypeError):
                size = None
            mode = str(item.get('weapon_mode') or '').casefold()
            if size is not None and size < 3 and (name in {key('Chaff Launcher'), key('Heat Sink Launcher'),
                    key('Heatsink Launcher')} or mode in ('fixed', 'gimbal', 'gimballed')):
                add(30, 'Attilius Orbital')
    return max(rules, key=lambda rule: rule['percent']) if rules else unknown
