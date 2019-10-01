import unittest
from sqlang.sql import SQL, Table, Alias, Token

class ExtensionTester(unittest.TestCase):
    def test_add_attr(self):
        SQL.consume('RULE', 0, lambda x: 'RULE -- RULE')
        x = SQL.RULE()
        self.assertEqual(x.key, 'RULE')
        self.assertEqual(x.elements, (None,))
        self.assertEqual(SQL.eval(x), 'RULE -- RULE')
