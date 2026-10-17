"""Ship-engineer destinations, not Odyssey suit/handheld-weapon engineers.

Source: https://elite-dangerous.fandom.com/wiki/Engineers#Ship_Engineers
Checked 2026-10-17. Includes the Bubble, Colonia and Witch Head engineers.
Names/systems are canonical game names and stay unchanged across UI languages.
"""

SHIP_ENGINEERS = (
    ('Bill Turner', 'Alioth'),
    ('Broo Tarquin', 'Muang'),
    ('Chloe Sedesi', 'Shenve'),
    ('Colonel Bris Dekker', 'Sol'),
    ('Didi Vatermann', 'Leesti'),
    ('Elvira Martuuk', 'Khun'),
    ('Etienne Dorn', 'Los'),
    ('Felicity Farseer', 'Deciat'),
    ('Hera Tani', 'Kuwemaki'),
    ('Juri Ishmaak', 'Giryak'),
    ('Lei Cheung', 'Laksak'),
    ('Liz Ryder', 'Eurybia'),
    ('Lori Jameson', 'Shinrarta Dezhra'),
    ('Marco Qwent', 'Sirius'),
    ('Marsha Hicks', 'Tir'),
    ('Mel Brandon', 'Luchtaine'),
    ('Petra Olmanova', 'Asura'),
    ('Professor Palin', 'Arque'),
    ('Ram Tah', 'Meene'),
    ('Selene Jean', 'Kuk'),
    ('The Dweller', 'Wyrd'),
    ('The Sarge', 'Beta-3 Tucani'),
    ('Tiana Fortune', 'Achenar'),
    ('Tod "The Blaster" McQuinn', 'Wolf 397'),
    ('Zacariah Nemo', 'Yoru'),
)

CHOICES = tuple(f'{name} — {system}' for name, system in SHIP_ENGINEERS)


def destination_choice(value):
    """Restore old system-only sessions, but never accept unrelated systems."""
    key = value.strip().casefold()
    for (name, system), choice in zip(SHIP_ENGINEERS, CHOICES):
        if key in (name.casefold(), system.casefold(), choice.casefold()):
            return choice
    return ''


def destination_system(value):
    choice = destination_choice(value)
    if not choice:
        raise ValueError('请从列表选择目标舰船工程师')
    return SHIP_ENGINEERS[CHOICES.index(choice)][1]
