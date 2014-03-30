
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

    def make_injector(self, providers):
        return Injector(self, providers)


class Injector(object):
    """
    Implements a mapping from interfaces to object providers.

    Once an application has dependency lists for a number of callables,
    an injector from that application can be used to automatically provide
    the dependency objects.

    When instantiating an injector, the calling application passes in
    a mapping object whose keys are either interface instances or interface
    types and whose values are provider functions.

    A provider function is any callable that takes an interface instance and
    an injector as positional arguments and returns an implementation of the
    given interface.
    """

    def __init__(self, app, providers):
        self.app = app
        self.providers = providers
        self.currently_binding = set()
        # Expose the injector itself as an injectable object
        providers[Injector] = lambda dummy: self

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
        return injected

    def specialize(self, more_providers):
        """
        Create a new injector initialized with the same provider
        configuration as this one, and for the same application,
        but with some additional providers.

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
        new_providers = dict(self.providers)
        new_providers.update(more_providers)
        return Injector(self.app, new_providers)


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


class DependencyCycleError(Exception):
    pass
