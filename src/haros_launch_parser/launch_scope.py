# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from collections import namedtuple
import os
import random
import socket
import sys

import yaml

# from .metamodel import ScopeCondition

if not hasattr(__builtins__, 'basestring'): basestring = (str, bytes)

###############################################################################
# Errors and Exceptions
###############################################################################

class ArgError(KeyError):
    @classmethod
    def undeclared(cls, name):
        return cls(name, 'undeclared')

    @classmethod
    def duplicate(cls, name):
        return cls(name, 'already defined')

    @property
    def arg_name(self):
        return self.args[0]

    #def __str__(self):
    #    return '$(arg {name}): {name} is {what}'.format(
    #        name=self.args[0], what=self.args[1])


###############################################################################
# Launch File Scopes
###############################################################################

class BaseScope(object):
    __slots__ = ('parent', 'system', 'dirpath', 'ns', 'args', 'arg_defaults',
                 'condition', 'remaps', 'anonymous', 'node_env')

    def __init__(self, parent, system, dirpath, ns, args, arg_defaults,
                 remaps, condition, anon, env):
        # `parent` is the parent scope or None if root scope
        # `system` is the API to the ROS/file system
        # `dirpath` is a pathlib.Path
        # `ns` is the current namespace for this scope
        # `args` is the dict of currently defined/assigned args
        # `arg_defaults` is the dict of declared args
        # `remaps` is the dict of available remaps
        # `anonymous` is the anonymous name cache
        # `env` is the new environment variables assigned with <env>
        # `condition` is the LogicValue affecting this scope
        self.parent = parent
        self.system = system
        self.dirpath = dirpath
        self.ns = ns
        self.args = args
        self.arg_defaults = arg_defaults
        self.remaps = remaps
        self.condition = condition
        self.anonymous = anon
        self.node_env = env

    @property
    def private_ns(self):
        return self.ns

    @property
    def filepath(self):
        if parent is None:
            return None
        return parent.filepath

    @property
    def is_present(self):
        return self.condition.is_true

    @property
    def is_absent(self):
        return self.condition.is_false

    @property
    def is_conditional(self):
        return not self.is_present and not self.is_absent

    def get_conditions(self): # FIXME: might not be needed
        conditions = []
        scope = self
        while scope is not None:
            if not scope.condition.is_true:
                conditions.append(scope.condition)
            scope = scope.parent
        if conditions:
            conditions.reverse()
        return conditions

    def get_arg(self, name):
        if name not in self.arg_defaults:
            raise ArgError.undeclared(name)
        try:
            return self.args[name]
        except KeyError:
            return self.arg_defaults[name]

    def declare_arg(self, name, default=None):
        if name in self.arg_defaults:
            raise ArgError.duplicate(name)
        self.arg_defaults[name] = default

    def set_arg(self, name, value):
        self.declare_arg(name)
        self.args[name] = value

    def get_env(self, name):
        return self.system.get_environment_variable(name)

    def set_env(self, name, value):
        self.node_env[name] = value

    def get_pkg_path(self, name):
        dirpath = self.system.get_package_path(name)
        return None if dirpath is None else str(dirpath)

    def get_anonymous_name(self, name):
        value = self.anonymous.get(name)
        if value is None:
            value = self._anonymous_name(name)
            self.anonymous[name] = value
        return value

    def _anonymous_name(self, name):
        # Behaviour copied from rosgraph.names.anonymous_name(id)
        name = '{}_{}_{}_{}'.format(name, socket.gethostname(),
            os.getpid(), random.randint(0, sys.maxsize))
        return name.replace('.', '_').replace('-', '_').replace(':', '_')

    def get_remap(self, name): # FIXME: this might not be needed
        # may be None if `to` is unknown
        return self.remaps.get(name, name)

    def set_remap(self, from_name, to_name):
        source = RosName.resolve(from_name, self.ns, private_ns=self.private_ns)
        target = RosName.resolve(to_name, self.ns, private_ns=self.private_ns)
        self.remaps[source] = target

    def set_param(self, name, value, param_type, condition, location,
                  reason=None, ns=None):
        # check if forward param
        pass # FIXME

    def new_group(self, ns, condition):
        # assert isinstance(ns, str)
        # assert isinstance(condition, LogicValue)
        parent = self
        system = self.system
        dirpath = self.dirpath
        if ns is not None:
            ns = RosName.resolve(ns, self.ns, private_ns=self.private_ns)
        args = self.args
        arg_defaults = self.arg_defaults
        remaps = dict(self.remaps)
        ifunless = condition
        anon = self.anonymous
        env = dict(self.node_env)
        new = GroupScope(parent, system, dirpath, ns, args, arg_defaults,
                 remaps, ifunless, anon, env)
        new._fwd_params = list(self._fwd_params) # FIXME
        return new

    def new_node(self, name, ns, condition):
        return new

    def new_include(self, filepath, pass_all_args, ns=None):
        return new

    def new_launch(self):
        return new

    def add_machine(self, name, address, ssh_port, env_loader=None, user=None,
                    pw=None, default=False, timeout=None):
        pass # TODO


class LaunchScope(BaseScope):
    __slots__ = BaseScope.__slots__ + ('passed_args', '_filepath',)

    def __init__(self, filepath, system, ns='/', args=None):
        # `filepath` is a pathlib.Path
        super().__init__(system, filepath.parent, ns, {})
        self.passed_args = args if args is not None else {}
        self._filepath = filepath

    @property
    def filepath(self):
        return self._filepath

    def get_arg(self, name):
        pass # TODO override; look in passed args too


class GroupScope(BaseScope):
    pass


class NodeScope(BaseScope):
    __slots__ = BaseScope.__slots__ + ('rosname',)

    def __init__(self, name, system, dirname, ns, args):
        self.rosname = RosName(name, ns=ns)

    @property
    def private_ns(self):
        return self.rosname

    def new_group(self, ns, condition):
        raise NotImplementedError()






class LaunchScope(object):
    TempParam = namedtuple('TempParam', ['name', 'type', 'value', 'ifs'])

    def __init__(self, launch_file, ns='/', node=None,
                 remaps=None, params=None, args=None, conditions=None):
        self.configuration = config
        self.launch_file = launch_file
        self.namespace = ns
        self.node = node
        self.remaps = remaps if not remaps is None else {}
        self.parameters = params if not params is None else []
        self.arguments = args if not args is None else {}
        self.conditions = conditions if not conditions is None else []
        self._fwd_params = []

    @property
    def private_ns(self):
        return self.node.rosname.full if self.node else self.namespace

    def child(self, ns, condition, launch=None, args=None):
        launch = launch or self.launch_file
        new = LaunchScope(self, self.configuration, launch,
                          ns=self._namespace(ns),
                          remaps=dict(self.remaps),
                          params=self.parameters,
                          args=args if not args is None else self.arguments,
                          conditions=list(self.conditions))
        new._fwd_params = list(self._fwd_params)
        if not condition is True:
            new.conditions.append(condition)
        return new

    def make_node(self, node, name, ns, args, condition, line=None, col=None):
        ns = self._namespace(ns)
        name = name or node.rosname.own
        rosname = RosName(name, ns, self.private_ns)
        self.log.debug('Creating NodeInstance %s for Node %s.',
                       rosname.full, node.name)
        instance = NodeInstance(self.configuration, rosname, node,
            launch=self.launch_file, argv = args, remaps=dict(self.remaps),
            conditions=list(self.conditions))
        if instance._location is not None:
            instance._location.line = line
            instance._location.column = col
        node.instances.append(instance)
        if not condition is True:
            instance.conditions.append(condition)
        previous = self.configuration.nodes.add(instance)
        new_scope = LaunchScope(self, self.configuration, self.launch_file,
            ns=ns, node=instance, remaps=instance.remaps,
            params=self.parameters, args=self.arguments,
            conditions=instance.conditions)
        new_scope._fwd_params = list(self._fwd_params)
        pns = new_scope.private_ns
        for param in self._fwd_params:
            rosname = RosName(param.rosname.given, pns, pns)
            conditions = param.conditions + instance.conditions
            self.log.debug('Creating new forward Parameter %s.', rosname.full)
            new_param = Parameter(self.configuration, rosname, param.type,
                param.value, node_scope=param.node_scope,
                launch=param.launch_file, conditions=conditions)
            new_param._location = param._location
            self.parameters.append(new_param)
        return new_scope

    def make_params(self, name, ptype, value, condition, line=None, col=None):
        if not value is None:
            value = self._convert_value(str(value), ptype)
            ptype = Parameter.type_of(value)
        conditions = list(self.conditions)
        if not condition is True:
            conditions.append(condition)
        if ptype == 'yaml' or isinstance(value, dict):
            self._yaml_param(name, value, conditions, line=line, col=col)
        else:
            rosname = RosName(name, self.private_ns, self.private_ns)
            param = Parameter(self.configuration, rosname, ptype, value,
                              node_scope = not self.node is None,
                              launch = self.launch_file,
                              conditions = conditions)
            if param._location is not None:
                param._location.line = line
                param._location.column = col
            if not self.node and rosname.is_private:
                self._add_param(param, self._fwd_params)
            else:
                self._add_param(param, self.parameters)

    def make_rosparam(self, name, ns, value, condition, line=None, col=None):
    # ---- lazy import as per the oringinal roslaunch code
        global rosparam_yaml_monkey_patch
        if rosparam_yaml_monkey_patch is None:
            import .rosparam_yaml_monkey_patch
        try:
            value = yaml.safe_load(value)
        except yaml.MarkedYAMLError as e:
            raise ConfigurationError(str(e))
    # ----- try to use given name, namespace or both
        ns = self._ns_join(ns or self.private_ns, self.private_ns)
        if name:
            name = self._ns_join(name, ns)
        else:
            if not isinstance(value, dict):
                raise ConfigurationError('"param" attribute must be set'
                                         ' for non-dictionary values')
    # ----- this will unfold, so we can use namespace in place of a name
            name = ns
        conditions = list(self.conditions)
        if not condition is True:
            conditions.append(condition)
        self._yaml_param(name, value, conditions, private=False,
                         line=line, col=col)

    def remove_param(self, name, ns, condition):
        # TODO check whether '~p' = '/rosparam/p' is intended or a bug
        ns = self._ns_join(ns or self.private_ns, self.private_ns)
        name = RosName.resolve(name, ns, '/rosparam')
        param = self.configuration.parameters.get(name)
        if not param:
            raise ConfigurationError('missing parameter: ' + name)
        if not condition is True or self.conditions:
            return
        else:
            self.resources.deleted_params.append(name)

    def _namespace(self, ns, private=False):
        pns = self.private_ns
        if not ns:
            return self.namespace if not private else pns
        if private:
            return RosName.resolve(ns, pns, private_ns=pns)
        return RosName.resolve(ns, self.namespace)

    # as seen in roslaunch code, sans a few details
    def _convert_value(self, value, ptype):
        return convert_value(value, ptype)

    def _yaml_param(self, name, value, conditions, private=True,
                    line=None, col=None):
        private = private and name.startswith('~')
        pns = self.private_ns
        node_scope = not self.node is None
        items = self._unfold(name, value)
        for name, value, independent in items:
            independent = name.startswith('/') or name.startswith('~')
            if independent and name.startswith('~'):
                rosname = RosName(name, '/roslaunch', '/roslaunch')
            else:
                rosname = RosName(name, pns, pns)
            param = Parameter(self.configuration, rosname, None, value,
                              node_scope=node_scope,
                              launch=self.launch_file, conditions=conditions)
            if param._location is not None:
                param._location.line = line
                param._location.column = col
            if independent or not private:
                self._add_param(param, self.parameters)
            else:
                self._add_param(param, self._fwd_params)

    def _unfold(self, name, value):
        result = []
        stack = [('', name, value)]
        while stack:
            ns, key, value = stack.pop()
            name = self._ns_join(key, ns)
            if not isinstance(value, dict):
                result.append((name, value, name == key)) #FIXME sometimes not independent: ~ns/p + a != a
            else:
                for key, other in value.iteritems():
                    stack.append((name, key, other))
        return result

    def _ns_join(self, name, ns):
        '''Dumb version of name resolution to mimic ROS behaviour.'''
        if name.startswith('~') or name.startswith('/'):
            return name
        if ns == '~':
            return '~' + name
        if not ns:
            return name
        if ns[-1] == '/':
            return ns + name
        return ns + '/' + name

    def _add_param(self, param, collection):
        if param.rosname.is_unresolved:
            collection.append(param)
        else:
            rosname = param.rosname.full
            for i in range(len(collection)):
                other = collection[i]
                if rosname == other.rosname.full:
                    if param.disabled:
                        if other.disabled:
                            collection[i] = param
                    else:
                        collection[i] = param
                    return
            collection.append(param)
