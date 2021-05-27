# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

import math
try:
    import regex as re
except ImportError:
    import re

from .data_structs import (
    TYPE_BOOL, TYPE_INT, TYPE_DOUBLE, TYPE_STRING, TYPE_STR, TYPE_YAML,
    TYPE_AUTO, STRING_TYPES,
    ResolvedValue, UnknownValue, UnresolvedValue,
)
from .rosparam_yaml_monkey_patch import yaml

###############################################################################
# Errors and Exceptions
###############################################################################

class SubstitutionError(Exception):
    _MSG_EQ = '$({}) takes exactly {} arguments, but received {!r}'
    _MSG_ZERO = '$({}) does not take arguments, but received {!r}'
    @classmethod
    def nargs_eq(cls, cmd, n, args):
        if n == 0:
            return cls(self._MSG_ZERO.format(cmd, args))
        else:
            return cls(self._MSG_EQ.format(cmd, n, args))

    _MSG_GTE = '$({}) takes at least {} arguments, but received {!r}'
    @classmethod
    def nargs_gte(cls, cmd, n, args):
        return cls(self._MSG_GTE.format(cmd, n, args))

    _MSG_LTE = '$({}) takes at most {} arguments, but received {!r}'
    @classmethod
    def nargs_lte(cls, cmd, n, args):
        if n <= 0:
            return cls(self._MSG_ZERO.format(cmd, args))
        else:
            return cls(self._MSG_LTE.format(cmd, n, args))

    @classmethod
    def eval_double_underscore(cls, s):
        msg = '$(eval {}) may not contain double underscore expressions'
        return cls(msg.format(s))


class UnknownValueError(Exception):
    pass


###############################################################################
# Substitution Parser Commands
###############################################################################

class SubstitutionCommand(object):
    __slots__ = ('args',)

    def __init__(self, args, min_args=0, max_args=float('inf')):
        assert min_args >= 0
        assert max_args >= min_args
        if min_args == max_args:
            if len(args) != min_args:
                raise SubstitutionError.nargs_eq(self.name, min_args, args)
        elif len(args) < min_args:
            raise SubstitutionError.nargs_gte(self.name, min_args, args)
        elif len(args) > max_args:
            raise SubstitutionError.nargs_lte(self.name, max_args, args)
        self.args = args

    @property
    def name(self):
        raise NotImplementedError()

    def resolve(self, scope):
        raise NotImplementedError()

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.args)

    def __str__(self):
        return '$({} {})'.format(self.name, ' '.join(self.args))


# This does not exist in ROS; it is just a convenience class.
class DummyCommand(SubstitutionCommand):
    def __init__(self, args):
        super(DummyCommand, self).__init__(args, min_args=1, max_args=1)

    @property
    def name(self):
        return 'dummy'

    def resolve(self, scope):
        return self.args[0]


class ArgCommand(SubstitutionCommand):
    def __init__(self, args):
        super(ArgCommand, self).__init__(args, min_args=1, max_args=1)

    @property
    def name(self):
        return 'arg'

    def resolve(self, scope):
        value = scope.get_arg(self.args[0])
        if value is None:
            raise UnknownValueError(self.name, self.args)
        return value


class FindCommand(SubstitutionCommand):
    def __init__(self, args):
        super(FindCommand, self).__init__(args, min_args=1, max_args=1)

    @property
    def name(self):
        return 'find'

    def resolve(self, scope):
        value = scope.get_pkg_path(self.args[0])
        if value is None:
            raise UnknownValueError(self.name, self.args)
        return value


class AnonCommand(SubstitutionCommand):
    def __init__(self, args):
        super(AnonCommand, self).__init__(args, min_args=1, max_args=1)

    @property
    def name(self):
        return 'anon'

    def resolve(self, scope):
        return scope.get_anonymous_name(self.args[0])


class EnvCommand(SubstitutionCommand):
    def __init__(self, args):
        super(EnvCommand, self).__init__(args, min_args=1, max_args=1)

    @property
    def name(self):
        return 'env'

    def resolve(self, scope):
        value = scope.get_env(self.args[0])
        if value is None:
            raise UnknownValueError(self.name, self.args)
        return value


class OptEnvCommand(SubstitutionCommand):
    def __init__(self, args):
        super(OptEnvCommand, self).__init__(args, min_args=1, max_args=2)

    @property
    def name(self):
        return 'optenv'

    def resolve(self, scope):
        value = scope.get_env(self.args[0])
        if value is None:
            return '' if len(self.args) == 1 else self.args[1]
        return value


class DirnameCommand(SubstitutionCommand):
    def __init__(self, args):
        super(DirnameCommand, self).__init__(args, min_args=0, max_args=0)

    @property
    def name(self):
        return 'dirname'

    def resolve(self, scope):
        return str(scope.dirpath)


class EvalCommand(SubstitutionCommand):
    def __init__(self, args):
        super(EvalCommand, self).__init__(args, min_args=1, max_args=1)

    @property
    def name(self):
        return 'eval'

    def resolve(self, scope):
        expr = self.args[0]
        # ignore values containing double underscores (for safety)
        # http://nedbatchelder.com/blog/201206/eval_really_is_dangerous.html
        if expr.find('__') >= 0:
            raise SubstitutionError.eval_double_underscore(expr)
        try:
            return str(eval(expr, {}, _EvalSymbols(scope)))
        except UnknownValueError as e:
            raise e
        except:
            raise UnknownValueError(self.name, self.args)


# adapted from roslaunch
class _EvalSymbols(object):
    __slots__ = ('_scope',)

    # Create a dictionary of global symbols that will be available in eval.
    # Copied from roslaunch.
    _SYMBOLS = {
        'true': True,
        'True': True,
        'false': False,
        'False': False,
        '__builtins__': {
            k: __builtins__[k]
            for k in ('list', 'dict', 'map', 'str', 'float', 'int')
        },
    }

    def __init__(self, scope):
        self._scope = scope

    def __getitem__(self, key):
        if key == 'arg':
            return self._eval_arg
        if key == 'find':
            return self._eval_find
        if key == 'anon':
            return self._eval_anon
        if key == 'env':
            return self._eval_env
        if key == 'optenv':
            return self._eval_optenv
        if key == 'dirname':
            return self._eval_dirname
        try:
            return self._SYMBOLS[key]
        except KeyError:
            return self._eval_arg(key)

    def _eval_arg(self, name):
        value = self._scope.get_arg(name)
        if value is None:
            raise UnknownValueError('arg', (name,))
        return convert_value(value)

    def _eval_find(self, name):
        dirpath = self._scope.get_pkg_path(name)
        if dirpath is None:
            raise UnknownValueError('find', (name,))
        return dirpath

    def _eval_anon(self, name):
        return self._scope.get_anonymous_name(name)

    def _eval_env(self, name):
        value = self._scope.get_env(name)
        if value is None:
            raise UnknownValueError('env', (name,))
        return value

    def _eval_optenv(self, name, default=''):
        value = self._scope.get_env(name)
        return default if value is None else value

    def _eval_dirname(self):
        return str(self._scope.dirpath)

_EvalSymbols._SYMBOLS.update(math.__dict__)


_COMMANDS = {
    'arg': ArgCommand,
    'find': FindCommand,
    'anon': AnonCommand,
    'env': EnvCommand,
    'optenv': OptEnvCommand,
    'dirname': DirnameCommand,
    'eval': EvalCommand
}


###############################################################################
# Substitution Parser
###############################################################################

# Python 2 str vs unicode; not an issue in Python 3
def _strip(s):
    return s.strip()

# Usage:
#   value = '$(find robot_pkg)/$(arg robot_name)'
#   value = SubstitutionParser(value, param_type='string')
#   result = value.resolve(scope)
#   if not result.is_resolved:
#       print('Could not resolve ' + repr(value.text))
#       for x in result.unknown:
#           print('The value of {} is unknown.'.format(x.text))
#   else:
#       print('Resolved to the string ' + repr(result.value))
class SubstitutionParser(object):
    __slots__ = ('text', 'param_type', '_commands')
    # `text`: original string to parse and resolve
    # `param_type`: expected conversion type (str) or None
    # `_commands`: internal list of commands for value resolution

    SUB_PATTERN = re.compile(r'\$\(([^$()]+?)\)')
    ERROR_PATTERN = re.compile(r'\$\([^\$\(\)]*?\$[^\)]*?\)')

    def __init__(self, value, param_type=None):
        if not isinstance(value, STRING_TYPES):
            raise TypeError('expected a string: {!r}'.format(value))
        self.text = value
        self.param_type = param_type
        self._build_command_list(value)

    @classmethod
    def of_bool(cls, value):
        return cls(value, param_type=TYPE_BOOL)

    @classmethod
    def of_int(cls, value):
        return cls(value, param_type=TYPE_INT)

    @classmethod
    def of_double(cls, value):
        return cls(value, param_type=TYPE_DOUBLE)

    @classmethod
    def of_string(cls, value):
        return cls(value, param_type=TYPE_STRING)

    @classmethod
    def of_yaml(cls, value):
        return cls(value, param_type=TYPE_YAML)

    # returns a SolverResult
    # `r.value` is converted to `self.param_type` if possible
    # throws SubstitutionError, ValueError
    def resolve(self, scope):
        parts = []
        unknown = False
        for cmd in self._commands:
            try:
                value = cmd.resolve(scope) #!
                assert isinstance(value, STRING_TYPES)
                parts.append(value)
            except UnknownValueError as e:
                unknown = True
                parts.append(UnknownValue(e.args[0], e.args[1], str(cmd)))
        if unknown:
            return UnresolvedValue(parts, self.param_type)
        value = ''.join(parts)
        value = convert_value(value, param_type=self.param_type) #!
        return ResolvedValue(value, self.param_type)

    def _build_command_list(self, value):
        self._commands = []
        if value.startswith('$(eval '):
            if not value.endswith(')'):
                raise SubstitutionError('eval must span the whole expression')
            if '$(' in value[7:]:
                raise SubstitutionError('"$" cannot appear within expression')
            args = (value[7:-1],)
            return self._commands.append(EvalCommand(args))
        if self.ERROR_PATTERN.search(value):
            raise SubstitutionError('"$" cannot appear within expression')
        match = self.SUB_PATTERN.search(value)
        if not match:
            args = (value,)
            return self._commands.append(DummyCommand(args))
        rest = value
        while match:
            parts = filter(bool, map(_strip, match.group(1).split(None, 1)))
            assert len(parts) == 1 or len(parts) == 2
            cmd_name = parts[0]
            arg_str = parts[1] if len(parts) == 2 else ''
            cmd = _COMMANDS.get(cmd_name)
            if cmd is None:
                raise SubstitutionError('invalid command: ' + cmd_name)
            prefix = rest[:match.start()]
            if prefix:
                if cmd_name == 'eval':
                    raise SubstitutionError('$(eval) must appear at the start')
                args = (prefix,)
                self._commands.append(DummyCommand(args))
            if arg_str:
                assert cmd_name != 'eval'
                args = filter(bool, map(_strip, arg_str.split(None, 1)))
                args = tuple(args)
            else:
                args = ()
            self._commands.append(cmd(args))
            rest = rest[match.end():]
            match = self.SUB_PATTERN.search(rest)
        if rest:
            args = (rest,)
            self._commands.append(DummyCommand(args))

    def __repr__(self):
        return '{}({!r}, param_type={!r})'.format(type(self).__name__,
            self.text, self.param_type)

    def __str__(self):
        return self.text

    def __eq__(self, other):
        if not isinstance(other, SubstitutionParser):
            return False
        return self.text == other.text

    def __hash__(self):
        return hash(self.text)


# as seen in roslaunch code, sans a few details
# throws ValueError
def convert_value(value, param_type=None):
    assert isinstance(value, STRING_TYPES), 'type: ' + str(type(value))
    if param_type is None or param_type == TYPE_AUTO:
        # attempt numeric conversion
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError as e:
            pass
        # bool
        lval = value.lower()
        if lval == 'true':
            return True
        if lval == 'false':
            return False
        # string
        return value
    elif param_type == TYPE_STR or param_type == TYPE_STRING:
        return value
    elif param_type == TYPE_INT:
        return int(value)
    elif param_type == TYPE_DOUBLE:
        return float(value)
    elif param_type == TYPE_BOOL:
        value = value.lower().strip()
        if value == 'true' or value == '1':
            return True
        elif value == 'false' or value == '0':
            return False
        raise ValueError('{!r} is not a bool'.format(value))
    elif param_type == TYPE_YAML:
        try:
            return yaml.safe_load(value)
        except yaml.parser.ParserError as e:
            raise ValueError(e)
    else:
        raise ValueError('unknown value type {!r}'.format(param_type))

def convert_to_bool(value):
    return convert_value(value, param_type=TYPE_BOOL)

def convert_to_int(value):
    return convert_value(value, param_type=TYPE_INT)

def convert_to_double(value):
    return convert_value(value, param_type=TYPE_DOUBLE)

def convert_to_yaml(value):
    return convert_value(value, param_type=TYPE_YAML)


def resolve_to_yaml(text, scope):
    unresolved = SubstitutionParser.of_yaml(text) #!
    return unresolved.resolve(scope) #!
