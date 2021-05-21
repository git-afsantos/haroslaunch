# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from __builtins__ import range
import re

from .data_structs import (
    ResolvedBool, ResolvedDouble, ResolvedString, SolverResult, SourceLocation,
)
from .logic import LOGIC_TRUE, LogicValue

###############################################################################
# ROS Names
###############################################################################

class RosName(object):
    __slots__ = ('_given', '_name', '_own', '_ns')

    WILDCARD = '*'
    _FIRST_PART = re.compile(r'^[\~]?([A-Za-z\*][\w\*]*)?$')
    _NAME_CHARS = re.compile(r'^[A-Za-z\*][\w\*]*$')

    @staticmethod
    def check_valid_name(name, no_ns=False, no_empty=True):
        # does not accept `None`
        # does not accept '/' or '~' if `no_ns`
        # does not accept empty own names if `no_empty`
        if name is None:
            raise ValueError('invalid ROS name: ' + name)
        if no_empty and not name:
            raise ValueError('ROS name cannot be empty')
        if no_ns:
            m = self._NAME_CHARS.match(name)
            if not m or m.group(0) != name:
                raise ValueError('invalid ROS name: ' + name)
        else:
            parts = name.split('/')
            m = self._FIRST_PART.match(parts[0])
            if not m or m.group(0) != parts[0]:
                raise ValueError('invalid ROS name: ' + name)
            for i in range(1, len(parts)-1):
                m = self._NAME_CHARS.match(parts[i])
                if not m or m.group(0) != parts[i]:
                    raise ValueError('invalid ROS name: ' + name)
            if no_empty and not parts[-1]:
                raise ValueError('ROS name cannot be empty or end with "/"')
            if len(parts) > 1 and parts[-1]:
                m = self._NAME_CHARS.match(parts[-1])
                if not m or m.group(0) != parts[-1]:
                    raise ValueError('invalid ROS name: ' + name)

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
        self._name = RosName.transform(name, ns=ns, pns=pns, remaps=remaps)
        # RosName.check_valid_name(self._name, no_ns=False, no_empty=False)
        self._given = name
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
# Runtime Entities
###############################################################################

class RosRuntimeEntity(object):
    __slots__ = ('name',)

    def __init__(self, name):
        if isinstance(name, str):
            name = RosName(name)
        else:
            assert isinstance(name, RosName)
        self.name = name


class RosResource(RosRuntimeEntity):
    __slots__ = RosRuntimeEntity.__slots__ + (
        'system',       # None | string
        'condition',    # LogicValue
        'traceability'  # None | SourceLocation
    )

    def __init__(self, name, system=None, condition=None, location=None):
        super(RosResource, self).__init__(name)
        assert system is None or isinstance(system, str)
        assert condition is None or isinstance(condition, LogicValue)
        assert location is None or isinstance(location, SourceLocation)
        self.system = system
        self.condition = condition or LOGIC_TRUE
        self.traceability = location


class RosNode(RosResource):
    __slots__ = RosResource.__slots__ + (
        'package',      # string
        'executable',   # string
        'machine',      # None|SolverResult(TYPE_STRING)
        'is_required',  # SolverResult(TYPE_BOOL)
        'respawns',     # SolverResult(TYPE_BOOL)
        'respawn_delay',# SolverResult(TYPE_DOUBLE)
        'args',         # SolverResult(TYPE_STRING)
        'output',       # SolverResult(TYPE_STRING)
        'working_dir',  # SolverResult(TYPE_STRING)
        'launch_prefix',# None|SolverResult(TYPE_STRING)
    )

    def __init__(self, name, pkg, exec, system=None, args=None, machine=None,
                 required=None, respawn=None, delay=None, output=None, cwd=None,
                 prefix=None, condition=None, location=None):
        super(RosNode, self).__init__(name, system=system, condition=condition,
            location=location)
        assert isinstance(pkg, str)
        assert isinstance(exec, str)
        assert machine is None or isinstance(machine, SolverResult)
        assert required is None or isinstance(required, SolverResult)
        assert respawn is None or isinstance(respawn, SolverResult)
        assert delay is None or isinstance(delay, SolverResult)
        assert args is None or isinstance(args, SolverResult)
        assert output is None or isinstance(output, SolverResult)
        assert cwd is None or isinstance(cwd, SolverResult)
        assert prefix is None or isinstance(prefix, SolverResult)
        self.package = pkg
        self.executable = exec
        self.machine = machine
        self.is_required = required or ResolvedBool(False)
        self.respawns = respawn or ResolvedBool(False)
        self.respawn_delay = delay or ResolvedDouble(0.0)
        self.args = args or ResolvedString('')
        self.output = output or ResolvedString('log')
        self.working_dir = cwd or ResolvedString('ROS_HOME')
        self.launch_prefix = prefix


class RosParameter(RosResource):
    __slots__ = RosResource.__slots__ + ()

    def __init__(self, name, system=None, condition=None):
        super(RosParameter, self).__init__(name, system=system, condition=condition)
