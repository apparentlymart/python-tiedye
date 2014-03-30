
import unittest
from tiedye import make_interface


class TestInterface(unittest.TestCase):

    def test_interface_enum(self):
        interface1 = make_interface(
            "hi",
        )
        interface2 = make_interface(
            "howdy",
        )

        self.assertTrue(
            interface1 is not interface2,
        )
        self.assertTrue(
            type(interface1) is not type(interface2),
        )
