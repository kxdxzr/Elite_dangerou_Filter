"""Typed display-cell keys for sortable result tables; never mutate models."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re


UNKNOWN = frozenset(('', '-', '—', '–', 'unknown', 'n/a', 'none', 'null', 'nan',
                     'inf', '+inf', '-inf', 'infinity', '未知', '情况未知', '未记录', '无数据'))
NUMBER = re.compile(
    r'^(?:(?:cr|[$€£¥])\s*)?'
    r'([+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)'
    r'(?:\s*(?:ly|ls|cr|%|t|g|s))?$', re.IGNORECASE)


def cell_key(value):
    """None means unknown (always last); otherwise return a comparable typed key."""
    text = '' if value is None else str(value).strip()
    if text.casefold() in UNKNOWN:
        return None
    number = NUMBER.fullmatch(text)
    if number:
        try:
            parsed = Decimal(number[1].replace(',', ''))
            if parsed.is_finite():
                return 0, parsed
        except InvalidOperation:
            pass
    if re.match(r'^\d{4}-\d{2}-\d{2}(?:$|[T ])', text):
        try:
            date = datetime.fromisoformat(text.replace('Z', '+00:00'))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            return 1, date.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            pass
    # Natural names: HIP 2 before HIP 10, without converting names to scalars.
    parts = tuple((0, Decimal(part)) if part.isdecimal() else (1, part)
                  for part in re.split(r'(\d+)', text.casefold()) if part)
    return 2, parts


def sorted_cells(items, descending=False):
    """Sort (identity, value) pairs stably; retain unknowns at the end both ways."""
    known, unknown = [], []
    for identity, value in items:
        key = cell_key(value)
        if key is None:
            unknown.append(identity)
        else:
            known.append((identity, key))
    known.sort(key=lambda item: item[1], reverse=descending)
    return [identity for identity, _ in known] + unknown
