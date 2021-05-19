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


SolverResult = namedtuple('SolverResult', (
    'value',        # literal value if resolved else [string|UnknownValue]
    'var_type',     # string
    'is_resolved',  # bool
    'unknown'       # [UnknownValue]
))

def _solver_result_as_string(self):
    if self.is_resolved:
        return str(self.value)
    return ''.join((x if isinstance(x, basestring) else '$(?)')
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

def _scope_condition_as_string(self):
    return '{} ({})'.format(self.statement, self.value.as_string())

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
        self.condition = condition


class RosNode(RosResource):
    __slots__ = RosResource.__slots__ + ()

    def __init__(self, system, rosname):
        super(RosNode, self).__init__(system, rosname)


class RosParameter(RosResource):
    __slots__ = RosResource.__slots__ + ()

    def __init__(self, system, rosname):
        super(RosParameter, self).__init__(system, rosname)
