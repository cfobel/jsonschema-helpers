JSON schema helpers
===================

This package contains utility functions, etc. for working with the
[`jsonschema`][1] package.



Validating `simpleschema` decorator
===================================

The `simpleschema` decorator can be used to apply [`jsonschema`][1] validation
to arguments and/or keyword arguments of functions/methods.

The decorator accepts a simplified schema, corresponding to only the
[`properties`][2] entry of a `jsonschema` schema.

Consider the following function:

    >>> from jsonschema_helpers import simpleschema
    >>>
    >>> @simpleschema({'a': {'type': 'string'},
    ...                'b': {'type': 'number'},
    ...                'd': {'type': 'integer'}})
    ... def foo(a, b, c, d=1, e=None):  #, **kwargs):
    ...         print a, b, c, d, e

Using [`jsonschema`][1] syntax, types have been specified for arguments `a`,
`b`, and `d`.

If `foo` is called with an incorrect argument type, a `ValidationError`
exception is raised.  In the example below, a string was passed for the value
of the `d` parameter, where an [`integer`][3] type was specified in the
decorated schema above.

    >>> foo('hello', 1.213, 313513, d='bar')
    Traceback (most recent call last):
        ...
    ValidationError: 'bar' is not of type 'integer'
    <BLANKLINE>
    Failed validating 'type' in schema['properties']['d']:
        {'default': 1, 'type': 'integer'}
    <BLANKLINE>
    On instance['d']:
        'bar'

If schema validation succeeds, the decorated function is executed normally.

    >>> foo('hello', 1, None)
    hello 1 None 1 None


Schema short-hand
-----------------

Instead of specifying the parameter schema(s) as a dictionary argument to the
decorator, the schema for a parameter can be set as its Python default value.

For example:

    >>> @simpleschema
    ... def barfoo(a, b={'type': 'string'}, c=3):
    ...     print 'a={}, b={}, c={}'.format(a, b, c)
    ...
    >>> barfoo(1, 'hello')
    a=1, b=hello, c=3
    >>> barfoo(1, 2)
    Traceback (most recent call last):
        ...
    ValidationError: 2 is not of type 'string'
    <BLANKLINE>
    Failed validating 'type' in schema['properties']['b']:
        {'type': 'string'}
    <BLANKLINE>
    On instance['b']:
        2


Default values
--------------

A default value may be specified in a schema definition.  Note that a schema
default overrides a standard Python default value.

For example:

    >>> @simpleschema({'a': {'type': 'string', 'default': 'hello, world!'}})
    ... def bar(a='goodbye, world!'):
    ...         print a
    ...
    >>> bar()
    hello, world!


Keyword arguments
-----------------

Validation can be applied to optional/keyword arguments as well.

For example:

    >>> @simpleschema({'a': {'type': 'string'}})
    ... def foobar(**kwargs):
    ...         print kwargs
    ...
    >>> foobar()  # No keyword argument.
    {}
    >>> foobar(a=1)
    Traceback (most recent call last):
        ...
    ValidationError: 1 is not of type 'string'
    <BLANKLINE>
    Failed validating 'type' in schema['properties']['a']:
        {'type': 'string'}
    <BLANKLINE>
    On instance['a']:
        1

    >>> foobar(a='hello, world!')
    {'a': 'hello, world!'}


Credits
-----------------

Copyright 2016 Christian Fobel <christian@fobel.net>


[1]: http://spacetelescope.github.io/understanding-json-schema/
[2]: http://spacetelescope.github.io/understanding-json-schema/reference/object.html#properties
[3]: http://spacetelescope.github.io/understanding-json-schema/reference/numeric.html#integer
