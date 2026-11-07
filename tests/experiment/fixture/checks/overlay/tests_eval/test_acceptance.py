import unittest

from pricing import apply_discount


class Acceptance(unittest.TestCase):
    def test_reduces_by_percent(self):
        self.assertEqual(apply_discount(200, 25), 150.0)
        self.assertEqual(apply_discount(80, 0), 80)
