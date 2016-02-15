from collections import OrderedDict
import inspect

import jsonschema


class SimpleSchemaFunction(object):
    def __init__(self, function, simple_schema_override=None):
        self.function = function
        self.argspec = inspect.getargspec(function)

        self.args_count = len(self.argspec.args)
        self.default_count = len(self.argspec.defaults)
        self.required_count = self.args_count - self.default_count

        # Fill in "empty" schema definitions for args or kwargs not
        # present in user-defined schema (if any).
        simple_schema = dict([(k, {})
                              for i, k in enumerate(self.argspec.args)])

        if simple_schema_override:
            simple_schema.update(simple_schema_override)

        for i, k in enumerate(self.argspec.args[self.required_count:]):
            if 'default' not in simple_schema[k]:
                simple_schema[k]['default'] = self.argspec.defaults[i]

        self.schema = {'type': 'object',
                       'properties': simple_schema,
                       'required': self.argspec.args,
                       'additionalProperties':
                       (self.argspec.keywords is not None)}

    def __call__(self, *args, **kwargs):
        named_args = OrderedDict(zip(self.argspec.args, args))
        defaults = OrderedDict([(k, self.schema['properties'][k]['default'])
                                for k in self.argspec.args[len(args):]])
        named_args.update(defaults)
        named_args.update(kwargs)
        jsonschema.validate(named_args, self.schema)
        return self.function(*named_args.values()[:self.args_count], **kwargs)


def simpleschema(simple_schema_override=None):
    def simpleschema_closure(f):
        return SimpleSchemaFunction(f, simple_schema_override)
    return simpleschema_closure
