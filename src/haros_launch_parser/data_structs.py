# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from collections import defaultdict, namedtuple

from .logic import LOGIC_TRUE

if not hasattr(__builtins__, 'basestring'):
    basestring = (str, bytes)

###############################################################################
# Constants
###############################################################################

VAR_STRING = '$(?)'

TYPE_BOOL = 'bool'
TYPE_INT = 'int'
TYPE_DOUBLE = 'double'
TYPE_STRING = 'string'
TYPE_STR = 'str'
TYPE_YAML = 'yaml'
TYPE_AUTO = 'auto'

###############################################################################
# Source Code Location
###############################################################################

SourceLocation = namedtuple('SourceLocation', (
    'package',  # string|None
    'filepath', # string
    'line',     # int > 0
    'column'    # int > 0
))


###############################################################################
# Unknown Values and Variables
###############################################################################

# for cpp conditions we can use 'eval' or 'eval-cpp'
UnknownValue = namedtuple('UnknownValue', (
    'cmd',  # string
    'args', # (string)
    'text'  # string
))


SolverResult = namedtuple('SolverResult', (
    'value',        # literal value if resolved else [string|UnknownValue]
    'var_type',     # string
    'is_resolved',  # bool
    'unknown'       # [UnknownValue]
))

def _solver_result_as_string(self, wildcard=VAR_STRING):
    if self.is_resolved:
        return str(self.value)
    return ''.join((x if isinstance(x, basestring) else wildcard)
                   for x in self.value)

SolverResult.as_string = _solver_result_as_string

# alias
SolverResult.param_type = property(lambda self: self.var_type)

def ResolvedValue(value, param_type):
    return SolverResult(value, param_type, True, None)

def ResolvedBool(value):
    if not isinstance(value, bool):
        raise TypeError('expected a bool, got: ' + repr(value))
    return SolverResult(value, TYPE_BOOL, True, None)

def ResolvedInt(value):
    if not isinstance(value, int):
        raise TypeError('expected an int, got: ' + repr(value))
    return SolverResult(value, TYPE_INT, True, None)

def ResolvedDouble(value):
    if not isinstance(value, float):
        raise TypeError('expected a float, got: ' + repr(value))
    return SolverResult(value, TYPE_DOUBLE, True, None)

def ResolvedString(value):
    if not isinstance(value, basestring):
        raise TypeError('expected a string, got: ' + repr(value))
    return SolverResult(value, TYPE_STRING, True, None)

def ResolvedYaml(value):
    if value is not None:
        types = (dict, list, int, float, bool, basestring)
        if not isinstance(value, types):
            raise TypeError('expected a YAML object, got: ' + repr(value))
    return SolverResult(value, TYPE_YAML, True, None)

def UnresolvedValue(parts, param_type):
    unknown = tuple(x for x in parts if isinstance(x, UnknownValue))
    assert len(unknown) > 0
    return SolverResult(parts, param_type, False, unknown)

def UnresolvedFileContents(filepath):
    unknown = UnknownValue('file', (filepath,), filepath)
    return SolverResult([unknown], TYPE_STRING, False, (unknown,))

def UnresolvedCommandLine(cmd_string):
    unknown = UnknownValue('cmd', (cmd_string,), cmd_string)
    return SolverResult([unknown], TYPE_STRING, False, (unknown,))


###############################################################################
# Conditional Elements
###############################################################################

ScopeCondition = namedtuple('ScopeCondition', (
    'statement', # string
    'value',     # SolverResult
    'location'   # SourceLocation
))

def _scope_condition_as_string(self, wildcard=VAR_STRING):
    return '{} ({})'.format(self.statement,
        self.value.as_string(wildcard=wildcard))

ScopeCondition.as_string = _scope_condition_as_string

def IfCondition(value, location):
    return ScopeCondition('if', value, location)

def UnlessCondition(value, location):
    return ScopeCondition('unless', value, location)


###############################################################################
# Conditional Data
###############################################################################

class ConditionalData(object):
    __slots__ = ('_base', '_variants')

    def __init__(self, value=None, variants=None):
        self._base = value
        self._variants = variants if variants is not None else []

    @property
    def is_deterministic(self):
        return not self._variants

    @property
    def base_value(self):
        return self._base

    def possible_values(self):
        values = []
        for item in reversed(self._variants):
            values.append(item)
        values.append((self._base, LOGIC_TRUE))
        return values

    def get_value(self):
        if self._variants:
            raise ValueError('multiple possible values')
        return self._base

    def set(self, value, condition):
        if condition.is_true:
            self._base = value
            self._variants = []
        elif not condition.is_false:
            self._variants.append((value, condition))

    def __repr__(self):
        return '{}(value={!r}, variants={!r})'.format(
            type(self).__name__, self._base, self._variants)

    def __str__(self):
        values = []
        for v, c in reversed(self._variants):
            values.append('({!r} if {})'.format(v, c))
        values.append(repr(self._base))
        return ' or '.join(values)


def VariantDict(other=None):
    if other is None:
        return defaultdict(ConditionalData)
    return defaultdict(ConditionalData, other)
