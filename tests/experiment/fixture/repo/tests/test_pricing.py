import unittest

from pricing import format_price


class FormatPrice(unittest.TestCase):
    def test_two_decimals(self):
        self.assertEqual(format_price(3), "3.00")
