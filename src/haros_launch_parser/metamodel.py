# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from __builtins__ import range
import re

from .logic import LOGIC_TRUE

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
