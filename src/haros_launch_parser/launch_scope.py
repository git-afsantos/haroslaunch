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

from .data_structs import ConditionalData, SolverResult, VariantDict
from .logic import LOGIC_TRUE, LogicValue

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
# Helper Functions
###############################################################################

def _yaml_param(name, ns, pns, value, condition, location):
    params = []
    for key, literal in _unfold(name, value):
        RosName.check_valid_name(key, no_ns=False, no_empty=True)
        ros_name = RosName(key, ns=ns, pns=pns)
        if isinstance(literal, bool):
            v = ResolvedBool(literal)
        elif isinstance(literal, int):
            v = ResolvedInt(literal)
        elif isinstance(literal, float):
            v = ResolvedDouble(literal)
        elif isinstance(literal, basestring):
            v = ResolvedString(literal)
        else:
            v = ResolvedYaml(literal)
        params.append(RosParameter(ros_name, v.param_type, v,
            condition=condition, location=location))
    return params

def _unfold(name, value):
    result = []
    stack = [('', name, value)]
    while stack:
        ns, key, value = stack.pop()
        name = _ns_join(key, ns)
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                stack.append((name, subkey, subvalue))
        else:
            # sometimes not independent: ~ns/p + a != a
            yield (name, value)

def _ns_join(name, ns):
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


###############################################################################
# Launch File Scopes
###############################################################################

class BaseScope(object):
    __slots__ = (
        'parent', # parent scope (subclass of `BaseScope`) or `None`
        'system', # file system for queries
        'ns', # `RosName` with the current namespace
        'args', # dict of `<arg>` with a defined `value`
        'arg_defaults', # dict of declared `<arg>` (with `default` or `None`)
        'condition', # `LogicValue` for the condition affecting the scope
        'anonymous', # cache dict of anonymous names
        'remaps', # `VariantDict` with current `<remap>` rules
        'node_env', # `VariantDict` with environment variables for nodes
        'params', # list of parameters created within the scope
        'fwd_params', # list of declared forward parameters
    )

    def __init__(self, parent, system, ns, args, arg_defaults,
                 condition, anon, remaps, node_env, fwd_params):
        assert parent is None or isinstance(parent, BaseScope)
        assert system is not None
        assert isinstance(ns, RosName)
        assert isinstance(args, dict)
        assert isinstance(arg_defaults, dict)
        assert isinstance(condition, LogicValue)
        assert isinstance(anon, dict)
        assert isinstance(remaps, dict)
        assert isinstance(env, dict)
        assert isinstance(fwd_params, list)
        self.parent = parent
        self.system = system
        self.ns = ns
        self.args = args
        self.arg_defaults = arg_defaults
        self.condition = condition
        self.anonymous = anon
        self.remaps = remaps
        self.node_env = env
        self.params = []
        self.fwd_params = fwd_params

    @property
    def private_ns(self):
        return self.ns

    @property
    def filepath(self):
        if parent is None:
            return None
        return parent.filepath

    @property
    def dirpath(self):
        # `pathlib.Path` to the dir containing launch file
        return self.filepath.parent

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
        assert isinstance(name, str)
        assert default is None or isinstance(default, str)
        if name in self.arg_defaults:
            raise ArgError.duplicate(name)
        self.arg_defaults[name] = default

    def set_arg(self, name, value):
        assert isinstance(name, str)
        assert value is None or isinstance(value, str)
        self.declare_arg(name)
        self.args[name] = value

    def get_env(self, name):
        assert isinstance(name, str)
        return self.system.get_environment_variable(name)

    def set_env(self, name, value, condition):
        assert isinstance(name, str)
        assert isinstance(value, SolverResult)
        assert isinstance(condition, LogicValue)
        self.node_env[name].set(value, condition)

    def get_pkg_path(self, name):
        assert isinstance(name, str)
        dirpath = self.system.get_package_path(name)
        return None if dirpath is None else str(dirpath)

    def get_anonymous_name(self, name):
        assert isinstance(name, str)
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

    def set_remap(self, from_name, to_name, condition):
        assert isinstance(from_name, str)
        assert isinstance(to_name, str)
        assert isinstance(condition, LogicValue)
        RosName.check_valid_name(from_name, no_ns=False, no_empty=True)
        RosName.check_valid_name(to_name, no_ns=False, no_empty=True)
        source = RosName.resolve(from_name, ns=self.ns, pns=self.private_ns)
        target = RosName.resolve(to_name, ns=self.ns, pns=self.private_ns)
        self.remaps[source].set(target, condition)

    def set_param(self, name, value, param_type, condition,
                  ns='', location=None):
        assert isinstance(name, str)
        assert value is None or isinstance(value, SolverResult)
        assert isinstance(param_type, str)
        assert isinstance(condition, LogicValue)
        assert isinstance(ns, str)
        assert location is None or isinstance(location, SourceLocation)
        RosName.check_valid_name(name, no_ns=False, no_empty=True)
        RosName.check_valid_name(ns, no_ns=False, no_empty=False)
        pns = '/roslaunch' if self.private_ns == self.ns else self.private_ns
        ns = RosName.resolve(ns, self.ns, pns=self.private_ns)
        ros_name = RosName(name, ns=ns, pns=self.private_ns)
        if param_type == TYPE_YAML:
            if value.is_resolved and isinstance(value.value, dict):
                # FIXME: sub names starting with '~' (within the dict)
                #   are discarded with param tag
                params = _yaml_param(name, ns, pns, value.value,
                    condition, location)
            else:
                params = (RosParameter(ros_name, param_type, value,
                    condition=condition, location=location),)
        else:
            if value.is_resolved and value.param_type != param_type:
                raise TypeError('expected {!r}, got {!r}'.format(
                    param_type, value.param_type))
            params = (RosParameter(ros_name, param_type, value,
                condition=condition, location=location),)
        self._set_ros_params(params)

    def _set_ros_params(self, params):
        for param in params:
            RosName.check_valid_name(str(param.name),
                no_ns=False, no_empty=True)
            if param.name.is_private:
                self.fwd_params.append(param)
            else:
                self.params.append(param)

    def add_machine(self, name, address, ssh_port, env_loader=None, user=None,
                    pw=None, default=False, timeout=None):
        pass # TODO

    def new_group(self, ns, condition):
        assert isinstance(ns, str)
        assert isinstance(condition, LogicValue)
        RosName.check_valid_name(ns, no_ns=False, no_empty=False)
        parent = self
        system = self.system
        dirpath = self.dirpath
        ns = RosName.resolve(ns, self.ns, pns=self.private_ns)
        args = self.args
        arg_defaults = self.arg_defaults
        remaps = dict(self.remaps) # TODO: defaultdict ConditionalData
        ifunless = condition
        anon = self.anonymous
        env = dict(self.node_env)
        new = GroupScope(parent, system, dirpath, ns, args, arg_defaults,
                 remaps, ifunless, anon, env)
        new._fwd_params = list(self._fwd_params) # FIXME
        return new

    def new_node(self, name, pkg, exe, condition, ns='', machine=None,
                 required=None, respawn=None, delay=None, args=None,
                 output=None, cwd=None, prefix=None, location=None):
        assert isinstance(name, str)
        assert isinstance(pkg, str)
        assert isinstance(exe, str)
        assert isinstance(condition, LogicValue)
        assert ns is None or isinstance(ns, str)
        assert machine is None or isinstance(machine, SolverResult)
        assert required is None or isinstance(required, SolverResult)
        assert respawn is None or isinstance(respawn, SolverResult)
        assert delay is None or isinstance(delay, SolverResult)
        assert args is None or isinstance(args, SolverResult)
        assert output is None or isinstance(output, SolverResult)
        assert cwd is None or isinstance(cwd, SolverResult)
        assert prefix is None or isinstance(prefix, SolverResult)
        assert location is None or isinstance(location, SourceLocation)
        RosName.check_valid_name(name, no_ns=True, no_empty=True)
        RosName.check_valid_name(ns, no_ns=False, no_empty=False)
        # TODO: get remaps and environment variables from scope
        node = RosNode(name, pkg, exe, machine=machine, required=required,
            respawn=respawn, delay=delay, args=args, output=output, cwd=cwd,
            prefix=prefix, condition=condition, location=location)
        return new

    def new_test(self, test_name, name, pkg, exe, condition,
                 ns='', args=None, cwd=None, prefix=None,
                 retries=None, time_limit=None, location=None):
        assert isinstance(test_name, str)
        assert isinstance(name, str)
        assert isinstance(pkg, str)
        assert isinstance(exe, str)
        assert isinstance(condition, LogicValue)
        assert ns is None or isinstance(ns, str)
        assert args is None or isinstance(args, SolverResult)
        assert cwd is None or isinstance(cwd, SolverResult)
        assert prefix is None or isinstance(prefix, SolverResult)
        assert retries is None or isinstance(retries, SolverResult)
        assert time_limit is None or isinstance(time_limit, SolverResult)
        assert location is None or isinstance(location, SourceLocation)
        # TODO: get remaps and environment variables from scope
        test = RosTest(test_name, name, pkg, exe, args=args, cwd=cwd,
            prefix=prefix, retries=retry, time_limit=time_limit,
            condition=condition, location=location)
        return new

    def new_include(self, filepath, ns, condition, pass_all_args):
        assert isinstance(filepath, str)
        assert isinstance(ns, str)
        assert isinstance(condition, LogicValue)
        assert isinstance(pass_all_args, bool)
        RosName.check_valid_name(ns, no_ns=False, no_empty=False)
        return new


class LaunchScope(BaseScope):
    __slots__ = BaseScope.__slots__ + ('_filepath',)

    def __init__(self, filepath, system, ns='/', args=None, anon=None,
                 remaps=None, node_env=None, fwd_params=None):
        # `filepath` is a pathlib.Path
        if isinstance(ns, basestring):
            ns = RosName(ns)
        args = args if args is not None else {}
        anon = anon if anon is not None else {}
        remaps = remaps if remaps is not None else VariantDict()
        node_env = node_env if node_env is not None else VariantDict()
        arg_defaults = {}
        fwd_params = fwd_params if fwd_params is not None else []
        super(LaunchScope, self).__init__(None, system, ns, args, arg_defaults,
            LOGIC_TRUE, anon, remaps, node_env, fwd_params)
        self._filepath = filepath

    @property
    def filepath(self):
        return self._filepath


class GroupScope(BaseScope):
    __slots__ = BaseScope.__slots__


class NodeScope(BaseScope):
    __slots__ = BaseScope.__slots__ + ('node',)

    def __init__(self, node, parent, system, args, arg_defaults, anon):
        assert isinstance(node, RosNode)
        self.node = node
        ns = node.namespace
        condition = node.condition
        remaps = node.remaps
        env = node.environment
        super(NodeScope, self).__init__(parent, system, ns, args, arg_defaults,
            condition, anon, remaps, env, [])

    @property
    def private_ns(self):
        return self.node.name

    def declare_arg(self, name, default=None):
        raise NotImplementedError()

    def set_arg(self, name, value):
        raise NotImplementedError()

    def _set_ros_params(self, params):
        for param in params:
            RosName.check_valid_name(str(param.name),
                no_ns=False, no_empty=True)
            self.params.append(param)

    def add_machine(self, name, address, ssh_port, env_loader=None, user=None,
                    pw=None, default=False, timeout=None):
        raise NotImplementedError()

    def new_group(self, ns, condition):
        raise NotImplementedError()

    def new_node(self, name, pkg, exe, condition, ns='', machine=None,
                 required=None, respawn=None, delay=None, args=None,
                 output=None, cwd=None, prefix=None, location=None):
        raise NotImplementedError()

    def new_test(self, test_name, name, pkg, exe, condition,
                 ns='', args=None, cwd=None, prefix=None,
                 retries=None, time_limit=None, location=None):
        raise NotImplementedError()

    def new_include(self, filepath, ns, condition, pass_all_args):
        raise NotImplementedError()


class IncludeScope(BaseScope):
    __slots__ = BaseScope.__slots__ + ('_filepath',)

    def __init__(self, filepath, parent, system, ns, args, arg_defaults,
                 condition, anon, remaps, node_env, fwd_params):
        super(IncludeScope, self).__init__(parent, system, ns, args,
            arg_defaults, condition, anon, remaps, node_env, fwd_params)
        self._filepath = filepath

    def set_remap(self, from_name, to_name, condition):
        raise NotImplementedError()

    def set_param(self, name, value, param_type, condition,
                  ns='', location=None):
        raise NotImplementedError()

    def add_machine(self, name, address, ssh_port, env_loader=None, user=None,
                    pw=None, default=False, timeout=None):
        raise NotImplementedError()

    def new_group(self, ns, condition):
        raise NotImplementedError()

    def new_node(self, name, pkg, exe, condition, ns='', machine=None,
                 required=None, respawn=None, delay=None, args=None,
                 output=None, cwd=None, prefix=None, location=None):
        raise NotImplementedError()

    def new_test(self, test_name, name, pkg, exe, condition,
                 ns='', args=None, cwd=None, prefix=None,
                 retries=None, time_limit=None, location=None):
        raise NotImplementedError()

    def new_include(self, filepath, ns, condition, pass_all_args):
        raise NotImplementedError()

    def new_launch(self):
        return LaunchScope(self._filepath, self.system, ns=self.ns,
            args=dict(self.args), anon=self.anonymous,
            remaps=VariantDict(self.remaps),
            node_env=VariantDict(self.node_env),
            fwd_params=list(self.fwd_params))






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
