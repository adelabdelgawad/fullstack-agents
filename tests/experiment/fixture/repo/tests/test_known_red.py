import unittest


class KnownRed(unittest.TestCase):
    def test_already_failing(self):
        self.fail("known failure on the source commit")
