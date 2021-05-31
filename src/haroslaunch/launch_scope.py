# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

import os
from pathlib import Path
import random
import socket
import sys

from .data_structs import (
    ResolvedBool, ResolvedDouble, ResolvedInt, ResolvedString, ResolvedYaml,
    SolverResult, SourceLocation, VariantDict, STRING_TYPES, TYPE_YAML,
)
from .logic import LOGIC_TRUE, LogicValue
from .metamodel import RosMachine, RosName, RosNode, RosParameter, RosTest

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


class MachineError(KeyError):
    @classmethod
    def undeclared(cls, name):
        return cls(name, 'undeclared')

    @classmethod
    def duplicate(cls, name):
        return cls(name, 'already defined')

    @property
    def machine_name(self):
        return self.args[0]


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
        elif isinstance(literal, STRING_TYPES):
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
        'iface', # file system for queries
        'ns', # `RosName` with the current namespace
        'args', # dict of `<arg>` with a defined `value`
        'arg_defaults', # dict of declared `<arg>` (with `default` or `None`)
        'condition', # `LogicValue` for the condition affecting the scope
        'anonymous', # cache dict of anonymous names
        'remaps', # `VariantDict` with current `<remap>` rules
        'node_env', # `VariantDict` with environment variables for nodes
        'params', # list of parameters created within the scope
        'fwd_params', # list of declared forward parameters
        'machines', # `VariantDict` of machines
        '_machine', # singleton list containing the default machine
    )

    def __init__(self, parent, iface, ns, args, arg_defaults, condition,
                 anon, remaps, node_env, fwd_params, machines, def_machine):
        assert parent is None or isinstance(parent, BaseScope)
        assert iface is not None
        assert isinstance(ns, RosName)
        assert isinstance(args, dict)
        assert isinstance(arg_defaults, dict)
        assert isinstance(condition, LogicValue)
        assert isinstance(anon, dict)
        assert isinstance(remaps, dict)
        assert isinstance(node_env, dict)
        assert isinstance(fwd_params, list)
        assert isinstance(machines, dict)
        assert isinstance(def_machine, list) and len(def_machine) == 1
        self.parent = parent
        self.iface = iface
        self.ns = ns
        self.args = args
        self.arg_defaults = arg_defaults
        self.condition = condition
        self.anonymous = anon
        self.remaps = remaps
        self.node_env = node_env
        self.params = []
        self.fwd_params = fwd_params
        self.machines = machines
        self._machine = def_machine

    @property
    def private_ns(self):
        return self.ns

    @property
    def filepath(self):
        if self.parent is None:
            return None
        return self.parent.filepath

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

    @property
    def default_machine(self):
        # NOTE: intentional bug to mimic roslaunch behaviour:
        #   default machine should be limited to the scope
        #   but it actually propagates down
        return self._machine[0]

    @default_machine.setter
    def default_machine(self, machine):
        assert machine is None or isinstance(machine, RosMachine)
        self._machine[0] = machine

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
        return self.iface.get_environment_variable(name)

    def set_env(self, name, value, condition):
        assert isinstance(name, str)
        assert isinstance(value, SolverResult)
        assert isinstance(condition, LogicValue)
        self.node_env[name].set(value, condition)

    def get_pkg_path(self, name):
        assert isinstance(name, str)
        dirpath = self.iface.get_package_path(name)
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
        RosName.check_valid_name(ns, no_ns=False, no_empty=False)
        pns = '/roslaunch' if self.private_ns == self.ns else self.private_ns
        ns = RosName.resolve(ns, ns=self.private_ns, pns=self.private_ns)
        ros_name = RosName(name, ns=ns, pns=self.private_ns)
        if param_type == TYPE_YAML:
            RosName.check_valid_name(name, no_ns=False, no_empty=False)
            if value.is_resolved and isinstance(value.value, dict):
                # FIXME: sub names starting with '~' (within the dict)
                #   are discarded with param tag
                params = _yaml_param(name, ns, pns, value.value,
                    condition, location)
            else:
                params = (RosParameter(ros_name, param_type, value,
                    condition=condition, location=location),)
        else:
            RosName.check_valid_name(name, no_ns=False, no_empty=True)
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

    def add_machine(self, name, address, is_default, is_assignable,
                    env_loader=None, ssh_port=None,
                    user=None, pw=None, timeout=None):
        assert isinstance(name, str)
        assert isinstance(address, str)
        assert isinstance(is_default, bool)
        assert isinstance(is_assignable, bool)
        assert env_loader is None or isinstance(env_loader, SolverResult)
        assert ssh_port is None or isinstance(ssh_port, SolverResult)
        assert user is None or isinstance(user, SolverResult)
        assert pw is None or isinstance(pw, SolverResult)
        assert timeout is None or isinstance(timeout, SolverResult)
        if env_loader is None:
            distro = self.iface.ros_distro
            env_loader = ResolvedString('/opt/ros/{}/env.sh'.format(distro))
        # TODO: mimic 'localhost' address replacement
        m = RosMachine(name, address, is_assignable=is_assignable,
            env_loader=env_loader, ssh_port=ssh_port,
            user=user, pw=pw, timeout=timeout)
        prev = self.machines.get(name)
        if prev is not None and not prev == m:
            raise MachineError.duplicate(name)
        self.machines[name] = m
        if is_default:
            self.default_machine = m
        elif self.default_machine and self.default_machine.name == name:
            self.default_machine = None

    def new_group(self, ns, condition):
        assert isinstance(ns, str)
        assert isinstance(condition, LogicValue)
        RosName.check_valid_name(ns, no_ns=False, no_empty=False)
        ns = RosName(ns, self.ns, pns=self.private_ns)
        condition = self.condition.join(condition).simplify()
        return GroupScope(self, self.iface, ns, dict(self.args),
            dict(self.arg_defaults), condition, self.anonymous,
            VariantDict(self.remaps), VariantDict(self.node_env),
            list(self.fwd_params), self.machines, self._machine)

    def new_node(self, name, pkg, exe, condition, ns='', machine=None,
                 required=None, respawn=None, delay=None, args=None,
                 output=None, cwd=None, prefix=None, location=None):
        assert isinstance(name, str)
        assert isinstance(pkg, str)
        assert isinstance(exe, str)
        assert isinstance(condition, LogicValue)
        assert isinstance(ns, str)
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
        ns = RosName(ns, ns=self.ns, pns=self.private_ns)
        ros_name = RosName(name, ns=ns)
        remaps = VariantDict(self.remaps)
        env = VariantDict(self.node_env)
        condition = self.condition.join(condition).simplify()
        if machine is None:
            if self.default_machine is not None:
                machine = ResolvedString(self.default_machine.name)
        elif machine.is_resolved:
            if machine.value not in self.machines:
                raise MachineError.undeclared(machine.value)
        node = RosNode(ros_name, pkg, exe, args=args, machine=machine,
            required=required, respawn=respawn, delay=delay, output=output,
            cwd=cwd, prefix=prefix, remaps=remaps, env=env, condition=condition,
            location=location)
        return NodeScope(node, self, self.iface, dict(self.args),
            dict(self.arg_defaults), self.anonymous, self.machines,
            self._machine)

    def new_test(self, test_name, name, pkg, exe, condition,
                 ns='', args=None, cwd=None, prefix=None,
                 retries=None, time_limit=None, location=None):
        assert isinstance(test_name, str)
        assert isinstance(name, str)
        assert isinstance(pkg, str)
        assert isinstance(exe, str)
        assert isinstance(condition, LogicValue)
        assert isinstance(ns, str)
        assert args is None or isinstance(args, SolverResult)
        assert cwd is None or isinstance(cwd, SolverResult)
        assert prefix is None or isinstance(prefix, SolverResult)
        assert retries is None or isinstance(retries, SolverResult)
        assert time_limit is None or isinstance(time_limit, SolverResult)
        assert location is None or isinstance(location, SourceLocation)
        RosName.check_valid_name(name, no_ns=True, no_empty=True)
        RosName.check_valid_name(ns, no_ns=False, no_empty=False)
        ns = RosName(ns, ns=self.ns, pns=self.private_ns)
        ros_name = RosName(name, ns=ns)
        remaps = VariantDict(self.remaps)
        env = VariantDict(self.node_env)
        condition = self.condition.join(condition).simplify()
        test = RosTest(test_name, ros_name, pkg, exe, args=args, cwd=cwd,
            prefix=prefix, retries=retry, time_limit=time_limit, remaps=remaps,
            env=env, condition=condition, location=location)
        return NodeScope(test, self, self.iface, dict(self.args),
            dict(self.arg_defaults), self.anonymous, self.machines,
            self._machine)

    def new_include(self, filepath, ns, condition, pass_all_args):
        assert isinstance(filepath, str)
        assert isinstance(ns, str)
        assert isinstance(condition, LogicValue)
        assert isinstance(pass_all_args, bool)
        RosName.check_valid_name(ns, no_ns=False, no_empty=False)
        ns = RosName(ns, self.ns, pns=self.private_ns)
        filepath = Path(filepath)
        condition = self.condition.join(condition).simplify()
        scope = IncludeScope(filepath, self, self.iface, ns,
            dict(self.args), dict(self.arg_defaults), condition,
            self.anonymous, VariantDict(self.remaps),
            VariantDict(self.node_env), list(self.fwd_params),
            self.machines, self._machine)
        if pass_all_args:
            scope.passed_args.update(self.args)
        return scope


class LaunchScope(BaseScope):
    __slots__ = BaseScope.__slots__ + ('_filepath',)

    def __init__(self, filepath, iface, ns='/', args=None, anon=None,
                 remaps=None, node_env=None, fwd_params=None,
                 machines=None, def_machine=None):
        assert isinstance(filepath, Path)
        if isinstance(ns, STRING_TYPES):
            ns = RosName(ns)
        args = args if args is not None else {}
        anon = anon if anon is not None else {}
        remaps = remaps if remaps is not None else VariantDict()
        node_env = node_env if node_env is not None else VariantDict()
        arg_defaults = {}
        fwd_params = fwd_params if fwd_params is not None else []
        machines = machines if machines is not None else VariantDict()
        if isinstance(def_machine, STRING_TYPES):
            def_machine = machines[def_machine]
        if def_machine is None or isinstance(def_machine, RosMachine):
            def_machine = [def_machine]
        super(LaunchScope, self).__init__(None, iface, ns, args,
            arg_defaults, LOGIC_TRUE, anon, remaps, node_env,
            fwd_params, machines, def_machine)
        self._filepath = filepath

    @property
    def filepath(self):
        return self._filepath


class GroupScope(BaseScope):
    __slots__ = BaseScope.__slots__


class NodeScope(BaseScope):
    __slots__ = BaseScope.__slots__ + ('node',)

    def __init__(self, node, parent, iface, args, arg_defaults, anon,
                 machines, def_machine):
        assert isinstance(node, RosNode)
        self.node = node
        ns = node.namespace
        condition = node.condition
        remaps = node.remaps
        env = node.environment
        super(NodeScope, self).__init__(parent, iface, ns, args, arg_defaults,
            condition, anon, remaps, env, [], machines, def_machine)

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
    __slots__ = BaseScope.__slots__ + ('_filepath', 'passed_args')

    def __init__(self, filepath, parent, iface, ns, args, arg_defaults,
                 condition, anon, remaps, node_env, fwd_params, machines,
                 def_machine):
        super(IncludeScope, self).__init__(parent, iface, ns,
            args, arg_defaults, condition, anon, remaps, node_env,
            fwd_params, machines, def_machine)
        self._filepath = filepath
        self.passed_args = {}

    def declare_arg(self, name, default=None):
        assert isinstance(name, str)
        assert default is None or isinstance(default, str)
        pass # no point in declaring args here

    def set_arg(self, name, value):
        assert isinstance(name, str)
        assert value is None or isinstance(value, str)
        if name in self.passed_args:
            raise ArgError.duplicate(name)
        self.passed_args[name] = value

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
        return LaunchScope(self._filepath, self.iface, ns=self.ns,
            args=dict(self.passed_args), anon=self.anonymous,
            remaps=VariantDict(self.remaps),
            node_env=VariantDict(self.node_env),
            fwd_params=list(self.fwd_params),
            machines=self.machines, def_machine=self._machine)
