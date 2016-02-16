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


class SimpleSchemaFunction(DecoratorMixin):
    # Need to inherit from `DecoratorMixin` to support decorating methods.
    # If `DecoratorMixin` is not used, decorated methods will not be passed
    # instance as first argument.  See [here][1] for more information.
    #
    # [1]: http://stackoverflow.com/questions/22545339/callable-object-decorator-applied-to-method-doesnt-get-self-argument-on-input
    def __init__(self, function, simple_schema_override=None):
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

        # Fill in "empty" schema definitions for args or kwargs not
        # present in user-defined schema (if any).
        simple_schema = dict([(k, {})
                              for i, k in enumerate(self.args)])

        if simple_schema_override:
            simple_schema.update(simple_schema_override)

        for i, k in enumerate(self.args[self.required_count:]):
            if 'default' not in simple_schema[k]:
                simple_schema[k]['default'] = self.defaults[i]

        self.schema = {'type': 'object',
                       'properties': simple_schema,
                       'additionalProperties':
                       (self.argspec.keywords is not None)}
        if self.args:
            self.schema['required'] = self.args
        functools.update_wrapper(self, function)

    def __call__(self, *args, **kwargs):
        unnamed_count = len(self.unnamed_args)
        named_args = OrderedDict(zip(self.args, args[unnamed_count:]))
        defaults = OrderedDict([(k, self.schema['properties'][k]['default'])
                                for k in self.args[len(args):]])
        named_args.update(defaults)
        named_args.update(kwargs)
        jsonschema.validate(named_args, self.schema)
        return self.function(*(list(args[:unnamed_count]) +
                               named_args.values()[:self.args_count]),
                             **kwargs)


def simpleschema(simple_schema_override=None):
    def simpleschema_closure(f):
        return SimpleSchemaFunction(f, simple_schema_override)
    return simpleschema_closure


class AutoSchemaFunction(DecoratorMixin):
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

        # Fill in "empty" schema definitions for args or kwargs not
        # present in user-defined schema (if any).
        simple_schema = dict([(k, {})
                              for i, k in enumerate(self.args)])

        for i, k in enumerate(self.args[self.required_count:]):
            if isinstance(self.defaults[i], dict):
                simple_schema[k] = self.defaults[i]
            else:
                simple_schema[k]['default'] = self.defaults[i]

        if simple_schema_override:
            simple_schema.update(simple_schema_override)

        self.schema = {'type': 'object',
                       'properties': simple_schema,
                       'additionalProperties':
                       (self.argspec.keywords is not None)}
        if self.args:
            self.schema['required'] = self.args
        functools.update_wrapper(self, function)

    def __call__(self, *args, **kwargs):
        unnamed_count = len(self.unnamed_args)
        named_args = OrderedDict(zip(self.args, args[unnamed_count:]))
        default_args = self.args[max(self.required_count, len(args)):]
        defaults = OrderedDict()
        for k in default_args:
            if k not in named_args and k not in kwargs:
                if 'default' not in self.schema['properties'][k]:
                    raise KeyError('`%s` is a required argument.' % k)
                else:
                    defaults[k] = self.schema['properties'][k]['default']
        named_args.update(defaults)
        named_args.update(kwargs)

        jsonschema.validate(named_args, self.schema)
        return self.function(*(list(args[:unnamed_count]) +
                               named_args.values()[:self.args_count]),
                             **kwargs)


def autoschema(simple_schema_override=None):
    def simpleschema_closure(f):
        return AutoSchemaFunction(f, simple_schema_override)
    return simpleschema_closure
