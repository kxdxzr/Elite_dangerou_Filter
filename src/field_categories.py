"""Browsing groups for ordinary conditions; field IDs and semantics stay intact."""
from system_filter_fields import COUNT_FIELDS

GROUPS = ('不限', '基本信息', '位置距离', '经济人口', '势力派系', '站点设施',
          '商品与舰船模组', '天体信息', '航母信息', '殖民状态', '数量统计', '异族战争', '数据时间')


def category(field):
    if field in COUNT_FIELDS:
        return '数量统计'
    if field.endswith('_at'):
        return '数据时间'
    if field.startswith('thargoid_'):
        return '异族战争'
    if 'colonis' in field:
        return '殖民状态'
    if field.startswith('carrier_') or field == 'dssa_carrier':
        return '航母信息'
    if field.startswith('body_') or field in ('bodies', 'landmarks', 'landmark_value',
                                             'estimated_scan_value', 'estimated_mapping_value', 'synthesis_recipes'):
        return '天体信息'
    if 'distance' in field or field in ('region', 'system_name'):
        return '位置距离'
    if 'econom' in field or 'population' in field:
        return '经济人口'
    if any(part in field for part in ('faction', 'power', 'allegiance', 'government')) or field == 'state':
        return '势力派系'
    if field in ('ships', 'modules', 'marketplace', 'export_commodities', 'import_commodities', 'prohibited_commodities'):
        return '商品与舰船模组'
    if field in ('services', 'material_trader', 'technology_broker', 'stations', 'has_market',
                  'has_shipyard', 'has_outfitting', 'has_large_pad', 'large_pads', 'medium_pads', 'small_pads'):
        return '站点设施'
    return '基本信息'


def available_groups(fields):
    used = {category(field) for field in fields}
    return [group for group in GROUPS if group == '不限' or group in used]


def fields_for(fields, group):
    return sorted(field for field in fields if group == '不限' or category(field) == group)
