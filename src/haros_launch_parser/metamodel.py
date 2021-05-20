# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from __builtins__ import range
from collections import namedtuple
import re

from .logic import LOGIC_TRUE

###############################################################################
# Constants
###############################################################################

VAR_STRING = '$(?)'

###############################################################################
# ROS Names
###############################################################################

class RosName(object):
    __slots__ = ('_given', '_name', '_own', '_ns')

    WILDCARD = '*'

    @staticmethod
    def resolve(name, ns='/', pns=''):
        if name.startswith('~'):
            if pns.endswith('/'):
                return pns + name[1:]
            return pns + '/' + name[1:]
        elif name.startswith('/'):
            return name
        elif ns.endswith('/'):
            return ns + name
        return ns + '/' + name

    @staticmethod
    def transform(name, ns='/', pns='', remaps=None):
        name = RosName.resolve(name, ns=ns, pns=pns)
        if remaps:
            return remaps.get(name, name)
        return name

    def __init__(self, name, ns='/', pns='', remaps=None):
        name = name or ''
        self._given = name
        self._name = RosName.transform(name, ns=ns, pns=pns, remaps=remaps)
        if self._name.endswith('/'):
            self._own = ''
            self._ns = self._name
        else:
            parts = self._name.rsplit('/', 1)
            self._own = parts[-1]
            self._ns = parts[0] or '/'

    @property
    def full(self):
        return self._name

    @property
    def own(self):
        return self._own

    @property
    def namespace(self):
        return self._ns

    @property
    def given(self):
        return self._given

    @property
    def is_global(self):
        return self._given.startswith('/')

    @property
    def is_private(self):
        return self._given.startswith('~')

    @property
    def is_unknown(self):
        return self.WILDCARD in self._name

    def join(self, name):
        return RosName(name, ns=self._name, pns=self._name)

    def to_pattern(self):
        assert self._name.startswith('/')
        parts = self._name.split('/')
        assert not parts[0]
        for i in range(len(parts)):
            if parts[i] == self.WILDCARD:
                parts[i] = '(.+?)'
            else:
                parts[i] = parts[i].replace(self.WILDCARD, '(.*?)')
        parts.append('$')
        return '/'.join(parts)

    def to_regex(self):
        return re.compile(self.to_pattern())

    def __eq__(self, other):
        if isinstance(self, other.__class__):
            return self._name == other._name
        return self._name == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self._name.__hash__()

    def __str__(self):
        return self._name

    def __repr__(self):
        return "{}({!r}, ns={!r})".format(
            type(self).__name__, self._own, self._ns)


###############################################################################
# General-purpose Classes
###############################################################################

SourceLocation = namedtuple('SourceLocation', (
    'package',  # string|None
    'filepath', # string
    'line',     # int > 0
    'column'    # int > 0
))


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

def UnresolvedValue(parts, param_type):
    unknown = tuple(x for x in parts if isinstance(x, UnknownValue))
    assert len(unknown) > 0
    return SolverResult(parts, param_type, False, unknown)


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
# Runtime Entities
###############################################################################

class RosRuntimeEntity(object):
    __slots__ = ('name',)

    def __init__(self, rosname):
        self.name = rosname


class RosResource(RosRuntimeEntity):
    __slots__ = RosRuntimeEntity.__slots__ + ('system', 'condition')

    def __init__(self, system, rosname, condition=None):
        super(RosResource, self).__init__(rosname)
        self.system = system
        self.condition = condition or LOGIC_TRUE


class RosNode(RosResource):
    __slots__ = RosResource.__slots__ + ()

    def __init__(self, system, rosname, condition=None):
        super(RosNode, self).__init__(system, rosname, condition=condition)


class RosParameter(RosResource):
    __slots__ = RosResource.__slots__ + ()

    def __init__(self, system, rosname, condition=None):
        super(RosParameter, self).__init__(system, rosname, condition=condition)
