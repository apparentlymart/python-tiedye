tiedye
======

``tiedye`` is a simple, Pythonic dependency injection helper library.
Rather than providing a large, complex framework that requires you to change
how your application is built, we instead just provide some utilities to
make it simpler to implement the dependency injection style, building from
a technique that works in pure Python, *without* ``tiedye``.

Many people have maintained that a dynamic language like Python does not need
a dependency injection framework. This library is in agreement with that
opinion, and merely provides some optional wiring utilities to make it easier
to instantiate an application built in the DI style. For this reason, much of
this manual describes a way to do DI *without* this library, only at the end
introducing the motivation for ``tiedye`` and its usage.

Contents:

.. toctree::
   :maxdepth: 2

   di

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`

