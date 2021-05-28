# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from builtins import range
try:
    import regex as re
except ImportError:
    import re

from .data_structs import (
    ResolvedBool, ResolvedDouble, ResolvedInt, ResolvedString, VariantDict,
)
from .logic import LOGIC_TRUE

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
            raise ValueError('ROS name cannot be `None`')
        if not name:
            if no_empty:
                raise ValueError('ROS name cannot be empty')
            return
        if no_ns:
            m = RosName._NAME_CHARS.match(name)
            if not m or m.group(0) != name:
                raise ValueError('invalid ROS name: ' + name)
        else:
            parts = name.split('/')
            m = RosName._FIRST_PART.match(parts[0])
            if not m or m.group(0) != parts[0]:
                raise ValueError('invalid ROS name: ' + name)
            for i in range(1, len(parts)-1):
                m = RosName._NAME_CHARS.match(parts[i])
                if not m or m.group(0) != parts[i]:
                    raise ValueError('invalid ROS name: ' + name)
            if no_empty and not parts[-1]:
                raise ValueError('ROS name cannot be empty or end with "/"')
            if len(parts) > 1 and parts[-1]:
                m = RosName._NAME_CHARS.match(parts[-1])
                if not m or m.group(0) != parts[-1]:
                    raise ValueError('invalid ROS name: ' + name)

    @staticmethod
    def resolve(name, ns='/', pns=''):
        if not name:
            return ns
        if name.startswith('~'):
            if pns.endswith('/'):
                return pns + name[1:]
            return pns + '/' + name[1:]
        elif name.startswith('/'):
            return name
        elif ns.endswith('/'):
            return ns + name
        return ns + '/' + name

    def __init__(self, name, ns='/', pns=''):
        name = str(name or '')
        self._name = RosName.resolve(name, ns=str(ns), pns=str(pns))
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

class RosMachine(object):
    __slots__ = (
        'name',         # string
        'address',      # string URI
        'is_assignable',# bool
        'env_loader',   # SolverResult(TYPE_STRING)
        'ssh_port',     # SolverResult(TYPE_INT)
        'user',         # None|SolverResult(TYPE_STRING)
        'password',     # None|SolverResult(TYPE_STRING)
        'timeout',      # SolverResult(TYPE_DOUBLE)
    )

    def __init__(self, name, address, is_assignable=True, env_loader=None,
                 ssh_port=None, user=None, pw=None, timeout=None):
        self.name = name
        self.address = address
        self.is_assignable = is_assignable
        self.env_loader = env_loader
        self.ssh_port = ssh_port or ResolvedInt(22)
        self.user = user
        self.password = pw
        self.timeout = timeout or ResolvedDouble(10.0)

    def __eq__(self, other):
        if not isinstance(other, RosMachine):
            return False
        return (self.name == other.name and self.address == other.address
                and self.is_assignable is other.is_assignable
                and self.env_loader == other.env_loader
                and self.ssh_port == other.ssh_port
                and self.user == other.user and self.password == other.password
                and self.timeout == other.timeout)


class RosRuntimeEntity(object):
    __slots__ = ('name',) # RosName

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
        self.system = system
        self.condition = condition or LOGIC_TRUE
        self.traceability = location

    @property
    def namespace(self):
        return RosName(self.name.namespace)


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
        'remaps',       # VariantDict(RosName)
        'environment',  # VariantDict(string)
    )

    def __init__(self, name, pkg, exe, system=None, args=None, machine=None,
                 required=None, respawn=None, delay=None, output=None,
                 cwd=None, prefix=None, remaps=None, env=None,
                 condition=None, location=None):
        super(RosNode, self).__init__(name, system=system, condition=condition,
            location=location)
        self.package = pkg
        self.executable = exe
        self.machine = machine
        self.is_required = required or ResolvedBool(False)
        self.respawns = respawn or ResolvedBool(False)
        self.respawn_delay = delay or ResolvedDouble(0.0)
        self.args = args or ResolvedString('')
        self.output = output or ResolvedString('log')
        self.working_dir = cwd or ResolvedString('ROS_HOME')
        self.launch_prefix = prefix
        self.remaps = remaps if remaps is not None else VariantDict()
        self.environment = env if env is not None else VariantDict()

    @property
    def is_test_node(self):
        return False


class RosTest(RosResource):
    __slots__ = RosResource.__slots__ + (
        'test_name',    # string
        'package',      # string
        'executable',   # string
        'args',         # SolverResult(TYPE_STRING)
        'output',       # SolverResult(TYPE_STRING)
        'working_dir',  # SolverResult(TYPE_STRING)
        'launch_prefix',# None|SolverResult(TYPE_STRING)
        'retries',      # SolverResult(TYPE_INT)
        'time_limit',   # SolverResult(TYPE_DOUBLE)
        'remaps',       # VariantDict(RosName)
        'environment',  # VariantDict(string)
    )

    def __init__(self, test_name, name, pkg, exe, system=None, args=None,
                 cwd=None, prefix=None, retries=None, time_limit=None,
                 remaps=None, env=None, condition=None, location=None):
        super(RosTest, self).__init__(name, system=system, condition=condition,
            location=location)
        self.test_name = test_name
        self.package = pkg
        self.executable = exe
        self.args = args or ResolvedString('')
        self.output = output or ResolvedString('log')
        self.working_dir = cwd or ResolvedString('ROS_HOME')
        self.launch_prefix = prefix
        self.retries = retries or ResolvedInt(0)
        self.time_limit = time_limit or ResolvedDouble(60.0)
        self.remaps = remaps if remaps is not None else VariantDict()
        self.environment = env if env is not None else VariantDict()

    @property
    def is_test_node(self):
        return True


class RosParameter(RosResource):
    __slots__ = RosResource.__slots__ + (
        'param_type',   # string
        'value'         # SolverResult(param_type)
    )

    def __init__(self, name, param_type, value, system=None, condition=None,
            location=None):
        super(RosParameter, self).__init__(name, system=system,
            condition=condition, location=location)
        self.param_type = param_type
        self.value = value
