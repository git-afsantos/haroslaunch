# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from collections import namedtuple

from .data_structs import (
    IfCondition, ResolvedString, ResolvedValue, SourceLocation, UnlessCondition,
    UnresolvedCommandLine, UnresolvedFileContents
)
from .launch_scope import (
    ArgError, LaunchScope, NodeScope, GroupScope
)
from .launch_xml_parser import SchemaError
from .logic import LOGIC_TRUE, LOGIC_FALSE, LogicVariable
from .metamodel import (
    RosName, RosNode, RosParameter, RosTest
)
from .sub_parser import (
    TYPE_STRING, TYPE_YAML,
    convert_to_bool, convert_to_yaml, convert_value,
    resolve_to_yaml,
    SubstitutionError, SubstitutionParser
)

if not hasattr(__builtins__, 'basestring'): basestring = (str, bytes)

###############################################################################
# Errors and Exceptions
###############################################################################

class LaunchInterpreterError(Exception):
    pass

class SanityError(Exception):
    @classmethod
    def conditional_tag(cls, tag, condition):
        what = ', '.join(x.text for x in condition.data.value.unknown)
        msg = 'unable to resolve conditional <{}>: unknown {}'
        return cls(msg.format(tag.tag, what))

    @classmethod
    def cannot_resolve(cls, unknown):
        what = ', '.join(x.text for x in unknown)
        return cls('unable to resolve ' + what)


def _empty_value(attr):
    return ValueError('{!r} must not be empty'.format(attr))


###############################################################################
# Helper Functions
###############################################################################

def _launch_location(filepath, tag):
    return SourceLocation(None, str(filepath), tag.line, tag.column)

def _literal(substitution_result):
    if not substitution_result.is_resolved:
        raise SanityError.cannot_resolve(substitution_result.unknown)
    return substitution_result.value

def _literal_or_None(substitution_result):
    if substitution_result is None or not substitution_result.is_resolved:
        return None
    return substitution_result.value

def _string_or_None(substitution_result):
    if substitution_result is None:
        return None
    return substitution_result.as_string()

def _rosname_string(substitution_result):
    if substitution_result is None:
        return ''
    name = substitution_result.as_string(wildcard=RosName.WILDCARD)
    # collapse multiple variable symbols
    prev = ''
    multi = RosName.WILDCARD + RosName.WILDCARD
    while name != prev:
        prev = name
        name = prev.replace(multi, RosName.WILDCARD)
    return name

def _resolve_condition(tag, scope):
    # `tag` is a Tag object from .launch_xml_parser
    # `scope` is a Scope object from .launch_scope
    t = tag.resolve_if(scope)
    if t is None: # 'if' not defined in XML
        f = tag.resolve_unless(scope)
        if f is None: # 'unless' not defined in XML
            return LOGIC_TRUE
        if f.is_resolved:
            return LOGIC_FALSE if f.value else LOGIC_TRUE
        c = UnlessCondition(f, _launch_location(scope.filepath, tag))
        return LogicVariable(f.as_string(), c)
    if t.is_resolved:
        return LOGIC_TRUE if t.value else LOGIC_FALSE
    c = IfCondition(t, _launch_location(scope.filepath, tag))
    return LogicVariable(t.as_string(), c)

def _resolve_ns_clear_params(tag, scope):
    clear = _literal(tag.resolve_clear_params(scope)) #!
    # `resolve_clear_params()` checks for `ns` if `clear` is True
    ns = tag.resolve_ns(scope)
    assert not clear or ns is not None
    ns = _rosname_string(ns)
    return (ns, clear)

def _result_to_rosname(result, scope):
    ns = scope.ns
    pns = scope.private_ns
    name = '' if result is None else result.as_string(wildcard=RosName.WILDCARD)
    return RosName.resolve(name, ns=ns, pns=pns)


###############################################################################
# Launch Interpreter
###############################################################################

_RosparamDelete = namedtuple('RosparamDelete', ('ns', 'param'))
_RosparamDelete.cmd = 'delete'

_RosparamDump = namedtuple('RosparamDump',
    ('filepath', 'ns', 'param', 'condition'))
_RosparamDump.cmd = 'dump'

class LaunchInterpreter(object):
    def __init__(self, system, include_absent=False):
        self.system = system
        self.include_absent = include_absent
        self.rosparam_cmds = []
        self.parameters = []
        self.nodes = []

    def build(self):
        for cmd in self.rosparam_cmds:
            pass # delete|dump
        for param in self.parameters:
            pass # load
        for node in self.nodes:
            pass # launch
        return

    def interpret(self, filepath, args=None):
        # filepath is a pathlib Path
        # log debug interpret(filepath, args=args)
        tree = self.system.request_parse_tree(filepath)
        assert tree.tag == 'launch'
        tree.check_schema()
        args = dict(args) if args is not None else {}
        scope = LaunchScope(filepath, self.system, args=args)
        self._interpret_tree(tree, scope)
        # parameters can only be added in the end, because of rosparam
        # TODO
        #for param in scope.parameters:
        #    self.configuration.parameters.add(param)

    def interpret_many(self, filepaths, args=None):
        # filepaths is a list of pathlib Path
        # log debug interpret_many(filepaths, args=args)
        for filepath in filepaths:
            tree = self.system.request_parse_tree(filepath)
            assert tree.tag == 'launch'
            tree.check_schema()
            args = dict(args) if args is not None else {}
            scope = LaunchScope(filepath, self.system, args=args)
            self._interpret_tree(tree, scope)
        # parameters can only be added in the end, because of rosparam
        # TODO
        #for param in scope.parameters:
        #    self.configuration.parameters.add(param)

    def _interpret_tree(self, tree, scope):
        for tag in tree.children:
            try:
                tag.check_schema()
                condition = _resolve_condition(tag, scope)
                assert condition.is_atomic
                if condition.is_false and not self.include_absent:
                    continue
                if tag.tag == 'arg':
                    self._arg_tag(tag, scope, condition)
                elif tag.tag == 'node':
                    self._node_tag(tag, scope, condition)
                elif tag.tag == 'remap':
                    self._remap_tag(tag, scope, condition)
                elif tag.tag == 'param':
                    self._param_tag(tag, scope, condition)
                elif tag.tag == 'rosparam':
                    self._rosparam_tag(tag, scope, condition)
                elif tag.tag == 'include':
                    self._include_tag(tag, scope, condition)
                elif tag.tag == 'group':
                    self._group_tag(tag, scope, condition)
                elif tag.tag == 'env':
                    self._env_tag(tag, scope, condition)
                elif tag.tag == 'machine':
                    self._machine_tag(tag, scope, condition)
                elif tag.tag == 'test':
                    self._test_tag(tag, scope, condition)
                else:
                    self._fail(tag, scope, 'unknown tag: ' + str(tag))
            except (SchemaError, SubstitutionError,
                    ValueError, ArgError, SanityError) as err:
                self._fail(tag, scope, err)
        self._make_params(scope)

    def _arg_tag(self, tag, scope, condition):
        assert not tag.children
        if condition.is_false:
            return
        if condition.is_variable:
            raise SanityError.conditional_tag(tag, condition)
        assert condition.is_true
        name = _literal(tag.resolve_name(scope))
        value = tag.resolve_value(scope)
        if value is None:
            # declare arg (with default value if available)
            # `scope.get_arg()` works as intended with `None`
            value = _literal_or_None(tag.resolve_default(scope))
            scope.declare_arg(name, default=value)
        else:
            # define arg with final value
            value = value.value if value.is_resolved else None
            scope.set_arg(name, value)

    def _node_tag(self, tag, scope, condition):
        name = _rosname_string(tag.resolve_name(scope))
        clear = _literal(tag.resolve_clear_params(scope)) #!
        if not name:
            if clear:
                raise _empty_value('name')
            exec = _literal(tag.resolve_type(scope)) #!
            name = scope.get_anonymous_name(exec)
        ns = _rosname_string(tag.resolve_ns(scope))
        new_scope = scope.new_node(name, ns, condition) #!
        if clear:
            self._clear_params(new_scope.private_ns)
        self._interpret_tree(tag, new_scope)
        self._make_node(tag, new_scope, condition)

    def _remap_tag(self, tag, scope, condition):
        assert not tag.children
        if not condition.is_false:
            source = _rosname_string(tag.resolve_from(scope))
            target = _rosname_string(tag.resolve_to(scope))
            scope.set_remap(source, target, condition)

    def _param_tag(self, tag, scope, condition):
        assert not tag.children
        name = _rosname_string(tag.resolve_name(scope))
        param_type = _literal(tag.resolve_type(scope)) #!
        if tag.is_value_param:
            value = tag.resolve_value(scope)
        elif tag.is_textfile_param:
            value = self._param_tag_textfile(tag, scope)
        elif tag.is_binfile_param:
            value = self._param_tag_binfile(tag, scope)
        else:
            assert tag.is_command_param
            value = self._param_tag_command(tag, scope)
        if value.is_resolved:
            assert isinstance(value.value, basestring)
            value = convert_value(value.value, param_type=param_type) #!
            value = ResolvedValue(value, param_type)
        location = _launch_location(scope.filepath, tag)
        scope.set_param(name, value, param_type, condition, location)

    def _param_tag_textfile(self, tag, scope):
        value = tag.resolve_textfile(scope)
        if value.is_resolved:
            try:
                # system check - if tag.textfile_attr.startswith('$(find ')
                value = self.system.read_text_file(value.value)
                value = ResolvedString(value)
            except EnvironmentError as err:
                value = UnresolvedFileContents(value.value)
        return value

    def _param_tag_binfile(self, tag, scope):
        value = tag.resolve_binfile(scope)
        if value.is_resolved:
            try:
                # system check - if tag.binfile_attr.startswith('$(find ')
                value = self.system.read_binary_file(value.value)
                value = ResolvedString(value)
            except EnvironmentError as err:
                value = UnresolvedFileContents(value.value)
        return value

    def _param_tag_command(self, tag, scope):
        value = tag.resolve_command(scope)
        if value.is_resolved:
            try:
                value = self.system.execute_command(value.value)
                value = ResolvedString(value)
            except EnvironmentError as err:
                value = UnresolvedCommandLine(value.value)
        return value

    def _rosparam_tag(self, tag, scope, condition):
        assert not tag.children
        command = _literal(tag.resolve_command(scope)) #!
        if command == 'load':
            self._rosparam_tag_load(tag, scope, condition)
        elif command == 'delete':
            self._rosparam_tag_delete(tag, scope condition)
        else:
            assert command == 'dump'
            self._rosparam_tag_dump(tag, scope, condition)

    def _rosparam_tag_load(self, tag, scope, condition):
        value = reason = None
        filepath = tag.resolve_file(scope)
        if filepath is None: # not defined in XML
            value = tag.text
        elif filepath.is_resolved:
            try:
                value = self.system.read_text_file(filepath.value)
            except EnvironmentError as err:
                reason = err
        else:
            reason = SanityError.cannot_resolve(filepath.unknown)
        if value is not None:
            assert isinstance(value, basestring)
            assert reason is None
            subst_value = _literal(tag.resolve_subst_value(scope)) #!
            if subst_value:
                value = resolve_to_yaml(value, scope) #!
                if value.is_resolved:
                    value = value.value if value.value is not None else {}
                else:
                    reason = SanityError.cannot_resolve(value.unknown)
                    value = None
            else:
                value = convert_to_yaml(value) #!
                value = value if value is not None else {}
        ns = _string_or_None(tag.resolve_ns(scope))
        param = _string_or_None(tag.resolve_param(scope))
        if value is None:
            assert reason is not None
        elif not param and type(value) != dict:
            raise SchemaError.missing_attr('param')
        scope.set_param(param, value, param_type, condition,
                        _launch_location(scope.filepath, tag),
                        reason=reason, ns=ns)

    def _rosparam_tag_delete(self, tag, scope, condition):
        if condition.is_false:
            return
        if condition.is_variable:
            raise SanityError.conditional_tag(tag, condition)
        ns = _string_or_None(tag.resolve_ns(scope))
        param = _string_or_None(tag.resolve_param(scope))
        cmd = _RosparamDelete(ns, param)
        self.rosparam_cmds.append(cmd)

    def _rosparam_tag_dump(self, tag, scope, condition):
        if condition.is_false:
            return
        ns = _string_or_None(tag.resolve_ns(scope))
        param = _string_or_None(tag.resolve_param(scope))
        filepath = _literal(tag.resolve_file(scope)) #!
        cmd = _RosparamDump(filepath, ns, param, condition)
        self.rosparam_cmds.append(cmd)

    def _include_tag(self, tag, scope, condition):
        filepath = _literal(tag.resolve_file(scope)) #!
        pass_all_args = _literal(tag.resolve_pass_all_args(scope)) #!
        ns, clear = _resolve_ns_clear_params(tag, scope) #!
        new_scope = scope.new_include(filepath, ns, condition, pass_all_args)
        if clear:
            self._clear_params(new_scope.ns)
        self._interpret_tree(tag, new_scope)
        new_scope = new_scope.new_launch()
        tree = self.system.request_parse_tree(filepath) #!
        assert tree.tag == 'launch'
        tree.check_schema() #!
        self._interpret_tree(tree, new_scope)

    def _group_tag(self, tag, scope, condition):
        ns, clear = _resolve_ns_clear_params(tag, scope) #!
        # TODO: warn if global ns
        new_scope = scope.new_group(ns, condition) # default=scope.ns
        if clear:
            self._clear_params(new_scope.ns)
        self._interpret_tree(tag, new_scope)

    def _env_tag(self, tag, scope, condition):
        assert not tag.children
        if not condition.is_false:
            name = _literal(tag.resolve_name(scope)) #!
            value = tag.resolve_value(scope)
            scope.set_env(name, value, condition)

    def _machine_tag(self, tag, scope, condition):
        assert not tag.children
        name = _literal(tag.resolve_name(scope)) #!
        address = _literal(tag.resolve_address(scope)) #!
        env_loader = _string_or_None(tag.resolve_env_loader(scope))
        ssh_port = _literal_or_None(tag.resolve_ssh_port(scope))
        user = _string_or_None(tag.resolve_user(scope))
        password = _literal_or_None(tag.resolve_password(scope))
        is_default = _literal(tag.resolve_default(scope)) #!
        timeout = _literal_or_None(tag.resolve_timeout(scope))
        scope.add_machine(name, address, ssh_port, env_loader=env_loader,
            user=user, pw=password, default=is_default, timeout=timeout)

    def _test_tag(self, tag, scope, condition):
        name = _rosname_string(tag.resolve_name(scope))
        clear = _literal(tag.resolve_clear_params(scope)) #!
        if not name:
            if clear:
                raise _empty_value('name')
            exec = _literal(tag.resolve_type(scope)) #!
            name = scope.get_anonymous_name(exec)
        ns = _rosname_string(tag.resolve_ns(scope))
        new_scope = scope.new_node(name, ns, condition) #!
        if clear:
            self._clear_params(new_scope.private_ns)
        self._interpret_tree(tag, new_scope)
        self._make_test(tag, new_scope, condition)

    def _clear_params(self, ns):
        cmd = _RosparamDelete(ns, '')
        self.rosparam_cmds.append(cmd)

    def _make_node(self, tag, scope, condition):
        name = scope.private_ns
        pkg = _literal(tag.resolve_pkg(scope)) #!
        exec = _literal(tag.resolve_type(scope)) #!
        machine = tag.resolve_machine(scope)
        required = tag.resolve_required(scope)
        respawn = tag.resolve_respawn(scope)
        if respawn.is_resolved and required.is_resolved:
            if respawn.value and required.value:
                raise SchemaError.incompatible('required', 'respawn')
        delay = tag.resolve_respawn_delay(scope)
        args = tag.resolve_args(scope)
        output = tag.resolve_output(scope)
        cwd = tag.resolve_cwd(scope)
        prefix = tag.resolve_launch_prefix(scope)
        location = _launch_location(scope.filepath, tag)
        node = RosNode(name, pkg, exec, machine=machine, required=required,
            respawn=respawn, delay=delay, args=args, output=output, cwd=cwd,
            prefix=prefix, condition=condition, location=location)
        self.nodes.append(node)
        # TODO: get remaps and environment variables from scope

    def _make_test(self, tag, scope, condition):
        name = scope.private_ns
        test_name = _literal(tag.resolve_test_name(scope)) #!
        pkg = _literal(tag.resolve_pkg(scope)) #!
        exec = _literal(tag.resolve_type(scope)) #!
        args = tag.resolve_args(scope)
        cwd = tag.resolve_cwd(scope)
        prefix = tag.resolve_launch_prefix(scope)
        retry = tag.resolve_retry(scope)
        time_limit = tag.resolve_time_limit(scope)
        location = _launch_location(scope.filepath, tag)
        test = RosTest(test_name, name, pkg, exec, args=args, cwd=cwd,
            prefix=prefix, retries=retry, time_limit=time_limit,
            condition=condition, location=location)
        self.nodes.append(test)
        # TODO: get remaps and environment variables from scope

    def _make_params(self, scope):
        pass # TODO

    def _fail(self, tag, scope, err):
        msg = str(err) or type(err).__name__
        raise LaunchInterpreterError('in {} <{}> [{}:{}]: {}'.format(
            scope.filepath, tag.tag, tag.line, tag.column, msg))
