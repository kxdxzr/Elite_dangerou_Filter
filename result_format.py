"""Presentation formatting only; never round search/filter data in place."""
from decimal import Decimal, InvalidOperation


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def format_ly(value, unknown=''):
    number = _number(value)
    return f'{number:,.2f}' if number is not None else unknown


def format_ls(value, unknown=''):
    """Arrival distances use the same precision as ly, without unit conversion."""
    number = _number(value)
    return f'{number:,.2f}' if number is not None else unknown


def format_population(value, unknown=''):
    number = _number(value)
    if number is None or number < 0 or number != number.to_integral_value():
        return unknown
    return f'{int(number):,}'


def format_number(value, unknown=''):
    """Group numeric result values without changing their fractional precision."""
    number = _number(value)
    if number is None:
        return unknown
    text = format(number, ',f')
    return text.rstrip('0').rstrip('.') if '.' in text else text
