
import weakref
import functools
import types


EMPTY_DEPS = {}


class Application(object):

    def __init__(self):
        self.dependency_map = weakref.WeakKeyDictionary()

    def dependencies(self, *args, **mapping):
        def register(callable):
            self.dependency_map[callable] = mapping
            return callable
        if len(args) == 1:
            register(args[0])
        elif len(args) == 0:
            return register
        else:
            raise TypeError(
                "Application.dependencies takes either one positional "
                "argument (when used as a function) or no positional "
                "arguments (when used as a decorator); %i given" % (
                    len(args)
                )
            )

    def make_injector(self, *provider_sets, **kwargs):
        """
        Create an :py:class:`Injector` instance for the current app.

        Once an application has dependency lists for a number of callables,
        an injector from that application can be used to automatically provide
        the dependency objects.

        When instantiating an injector, the calling application passes in one
        or more instances of :py:class:`ProviderSet` subclasses whose
        providers will be registered on the injector.

        A caller may optionally pass in a special named argument called
        ``local_providers`` which is a mapping from interface identifiers
        to provider functions. This is an alternative to wrapping a set
        of providers in a :py:class:`ProviderSet` when e.g. the application
        wants to provide a small set of extra local variables.

        A provider function is any callable that takes an interface instance
        returns an implementation of the given interface. If the provider
        function has registered dependencies then these will be bound before
        the provider function is called.

        """
        return Injector(
            self,
            provider_sets,
            kwargs.get("local_providers"),
        )


class Injector(object):
    """
    Implements a mapping from interfaces to object providers.

    Instead of instantiating ``Injector`` directly, prefer to use
    :py:meth:`Application.make_injector`.
    """

    def __init__(self, app, provider_sets, local_providers=None):
        self.app = app
        providers = {}

        # Build up a providers map from the provider sets, implicitly
        # declaring the provider dependencies on the app for later binding.
        # Doing this late allows us to avoid tethering a provider set to
        # any particular app, thus allowing many apps to share a provider set
        # in an external shared library.
        for provider_set in provider_sets:
            for provider_impl in provider_set.providers:
                # Register the dependencies on our app.
                self.app.dependencies(
                    provider_impl,
                    **provider_impl.provider_dependencies
                )
                # provider_impl is a raw function that isn't yet bound
                # to an instance, so we need to bind it to get the
                # actual provider.
                inst_provider_impl = types.MethodType(
                    provider_impl,
                    provider_set,
                )
                for interface in provider_impl.provider_interfaces:
                    providers[interface] = (
                        inst_provider_impl
                    )

        if local_providers is not None:
            providers.update(local_providers)

        # Expose the injector itself as an injectable object
        providers[Injector] = lambda dummy: self

        self.providers = providers
        self.currently_binding = set()
        self.bound_funcs = weakref.WeakKeyDictionary()

    def bind(self, func):
        """
        Bind dependencies to a callable.

        Takes any callable and returns a new wrapper callable that
        accepts the same arguments as the initial callable except that
        registered dependencies are automatically passed in.

        The returned callable can then be called with any further arguments
        that were not provided as dependencies.

        Any requested interfaces for which no provider is available will
        be left unbound, and can thus be provided explicitly in a call
        to the returned callable or bound separately by a later call to
        :py:meth:`Injector.bind`; this is known as *partial binding*.
        """

        # This is deliberately using 'func' rather than the 'lookup_func'
        # from below because when we're binding to an instance method we need
        # to create a distinct binding for each instance, not just one binding
        # for the method's function.
        if func in self.bound_funcs:
            return self.bound_funcs[func]

        # If we've been given a bound method then we need to peel off
        # the binding wrapper to find the item in our dependencies table,
        # but we still want to return a wrapper around exactly what was
        # provided, so an injected bound method stays bound.
        if isinstance(func, types.MethodType):
            lookup_func = func.im_func
        else:
            lookup_func = func

        if lookup_func in self.currently_binding:
            raise DependencyCycleError(
                "Dependency cycle between the following callables: %s" % (
                    ", ".join(self.currently_binding),
                )
            )

        self.currently_binding.add(lookup_func)

        try:
            deps = self.app.dependency_map[lookup_func]
        except KeyError:
            deps = EMPTY_DEPS

        kwargs = {}
        unprovided = {}
        for arg_name, interface in deps.iteritems():
            interface_type = type(interface)
            if interface in self.providers:
                provider = self.providers[interface]
            elif interface_type in self.providers:
                provider = self.providers[interface_type]
            else:
                # Record unprovided interfaces to allow partial injection,
                # e.g. to allow some interfaces to be injected at application
                # startup time and then others to be injected on a
                # per-request basis.
                unprovided[arg_name] = interface
                continue

            # Recursively bind the provider too, so it can request
            # dependencies of its own.
            provider = self.bind(provider)

            kwargs[arg_name] = provider(interface)

        self.currently_binding.remove(lookup_func)

        injected = functools.partial(func, **kwargs)
        if len(unprovided) > 0:
            self.app.dependencies(
                injected,
                **unprovided
            )
        self.bound_funcs[func] = injected
        return injected

    def specialize(self, *provider_sets, **kwargs):
        """
        Create a new injector initialized with the same provider
        configuration as this one, and for the same application,
        but with some additional providers. Takes the same arguments
        as :py:meth:`Application.make_injector`.

        The primary use for this is to create an application-wide injector
        on startup, containing items that should live for the lifetime of the
        application, and then create a derived injector for each request
        that includes additional request-specific items, such as an
        object representing the requesting user.

        This can be combined with partial binding (as described on
        :py:meth:`Injector.bind`) to do up-front as much dependency
        provision as possible, but defer a few request-specific dependencies
        until the request is being handled.
        """
        # By the time we're in here the original provider sets we were
        # passed have already be flattened into our providers dict,
        # so we don't need to worry about flattening them again.
        new_providers = dict(self.providers)
        local_providers = kwargs.get("local_providers")
        if local_providers is not None:
            new_providers.update(local_providers)
        return Injector(
            self.app,
            provider_sets,
            new_providers,
        )


def make_interface(name=None):
    """
    Create a single interface instance.

    The returned interface instance is guaranteed not to share a type with
    any other interface, so this method is good for one-off interfaces.
    If you have a set of interfaces that are all variants of the same
    type then consider using :py:func:`make_interface_enum` instead, so to
    enable the registration of a single provider function that works for
    all instances of the enumeration.
    """
    if_type = type(name, (object,), {})
    return if_type()


def make_interface_enum(*names):
    """
    Create an interface enumeration type.

    A common case is to have a set of related interfaces that all belong
    to a common container type. Since interfaces have no behavior of their
    own, all that's required is to have a distinct instance for each
    interface.

    This function provides a simple way to create a set of singleton interface
    instances that all share a common type. Just pass in the set of valid
    interface names and this function will return a type object whose
    attributes are instances of the type named after the provided names,
    with a separate instance for each given name.
    """
    type_name = "interface_enum(%s)" % (", ".join(names))
    if_type = type(type_name, (object,), {
        "__repr__": lambda self: "<%s.%s>" % (type_name, self.name),
    })
    for name in names:
        if_inst = if_type()
        if_inst.name = name
        setattr(if_type, name, if_inst)
    return if_type


class ProviderSetMeta(type):

    def __new__(self, name, bases, dict):
        providers = set()

        # "inherit" all of the providers from the base type
        for base_type in bases:
            base_type_providers = getattr(base_type, "providers", None)
            if base_type_providers is not None:
                providers.update(base_type_providers)

        # Now add all of the providers on *this* type
        for member in dict.itervalues():
            if callable(member):
                # If this attribute is present then we know the method
                # was decorated with @ProviderSet.provide.
                if hasattr(member, "provider_interfaces"):
                    providers.add(member)

        dict["providers"] = providers

        return type.__new__(self, name, bases, dict)


class ProviderSet(object):
    __metaclass__ = ProviderSetMeta

    def __init__(self):
        if type(self) is ProviderSet:
            raise Exception(
                "Don't instantiate ProviderSet directly. Subclass it instead."
            )

    @staticmethod
    def provide(*interfaces, **dependencies):
        def annotate(func):
            func.provider_interfaces = set(interfaces)
            func.provider_dependencies = dependencies
            return func
        return annotate


class DependencyCycleError(Exception):
    pass
