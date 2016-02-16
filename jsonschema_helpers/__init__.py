from collections import OrderedDict
import functools
import inspect

import jsonschema


class DecoratorMethod(object):
    # Adapted from [here][1] to support decorating methods.
    #
    # [1]: http://stackoverflow.com/questions/22545339/callable-object-decorator-applied-to-method-doesnt-get-self-argument-on-input
    def __init__(self, decor, instance):
        self.decor = decor
        self.instance = instance

    def __call__(self, *args, **kw):
        return self.decor(self.instance, *args, **kw)

    def __getattr__(self, name):
        return getattr(self.decor, name)

    def __repr__(self):
        return '<bound method {} of {}>'.format(self.decor, type(self))


class DecoratorMixin(object):
    # Adapted from [here][1] to support decorating methods.
    #
    # [1]: http://stackoverflow.com/questions/22545339/callable-object-decorator-applied-to-method-doesnt-get-self-argument-on-input
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return DecoratorMethod(self, instance)


class SchemaMixin(object):
    def __call__(self, *args, **kwargs):
        unnamed_count = len(self.unnamed_args)
        if self.argspec.varargs is None and (len(args) > unnamed_count +
                                             len(self.args)):
            raise TypeError('%s() takes at most %d positional arguments.' %
                            (self.function.func_name, len(self.args)))
        positional_args = dict(zip(self.args, args[unnamed_count:]))

        named_args = OrderedDict()
        for k in self.args:
            if k in positional_args:
                named_args[k] = positional_args[k]
            elif k in kwargs:
                named_args[k] = kwargs.pop(k)
            elif 'default' in self.schema['properties'][k]:
                named_args[k] = self.schema['properties'][k]['default']
            else:
                raise KeyError('`%s` is a required argument.' % k)
        named_args.update(kwargs)

        jsonschema.validate(named_args, self.schema)
        return self.function(*(list(args[:unnamed_count]) +
                               named_args.values()[:self.args_count]),
                             **kwargs)


class SimpleSchemaFunction(SchemaMixin, DecoratorMixin):
    # Need to inherit from `DecoratorMixin` to support decorating methods.
    # If `DecoratorMixin` is not used, decorated methods will not be passed
    # instance as first argument.  See [here][1] for more information.
    #
    # [1]: http://stackoverflow.com/questions/22545339/callable-object-decorator-applied-to-method-doesnt-get-self-argument-on-input
    def __init__(self, function, simple_schema_override=None):
        '''
        Interpret dictionary keyword argument default values as
        jsonschema schema property.
        '''
        self.function = function
        self.argspec = inspect.getargspec(function)

        self.args = self.argspec.args or []

        # Detect if function is a method, using technique described [here][1].
        #
        # [1]: http://stackoverflow.com/questions/8793233/python-can-a-decorator-determine-if-a-function-is-being-defined-inside-a-class
        frames = inspect.stack()

        class_name = None
        for frame in frames[1:]:
            if frame[3] == "<module>":
                # At module level, go no further
                break
            elif '__module__' in frame[0].f_code.co_names:
                class_name = frame[0].f_code.co_name
                break
        self.ismethod = (class_name is not None)

        if self.ismethod:
            self.unnamed_args = self.args[:1]
            self.args = self.args[1:]
        else:
            self.unnamed_args = []
        self.defaults = self.argspec.defaults or []
        self.args_count = len(self.args)
        self.default_count = len(self.defaults)
        self.required_count = self.args_count - self.default_count

        self.schema = self.create_schema(self.args, self.defaults,
                                         self.required_count,
                                         (self.argspec.keywords is not None),
                                         override=simple_schema_override)

        if self.args:
            self.schema['required'] = self.args
        functools.update_wrapper(self, function)

    def create_schema(self, args, defaults, required_count, additional_kwargs,
                      override=None):
        # Fill in "empty" schema definitions for args or kwargs not
        # present in user-defined schema (if any).
        simple_schema = dict([(k, {}) for i, k in enumerate(args)])

        if override:
            simple_schema.update(override)

        for i, k in enumerate(args[required_count:]):
            if isinstance(defaults[i], dict):
                simple_schema[k] = defaults[i]
            elif 'default' not in simple_schema[k]:
                simple_schema[k]['default'] = defaults[i]

        return {'type': 'object', 'properties': simple_schema,
                'additionalProperties': additional_kwargs}


def simpleschema(simple_schema_override=None):
    '''
    Decorator to apply [`jsonschema`][1] validation to arguments and/or keyword
    arguments of functions/methods.

    The `simpleschema` decorator accepts a simplified schema, corresponding to
    only the `properties` entry of a `jsonschema` schema.

    Consider the following function:

    >>> from jsonschema_helpers import simpleschema
    >>>
    >>> @simpleschema({'a': {'type': 'string'},
    ...                'b': {'type': 'number'},
    ...                'd': {'type': 'integer'}})
    ... def foo(a, b, c, d=1, e=None):  #, **kwargs):
    ...         print a, b, c, d, e

    Using [`jsonschema`][1] syntax, types have been specified for arguments
    `a`, `b`, and `d`.

    If `foo` is called with an incorrect argument type, a
    `jsonschema.ValidationError` exception is raised.  In the example below, a
    string was passed for the value of the `d` parameter, where an
    [`integer`][2] type was specified in the decorated schema above.

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

    Instead of specifying the parameter schema(s) as a dictionary argument to
    the decorator, the schema for a parameter can be set as its Python default
    value.

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

    A default value may be specified in a schema definition.  Note that a
    schema default overrides a standard Python default value.

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


    [1]: http://spacetelescope.github.io/understanding-json-schema/
    [2]: http://spacetelescope.github.io/understanding-json-schema/reference/numeric.html#integer
    '''
    if callable(simple_schema_override):
        # Assume `simpleschema` used as a decorator with no call brackets.
        #
        #     @simpleschema
        #     def foo():
        #         ...
        function = simple_schema_override
        return SimpleSchemaFunction(function)
    else:
        # Assume `simpleschema` used as a decorator with call brackets.
        def simpleschema_closure(function):
            return SimpleSchemaFunction(function, simple_schema_override)
        return simpleschema_closure
