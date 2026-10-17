"""Local browsing categories, never additional search restrictions."""
SLOT_GROUPS = ('不限', '核心内部', '可选内部', '武器挂点', '通用插槽', '其他／未分类')


def groups_for(name):
    import field_options as fo
    low = name.casefold()
    if low == 'fuel tank':
        return {'核心内部', '可选内部'}
    if any(word in low for word in ('power plant', 'power distributor', 'thrusters', 'frame shift drive')) \
            and 'interdictor' not in low and 'wake scanner' not in low:
        return {'核心内部'}
    if low in ('sensors', 'life support', 'lightweight alloy', 'reinforced alloy',
               'military grade composite', 'mirrored surface composite', 'reactive surface composite') \
            or 'ablative' in low and ('alloy' in low or 'composite' in low):
        return {'核心内部'}
    if low in {n.casefold() for n, spec in fo.BUNDLED_MODULE_SPECS.items() if spec['class'] == [0]}:
        return {'通用插槽'}
    if any(word in low for word in ('laser', 'cannon', 'rail gun', 'railgun', 'missile', 'torpedo',
                                    'mine launcher', 'abrasion blaster', 'flak launcher', 'flechette launcher',
                                    'plasma accelerator', 'plasma shock accelerator', 'plasma charger', 'shard cannon', 'frag-cannon',
                                    'enforcer cannon', 'retributor beam', 'mining lance', 'mining volley repeater')):
        return {'武器挂点'}
    if name in fo.BUNDLED_MODULE_SPECS:
        return {'可选内部'}
    return {'其他／未分类'}


def options_for(options, group):
    return list(options) if group == '不限' else [name for name in options if group in groups_for(name)]
