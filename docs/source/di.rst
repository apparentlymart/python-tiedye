Dependency Injection in Python: A Tutorial
==========================================

*Dependency injection* is a design pattern that aims to allow an application
to be decomposed into several distinct parts that do not directly depend
on one another. This is achieved by having each component receive its
dependencies from the *caller*, rather than by importing or instantiating
them directly.

This chapter is intended to serve a few different purposes:

* Describe some patterns for implementing dependency injection in Python
  *without* any special libraries.

* Describe how ``tiedye`` can be used to help implement one of those
  patterns.

* Help the reader decide if ``tiedye`` is really necessary for a given
  application, or if a plain Python approach would be sufficient or superior.

As an example, let's start from a simple application that does *not* use
dependency injection and then see what problems arise and how we can
address them.

Tightly-coupled Modules
-----------------------

For the remainder of this chapter we will consider a simple application
that retrieves and object and renders it with a template. For performance
reasons it caches the objects and the templates. Here is part of that
application written in a very simple style that is *not* using the
dependency injection pattern.

(For this and later examples we're showing a bunch of different functionality
as if it were in one source file; the comments starting with ``###`` are
intended to show the logical divisions between systems that in practice would
probably be separate Python modules.)

.. code-block:: python

   ### Template Rendering

   import ubertemplates
   import os.path

   template_dir = "templates"

   class TemplateRenderer(object):

       def __init__(self):
           self.template_cache = {}

       def render(data, template_name):
           if template_name in self.template_cache:
               compiled = self.template_cache[template_name]
           else:
               # Call into the third-party template library to compile
               # the template to python source code.
               compiled = ubertemplates.compile_template_to_python(
                   os.path.join(template_dir, template_name + '.tmpl')
               )
               self.template_cache[template_name] = template

           # This particular template engine gives us some Python
           # code to eval to do its work.
           return eval(compiled, data)

   ### Article Model and Data Access Interface

   import uberdatabase

   dsn = "mydb://dbhost.example.com/myapp"

   article_cache = {}

   class Article(object):
       def __init__(self, title, body):
           self.title = title
           self.body = body

   def load_article(article_id):
       if article_id in article_cache:
           raw_data = article_cache[article_id]
       else:
           # Use a third-party database library to get the article data.
           db = uberdatabase.connect(dsn)
           raw_data = db.get("article", article_id)
           article_cache[article_id] = raw_data

       return Article(
           title=raw_data["title"],
           body=raw_data["body"],
       )

   ### Entry Points

   renderer = TemplateRenderer()

   # This is an entry point for this snippet of code.
   # This would be called from elsewhere in the application.
   def render_article(article_id):
       article = load_article(article_id)
       data = {
           "article": article,
       }
       return renderer.render(data, template_name="article")

With this as part of a broader application, some unseen part of the app could
call ``render_article`` with some article id and get back a rendered article
string. This application works, but contains lots of examples of
*tight coupling* between components, including:

* The ``render_article`` function is tightly coupled to one particular
  implementation of loading an article, and to one particular template engine.

* The ``TemplateRenderer`` class is tightly coupled to the ``ubertemplates``
  library, and hard-codes the location of the template directory on disk.

* The ``load_article`` function is tightly coupled with the
  ``uberdatabase`` library, and hard-codes the location of the data.

Furthermore, two components are managing their own caching in a custom way,
which today happens to be an in-memory dictionary.

Now certainly not *all* coupling is bad, and in many ways the art of
software engineering is about figuring out where to split systems into
subsystems and create interfaces between them. However, in the next section
we'll consider one way in which this system's requirements could change and
the problems that arise as a result of the tight coupling.

Changing the Caching Strategy
-----------------------------

Imagine that our article-rendering application has been such a roaring success
that it's time to scale it to run on many different application servers and
handle thousands of different articles.

As part of figuring out how to achieve this, the engineering team decides to
switch away from caching inside a dictionary and instead to have a shared
cache pool using a third-party distributed caching service imaginitively called
``memcache``.

One of our intrepid engineers takes a first stab at replacing the existing
uses of caching with memcache:

.. code-block:: python

   ### Caching Utilities

   import memcache

   cache_servers = [
       'cache1.example.com:11211',
       'cache2.example.com:11211',
       'cache3.example.com:11211',
   ]

   def get_cache():
       return memcache.connect(cache_servers)

   ### Template Rendering

   import ubertemplates
   import os.path

   template_dir = "templates"

   class TemplateRenderer(object):

       def render(data, template_name):
           cache = get_cache()
           if cache.has("template", template_name):
               compiled = cache.get("template", template_name)
           else:
               # Call into the third-party template library to compile
               # the template to python source code.
               compiled = ubertemplates.compile_template_to_python(
                   os.path.join(template_dir, template_name + '.tmpl')
               )
               cache.put("template", template_name, template)

           # This particular template engine gives us some Python
           # code to eval to do its work.
           return eval(compiled, data)

   ### Article Model and Data Access Interface

   import uberdatabase

   dsn = "mydb://dbhost.example.com/myapp"

   class Article(object):
       def __init__(self, title, body):
           self.title = title
           self.body = body

   def load_article(article_id):
       cache = get_cache()
       if cache.has("article", article_id):
           raw_data = cache.get("article", article_id)
       else:
           # Use a third-party database library to get the article data.
           db = uberdatabase.connect(dsn)
           raw_data = db.get("article", article_id)
           cache.put("article", article_id, raw_data)

       return Article(
           title=raw_data["title"],
           body=raw_data["body"],
       )

   ### Entry Points

   renderer = TemplateRenderer()

   # This is an entry point for this snippet of code.
   # This would be called from elsewhere in the application.
   def render_article(article_id):
       article = load_article(article_id)
       data = {
           "article": article,
       }
       return renderer.render(data, template_name="article")

This works, but it was a pretty epic effort to replace every existing
implementation of caching with this new one -- we have to assume that other
parts of this application not shown here were using caching too! We'd need
to repeat this work if we later decided to use a different caching system,
since what we've returned here is specifically the memcache client object.

I'm sure at this point most readers are abuzz with different ways to solve
this problem. For example, those who have worked with the web framework
``django`` will probably think of how it provides a special mechanism for
separating application settings from code (``django.conf``). Some of those
settings are like our hard-coded cache server and database server settings
above, while others are strings that identify classes to be instantiated
to perform a particular function.

Let's take this track for the moment: assuming that we have a ``django``-like
settings system, here's what the "Caching Utilities" section could become:

.. code-block:: python

   ### Caching Utilities

   from uberframework.conf import settings

   class MemcacheCache(object):

       def __init__(self):
           import memcache
           self.memcache = memcache.connect(settings.MEMCACHE_SERVERS)

       def has(self, type, key):
           return self.memcache.has(type, key)

       def get(self, type, key):
           return self.memcache.get(type, key, get)

       def put(self, type, key, value):
           return self.memcache.put(type, key, value)

   class SiderCache(object):

       def __init__(self):
           import sider
           self.sider = sider.connect(settings.SIDER_SERVERS)

       def has(self, type, key):
           return self.sider.contains(type + ":" + key)

       def get(self, type, key):
           return self.sider.retrieve(type + ":" + key)

       def put(self, type, key, value):
           return self.sider.store(type + ":" + key, value)

   def get_cache():
       cache_class_name = settings.CACHE_CLASS
       cache_class = globals()[cache_class_name]
       return cache_class()

What we've created here is in fact an example of the dependency injection
pattern: we've separated the request for a cache from the specific cache
implementation, so now any caller can just ask for a cache and not need to
know what kind of cache was actually returned.

This sort of design can work -- and *has* worked -- for many applications;
as noted, ``django`` itself uses this pattern, as do many applications built
on it.

However, there are limitations of this approach as we will see in the
following section.

Unit Testing
------------

Our imaginary application has now become complicated enough that the team
wants to write automated unit tests as a first step towards safely making
changes.

A *unit test* should test only one part of a system in isolation, with the
goal of ensuring that its own behavior and its interactions with other parts
are correct without also implicitly testing the rest of the system at the
same time.

The most common technique for implementing unit tests is to use *mock objects*
to stand in for a unit's dependencies. Mocks provide a particular interface
but often return just hard-coded response values, and often they also
*log* calls to their methods to allow the test code to ensure the correct
methods were called, and with the correct arguments.

Let's try to write a test for our ``TemplateRenderer`` class, using
the standard Python :py:mod:`unittest` module:

.. code-block:: python

   import unittest
   from myapp import TemplateRenderer, Article

   class TestTemplateRenderer(unittest.TestCase):

       def test_render(self):
           renderer = TemplateRenderer()
           data = {
               "article": Article(
                   title="dummy title",
                   body="dummy body",
               ),
           }
           result = renderer.render(data, template_name="article")
           self.assertEqual(
               result,
               "<h1>dummy title</h1><p>dummy body</p>",
           )

This is certainly an automated test, but it's not strictly a *unit* test
for a number of reasons, including:

* It depends on a particular template from the real application, meaning that
  the test is effectively testing the template as well as the renderer,
  and will need to be updated each time the template changes.

* The test fails to exercise both the
  ``if cache.has("template", template_name)`` branch and the ``else`` branch
  inside ``render``, and in fact it is undetermined which branch will run,
  and in fact a different branch may run for different executions of the
  test depending on the cache state.

* The test reaches out to the same caching servers as the production
  application, which not only means that we're effectively testing the
  behavior of those servers but also that we're at risk of *polluting* the
  main application cache if our code has a bug.

* The test implicitly also tests the ``ubertemplates`` third-party library.
  Testing that a third-party library does what your application expects
  is important, but that's a task for *integration* testing, not *unit*
  testing.

A frequent solution to this problem for applications using the "global
settings object" strategy for dependency injection is to have a separate
configuration for running tests, and probably also e.g. to teach our
``get_cache`` function how to instantiate a mock cache so it can be used
while testing. This solution works somewhat, but fails to account for
each test needing to create its own separate mock configuration for some
reason, and increases the chances that state from one test will inadvertently
persist into another test and change its outcome.

Rather than adding further complexity to the global settings object, a
more straightforward approach is to simply tell the ``TemplateRenderer``
which cache to use *directly*, rather than having it create its own. This
can be achieved by just adding an initializer parameter for each dependency.
Let's see what ``TemplateRenderer`` looks like once we decouple it from
the caching system, the template compiler and the template directory:

.. code-block:: python

   ### Template Rendering

   class TemplateRenderer(object):

       def __init__(self, cache, compile_template):
           self.cache = cache
           self.compile_template = compile_template

       def render(data, template_name):
           if self.cache.has("template", template_name):
               compiled = self.cache.get("template", template_name)
           else:
               # Call into the third-party template library to compile
               # the template to python source code.
               compiled = self.compile_template(template_name)
               self.cache.put("template", template_name, template)

           # This particular template engine gives us some Python
           # code to eval to do its work.
           return eval(compiled, data)

The initializer now takes two new arguments:

* ``cache`` is an object implementing the cache interface, such as a
  ``MemcacheCache`` or a ``SiderCache``, or indeed a mock cache.

* ``compile_template`` is a callable that takes a template name and returns
  Python source code representing that template.

This is a more "traditional" implementation of the dependency injection
pattern, without any special global configuration objects. Instead, we just
"wire up" the dependencies by instantiating them in the caller and passing
them in as parameters. In most situations we'd inject objects rather than just
standalone callables, but both are possible in Python (unlike, say, Java) and
both are valid in different situations to solve different problems. In this
case we could equally have provided a "template compiler" object with a
"compile" method on it, but the example uses a callable simply to illustrate
that it is possible and explore the implications of that approach.

We can now add some mocks to our unit test. For the sake of example here we
use the facilities provided by the :py:mod:`mock` module.

.. code-block:: python

   import unittest
   import mock
   from myapp import TemplateRenderer, Article

   class TestTemplateRenderer(unittest.TestCase):

       def test_render_cache_miss(self):
           cache = mock.Mock()
           cache.has.return_value = False

           compile_template = mock.Mock()
           compile_template.return_value = "'hi ' + name"

           renderer = TemplateRenderer(
               cache=cache,
               compile_template=compile_template,
           )
           data = {
               "name": "world",
           }

           result = renderer.render(data, template_name="article")
           self.assertEqual(
               result,
               "hi world",
           )

           # Cache should've been called with the template name.
           cache.has.assert_called_with("template", "article")

           # Since we simulated a cache miss, cache should also have
           # been updated with the new template value.
           cache.put.assert_called_with("template", "article", "'hi ' + name")

           # Since it was a cache miss we should also have compiled the
           # template.
           compile_template.assert_called_with("article")

       def test_render_cache_hit(self):
           cache = mock.Mock()
           cache.has.return_value = True
           cache.get.return_value = "'hi ' + name"

           # Won't actually be called in this codepath, but
           # required to instantiate anyway.
           compile_template = mock.Mock()

           renderer = TemplateRenderer(
               cache=cache,
               compile_template=compile_template,
           )
           data = {
               "name": "world",
           }

           result = renderer.render(data, template_name="article")
           self.assertEqual(
               result,
               "hi world",
           )

           # Cache should've been called with the template name.
           cache.has.assert_called_with("template", "article")

           # Since we simulated a cache hit, we should also have
           # retrieved the template from the cache.
           cache.get.assert_called_with("template", "article")

           # Since it was a cache hit we should've skipped compiling the
           # template.
           self.assertFalse(compile_template.called)

This new test is now much more self-contained and is not dependent on any
significant global state. The test is in complete control of the environment
in which ``TemplateRenderer`` runs and can thus forcefully exercise both
a cache miss and a cache hit and ensure correct behavior in both cases.

This is still not perfect; for example, we're still calling into the real
:py:func:`eval` function to run the template, but we accept that compromise
since it's a standard part of Python and we're coupled to our programming
language anyway.

This has made our test more useful, but of course we actually changed the
signature of the ``TemplateRenderer`` initializer above, so unless we make
further changes the real application is broken: the global variable
``renderer`` can no longer be initialized since it does not provide the
two new required parameters. We'll fix this in the next section.


