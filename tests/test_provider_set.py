
import unittest
import mock

from tiedye import ProviderSet


class TestProviderSet(unittest.TestCase):

    def test_direct_instantiate(self):
        # Can't instantiate directly
        with self.assertRaises(Exception):
            ProviderSet()

    def test_definition(self):
        interface1 = mock.Mock(name="interface1")
        interface2 = mock.Mock(name="interface2")

        class TestProvidersBase(ProviderSet):

            @ProviderSet.provide(
                interface1,
                i2=interface2,
            )
            def get_impl1(self, i1, i2):
                pass

        class TestProviders(TestProvidersBase):

            @ProviderSet.provide(
                interface1,
                interface2,
            )
            def get_impl2(self, i2):
                pass

        self.assertEqual(
            TestProvidersBase.providers,
            set([
                TestProviders.get_impl1.im_func,
            ])
        )

        self.assertEqual(
            TestProviders.providers,
            set([
                TestProviders.get_impl1.im_func,
                TestProviders.get_impl2.im_func,
            ])
        )

        self.assertEqual(
            TestProviders.get_impl1.im_func.provider_interfaces,
            set([interface1]),
        )
        self.assertEqual(
            TestProviders.get_impl1.im_func.provider_dependencies,
            {
                "i2": interface2,
            },
        )
        self.assertEqual(
            TestProviders.get_impl2.im_func.provider_interfaces,
            set([interface1, interface2]),
        )
        self.assertEqual(
            TestProviders.get_impl2.im_func.provider_dependencies,
            {},
        )
