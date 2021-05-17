# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from collections import namedtuple

###############################################################################
# Constants
###############################################################################

###############################################################################
# ROS Names
###############################################################################

class RosName(object):
    pass


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


SolverValue = namedtuple('SolverValue', (
    'value',        # literal value if resolved else [string|UnknownValue]
    'var_type',     # string
    'is_resolved',  # bool
    'unknown'       # [UnknownValue]
))

def _solver_value_as_string(self):
    if self.is_resolved:
        return str(self.value)
    return ''.join((x if isinstance(x, basestring) else '$(?)')
                   for x in self.value)

SolverValue.as_string = _solver_value_as_string

# alias
SolverValue.param_type = property(lambda self: self.var_type)

def ResolvedValue(value, param_type):
    return SolverValue(value, param_type, True, None)

def UnresolvedValue(parts, param_type):
    unknown = tuple(x for x in parts if isinstance(x, UnknownValue))
    assert len(unknown) > 0
    return SolverValue(parts, param_type, False, unknown)


ScopeCondition = namedtuple('ScopeCondition', (
    'statement', # string
    'value',     # SolverValue
    'location'   # SourceLocation
))

def _scope_condition_as_string(self):
    return '{} ({})'.format(self.statement, self.value.as_string())

ScopeCondition.as_string = _scope_condition_as_string

def IfCondition(value, location):
    return ScopeCondition('if', value, location)

def UnlessCondition(value, location):
    return ScopeCondition('unless', value, location)


# Basically Disjunctive Normal Form,
#   `paths` represents all the possible paths (`or`)
#   each path is a conjunction of conditions (`and`)
#   e.g.: `(c1 and c2 and c3) or (c1 and c3) or (c4)`
class PresenceCondition(object):
    __slots__ = (
        'paths', # [[ScopeCondition]]
    )

    def __init__(self, paths=None):
        self.paths = paths if paths is not None else [[]]

    def add_path(self, path=None):
        path = path if path is not None else []
        self.paths.append(path)

    def add_branch(self, i=-1):
        if self.paths[i]:
            self.paths.append(list(self.paths[i]))

    def append(self, condition, i=-1):
        self.paths[i].append(condition)

    def append_to_all(self, condition):
        for path in self.paths:
            path.append(condition)

    def __str__(self):
        conjuncts = []
        for path in self.paths:
            s = ' and '.join(cond.as_string() for cond in path)
            conjuncts.append('({})'.format(s))
        return ' or '.join(conjuncts)


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
        self.condition = condition


class RosNode(RosResource):
    __slots__ = RosResource.__slots__ + ()

    def __init__(self, system, rosname):
        super(RosNode, self).__init__(system, rosname)


class RosParameter(RosResource):
    __slots__ = RosResource.__slots__ + ()

    def __init__(self, system, rosname):
        super(RosParameter, self).__init__(system, rosname)
