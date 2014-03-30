
import unittest
from mock import MagicMock
from tiedye import Application, Injector


class TestAppAndInjector(unittest.TestCase):

    def test_separate_dependency_registration(self):
        def dummy():
            pass

        interface = MagicMock(name="baz_interface")

        app = Application()
        app.dependencies(dummy, baz=interface)

        self.assertEqual(
            dict(app.dependency_map),
            {
                dummy: {
                    "baz": interface,
                }
            }
        )

        # and dummy can still be called
        dummy()

    def test_decorator_dependency_registration(self):
        interface = MagicMock(name="baz_interface")
        app = Application()

        @app.dependencies(baz=interface)
        def dummy():
            pass

        self.assertEqual(
            dict(app.dependency_map),
            {
                dummy: {
                    "baz": interface,
                }
            }
        )

        # and dummy can still be called
        dummy()

    def test_invalid_dependency_registration(self):
        app = Application()

        def dummy():
            pass

        def dummy2():
            pass

        with self.assertRaises(TypeError):
            # invalid because there are two positional arguments
            # when only zero or one is permitted
            app.dependencies(dummy, dummy2, baz=dummy)

    def test_make_injector(self):
        app = Application()
        interface1 = MagicMock(name="interface1")
        interface2 = MagicMock(name="interface2")
        interface3 = MagicMock(name="interface3")

        # This one will masquerade as a method on a ProviderSet instance.
        def provider1(self, interface, a):
            pass

        provider1.provider_interfaces = set([interface1, interface2])
        provider1.provider_dependencies = {
            "a": interface2,
        }

        def provider2(interface, injector):
            pass

        provider_set = MagicMock()
        provider_set.providers = set([
            provider1,
        ])

        injector = app.make_injector(
            provider_set,
        )
        specialized_injector = injector.specialize(
            local_providers={
                interface2: provider2,
                interface3: provider2,
            }
        )

        self.assertEqual(
            type(injector),
            Injector,
        )
        self.assertEqual(
            injector.app,
            app,
        )
        # Our given providers are registered.
        self.assertEqual(
            injector.providers[interface1].im_func,
            provider1,
        )
        self.assertEqual(
            injector.providers[interface2].im_func,
            provider1,
        )
        # Injector registers a provider for itself.
        self.assertEqual(
            injector.providers[Injector](Injector),
            injector,
        )
        # No other providers are registered.
        self.assertEqual(
            len(injector.providers),
            3,
        )

        self.assertEqual(
            type(specialized_injector),
            Injector,
        )
        self.assertEqual(
            specialized_injector.app,
            app,
        )
        self.assertEqual(
            specialized_injector.providers[interface1].im_func,
            provider1,
        )
        self.assertEqual(
            specialized_injector.providers[interface2],
            provider2,
        )
        self.assertEqual(
            specialized_injector.providers[interface3],
            provider2,
        )
        self.assertEqual(
            specialized_injector.providers[Injector](Injector),
            specialized_injector,
        )
        self.assertEqual(
            len(specialized_injector.providers),
            4,
        )

    def test_injector_full_bind(self):
        app = Application()
        interface1 = MagicMock(name="interface1")
        # Using a tuple as in interface is not a normal case but it works
        # well enough for this test, and shows that we aren't doing anything
        # that *prevents* using a tuple as an interface, if a caller wants to
        # do something unusual.
        interface2 = ("hi", "world")
        interface_type = type(interface2)

        # the provider itself gets bound, so it can declare dependencies
        # if it wants to.
        @app.dependencies(inj=Injector)
        def interface1_provider(iface, inj):
            return "interface1"

        injector = app.make_injector(
            local_providers={
                # provider for a specific interface instance
                interface1: interface1_provider,
                # provider for a whole type of interface, which is used
                # to support cases like automatic RPC proxy generation, etc.
                interface_type: lambda iface: "type %s" % iface[0]
            }
        )

        @app.dependencies(a=interface1, b=interface2)
        def func(a, b):
            return (a, b)

        bound_func = injector.bind(func)

        self.assertTrue(
            callable(bound_func),
        )
        self.assertEqual(
            bound_func(),
            ("interface1", "type hi"),
        )

        # If we call again with the same function we should get back
        # the same 'partial' object.
        bound_func2 = injector.bind(func)
        self.assertTrue(
            bound_func2 is bound_func,
        )

    def test_injector_partial_bind(self):
        app = Application()
        interface1 = MagicMock(name="interface1")
        interface2 = MagicMock(name="interface2")

        @app.dependencies(a=interface1, b=interface2)
        def func(a, b):
            return (a, b)

        injector1 = app.make_injector(
            local_providers={
                interface1: lambda iface: "hi",
            },
        )
        partial_bound_func = injector1.bind(func)

        self.assertEqual(
            partial_bound_func(b="world"),
            ("hi", "world"),
        )

        injector2 = injector1.specialize(
            local_providers={
                interface2: lambda iface: "cheese",
            }
        )

        bound_func = injector2.bind(partial_bound_func)

        self.assertEqual(
            bound_func(),
            ("hi", "cheese"),
        )

    def test_injector_method_bind(self):
        app = Application()
        interface1 = MagicMock(name="interface1")

        class Foo(object):

            def __init__(self, name):
                self.name = name

            @app.dependencies(a=interface1)
            def bar(self, a):
                return (self.name, a)

        foo1 = Foo("foo1")
        foo2 = Foo("foo2")

        injector = app.make_injector(
            local_providers={
                interface1: lambda iface: "interface1"
            }
        )

        foo1_bar = injector.bind(foo1.bar)
        foo2_bar = injector.bind(foo2.bar)

        self.assertEqual(
            foo1_bar(),
            ("foo1", "interface1"),
        )
        self.assertEqual(
            foo2_bar(),
            ("foo2", "interface1"),
        )

        # If we bind foo1.bar again we should get back the same
        # 'partial' object, even though it's distinct from the one we
        # got from foo2.bar
        foo1_bar2 = injector.bind(foo1.bar)
        self.assertTrue(
            foo1_bar2 is foo1_bar,
        )
        foo1_bar2 = injector.bind(foo1.bar)
        self.assertTrue(
            foo1_bar2 is not foo2_bar,
        )
