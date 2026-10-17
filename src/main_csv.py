"""Shared condition-driven columns for the main result table and CSV."""
import re

import filter_engine as eng
from result_format import format_ly, format_ls, format_population, format_number
from spansh_filter import field_label


def export_table(rows, kind, conditions, language, tr):
    english = language == 'en'

    def text(value):
        if value is None:
            return tr('情况未知')
        if isinstance(value, bool):
            return tr('是' if value else '否')
        if isinstance(value, list):
            return '; '.join(text(item) for item in value)
        if isinstance(value, dict):
            if 'name' in value:
                return text(value['name'])
            return ', '.join(f'{key}: {text(item)}' for key, item in value.items())
        value = tr(str(value))
        if english:
            value = re.sub(r'[\u3400-\u9fff]', lambda m: '\\u%04x' % ord(m[0]), value)
        return value

    columns = [('name', 'Name' if english else '名称', lambda r: r.get('name'))]
    if kind == 'stations':
        columns.append(('system_name', 'System' if english else '星系',
                        lambda r: r.get('system_name') or r.get('name')))
    seen = {'name', 'system_name'}

    def add(key, title, getter):
        if key not in seen:
            seen.add(key)
            columns.append((key, title, getter))

    def add_field(field):
        title = field.replace('_', ' ').capitalize() if english else field_label(kind, field)
        if field == 'distance_to_arrival':
            title = 'Arrival distance ls' if english else '到达距离 ls'

        def value(row):
            raw = eng.field_raw(kind, row, field)
            if raw is None:
                return None
            if field == 'distance_to_arrival':
                return format_ls(raw)
            if field in ('distance', 'distance_to_nearest_populated_system'):
                return format_ly(raw)
            if field.endswith('_count') or field in ('population', 'system_population'):
                return format_population(raw)
            return raw

        add(field, title, value)

    details_index = 0
    sale_index = 0
    for condition in conditions:
        if condition.get('type') == 'distance':
            ref = condition['ref_system']
            add(('distance', ref), f'Distance to {ref} (ly)' if english else f'距 {ref}（ly）',
                lambda r, ref=ref: format_ly(r['_distances'][ref])
                if r.get('_distances', {}).get(ref) is not None else None)
        elif condition.get('type') == 'system_details':
            details_index += 1
            index = details_index
            for group, evidence in (('body_groups', 'planets'), ('ring_groups', 'rings')):
                if condition.get(group):
                    title = (f'Matched {evidence} ({index})' if english else
                             f'匹配{"星球" if evidence == "planets" else "星环"}（{index}）')
                    add((index, evidence), title,
                        lambda r, index=index, evidence=evidence: '; '.join(
                            str(g.get(evidence, '')) for g in r.get('_system_details', {}).get('groups', [])
                            if g.get('condition') == index))
            if condition.get('nearest_min') is not None or condition.get('nearest_max') is not None:
                for key, en, zh in (('name', 'Nearest populated system', '最近有人星系'),
                                    ('population', 'Neighbour population', '邻近星系人口'),
                                    ('distance', 'Nearest populated distance (ly)', '最近有人星系距离（ly）')):
                    def neighbour(row, key=key, index=index):
                        record = next((n for n in row.get('_system_details', {}).get('neighbours', [])
                                       if n.get('condition') == index), {})
                        value = record.get(key)
                        if value is not None and key in ('population', 'distance'):
                            return (format_population if key == 'population' else format_ly)(value)
                        return value
                    add((index, key), f'{en} ({index})' if english else f'{zh}（{index}）', neighbour)
        elif condition.get('field'):
            field = condition['field']
            if field in ('ships', 'modules') and condition.get('op') in ('in', '=', 'contains'):
                sale_index += 1
                index = sale_index
                label = ('Matched ships' if field == 'ships' else 'Matched modules') if english else (
                    '命中舰船' if field == 'ships' else '命中模组')
                attributes = [('name', label)]
                if field == 'modules':
                    attributes += [('class', 'Class' if english else '等级'),
                                   ('rating', 'Rating' if english else '级别')]
                if condition.get('discounted') is True:
                    attributes += [('percent', 'Discount %' if english else '优惠幅度 %'),
                                   ('source', 'Discount source' if english else '折扣来源')]
                for attribute, title in attributes:
                    def sale_value(row, condition=condition, attribute=attribute):
                        values = []
                        for item, info in eng.matching_sale_items(kind, row, condition):
                            value = (info.get(attribute) if attribute in ('percent', 'source') else
                                     item.get(attribute) if isinstance(item, dict) else
                                     item if attribute == 'name' else None)
                            values.append(text(value))
                        return '; '.join(dict.fromkeys(values)) or None
                    add(('sale', index, attribute), f'{title} ({index})' if english else f'{title}（{index}）', sale_value)
            else:
                add_field(field)
            if condition.get('fresh_days') and field in eng.FRESH_TS_KEY:
                add_field(eng.FRESH_TS_KEY[field])

    return [title for _, title, _ in columns], [
        [text(getter(row)) for _, _, getter in columns] for row in rows]
