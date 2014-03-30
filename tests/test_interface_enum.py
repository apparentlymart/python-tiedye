
import unittest
from tiedye import make_interface_enum


class TestInterfaceEnum(unittest.TestCase):

    def test_interface_enum(self):
        enum1 = make_interface_enum(
            "foo",
            "bar",
            "baz",
        )
        enum2 = make_interface_enum(
            "foo",
            "bar",
            "baz",
            "wibble",
        )

        self.assertEqual(
            [type(x) for x in (enum1.foo, enum1.bar, enum1.baz)],
            [enum1, enum1, enum1],
        )
        self.assertEqual(
            [type(x) for x in (enum2.foo, enum2.bar, enum2.baz, enum2.wibble)],
            [enum2, enum2, enum2, enum2],
        )
        self.assertTrue(
            enum1.foo is not enum1.bar,
        )
        self.assertTrue(
            enum1.foo is not enum2.foo,
        )
        self.assertTrue(
            enum1 is not enum2,
        )
