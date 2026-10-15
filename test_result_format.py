import unittest

from result_format import format_ly, format_ls, format_population, format_number


class ResultFormatTests(unittest.TestCase):
    def test_ls_fixed_two_places_grouping_and_unknown(self):
        for value, expected in [(0, '0.00'), (28.340535, '28.34'), (1000, '1,000.00'),
                                (1279.406775, '1,279.41')]:
            self.assertEqual(format_ls(value), expected)
        for value in (None, '', True, float('nan'), float('inf')):
            self.assertEqual(format_ls(value, 'Unknown'), 'Unknown')
    def test_ly_fixed_two_places_and_grouping(self):
        for value, expected in [(0, '0.00'), (1, '1.00'), (4.417, '4.42'),
                                (12345.6789, '12,345.68'), ('1000.5', '1,000.50')]:
            self.assertEqual(format_ly(value), expected)

    def test_population_integer_and_grouping(self):
        self.assertEqual(format_population(1234567.0), '1,234,567')
        self.assertEqual(format_population('1000'), '1,000')
        self.assertEqual(format_population(0), '0')
        for value in (1.2, -1, True, None, float('nan'), float('inf')):
            self.assertEqual(format_population(value, '?'), '?')

    def test_missing_ly_and_nonfinite_never_become_zero(self):
        for value in (None, '', 'unknown', True, float('nan'), float('inf')):
            self.assertEqual(format_ly(value, '?'), '?')

    def test_other_values_preserve_precision_without_trailing_zeroes(self):
        self.assertEqual(format_number(1234567.0), '1,234,567')
        self.assertEqual(format_number('12345.67890'), '12,345.6789')
        self.assertEqual(format_number(None, 'Unknown'), 'Unknown')
