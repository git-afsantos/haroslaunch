# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from collections import namedtuple

from .launch_scope import (
    new_if, new_unless,
    ArgError, LaunchScope, NodeScope, GroupScope
)
from .launch_xml_parser import SchemaError
from .sub_parser import (
    TYPE_STRING, TYPE_YAML,
    convert_to_bool, convert_to_yaml, convert_value, new_literal_result,
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
    _UNK_TAG = 'unknown tag: {}'
    @classmethod
    def unknown_tag(cls, tag):
        return cls(cls._UNK_TAG.format(tag))

    _INVALID = '{val!r} is not a valid {attr!r} in tag: {tag}'
    @classmethod
    def invalid_value(cls, tag, attr, value):
        return cls(cls._INVALID.format(tag=tag, attr=attr, val=value))

    @classmethod
    def conditional_tag(cls, tag, unknown):
        attr = tag.conditional_statement
        assert attr is not None
        return cls.need_value(tag, attr, unknown)

    _NEED_VALUE = ('cannot resolve {attr!r} in {tag}: '
                   'unknown values for {unk}')
    @classmethod
    def need_value(cls, tag, attr, unknown):
        unknown = ', '.join(unk.text for unk in unknown)
        return cls(cls._NEED_VALUE.format(attr=attr, tag=tag, unk=unknown))

    @classmethod
    def cannot_resolve(cls, unknown):
        what = ', '.join(x.text for x in unknown)
        return cls('unable to resolve ' + what)

    _NO_EMPTY = '{attr!r} cannot be empty in {tag}'
    @classmethod
    def no_empty(cls, tag, attr):
        return cls(cls._NO_EMPTY.format(attr=attr, tag=tag))

    _MISS_ATTR = '{attr!r} is missing in {tag}'
    @classmethod
    def miss_attr(cls, tag, attr):
        return cls(cls._MISS_ATTR.format(attr=attr, tag=tag))

    _INVALID_ATTR = '{attr!r} is not a valid attribute in {tag}'
    @classmethod
    def invalid_attr(cls, tag, attr):
        return cls(cls._INVALID_ATTR.format(attr=attr, tag=tag))


def _empty_value(attr):
    return ValueError('{!r} must not be empty'.format(attr))


###############################################################################
# Helper Functions
###############################################################################

def _launch_location(filepath, tag):
    return {
        'file': str(filepath),
        'line': tag.line,
        'column': tag.column
    }

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

def _require(tag, attr):
    value = tag.attributes.get(attr)
    if value is None:
        raise SanityError.miss_attr(tag, attr)
    return value

def _resolve_condition(tag, scope):
    # `tag` is a Tag object from .launch_xml_parser
    # `scope` is a Scope object from .launch_scope
    t = tag.resolve_if(scope)
    if t is None: # 'if' not defined in XML
        f = tag.resolve_unless(scope)
        if f is None: # 'unless' not defined in XML
            return True
        if f.is_resolved:
            return not f.value
        loc = _launch_location(scope.filepath, tag)
        return new_unless(tag.unless_attr, f.unknown, location=loc)
    if t.is_resolved:
        return t.value
    loc = _launch_location(scope.filepath, tag)
    return new_if(tag.if_attr, t.unknown, location=loc)

def _resolve_strict(tag, scope, attr):
    original = tag.attributes.get(attr)
    if original is None:
        raise SanityError.miss_attr(tag, attr)
    unresolved = SubstitutionParser.of_string(original)
    value = unresolved.resolve(scope)
    if value is None:
        raise SanityError.need_value(tag, attr, unresolved.unknown)
    #if value == '':
    #    raise SanityError.no_empty(tag, attr)
    return value

#def _resolve_opt(tag, scope, attr, default=None, no_empty=False):
def _resolve_opt(tag, scope, attr, default=None, unknown=True):
    original = tag.attributes.get(attr)
        if original is None:
            return default
    unresolved = SubstitutionParser.of_string(original)
    value = unresolved.resolve(scope)
    #if no_empty and value == '':
    #    raise SanityError.no_empty(tag, attr)
    if value is None and not unknown:
        raise SanityError.need_value(tag, attr, unresolved.unknown)
    return value

def _resolve_opt_value(original_value, scope):
    unresolved = SubstitutionParser.of_string(original_value)
    value = unresolved.resolve(scope)
    if value is None:
        pass # TODO log unknown
    return value


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
            except SchemaError as err:
                self._fail(tag, scope, err)
            try:
                condition = _resolve_condition(tag, scope)
            except SubstitutionError:
                continue # TODO
            except ValueError:
                continue # TODO
            except ArgError:
                continue # TODO
            if condition is False and not self.include_absent:
                continue
            try:
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
            except SanityError as err:
                self._fail(tag, scope, err)
        # TODO at the end of the scope register new parameters

    def _arg_tag(self, tag, scope, condition):
        assert not tag.children
        if condition is False:
            return
        if condition is not True:
            raise SanityError.conditional_tag(tag, condition.unknown)
        assert condition is True
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
        name = tag.resolve_name(scope).as_string()
        # RosName.check_valid_name(name, ns=False, wildcards=True)
        clear = _literal(tag.resolve_clear_params(scope)) #!
        if clear and not name:
            raise _empty_value('name')
        ns = _string_or_None(tag.resolve_ns(scope))
        pkg = _literal(tag.resolve_pkg(scope)) #!
        exec = _literal(tag.resolve_type(scope)) #!
        machine = _string_or_None(tag.resolve_machine(scope))
        required = _literal(tag.resolve_required(scope)) #!
        respawn = _literal(tag.resolve_respawn(scope)) #!
        if respawn and required:
            raise SchemaError.incompatible('required', 'respawn')
        delay = _literal_or_None(tag.resolve_respawn_delay(scope))
        args = _literal_or_None(tag.resolve_args(scope))
        output = _literal_or_None(tag.resolve_output(scope))
        cwd = _literal_or_None(tag.resolve_cwd(scope))
        prefix = _literal_or_None(tag.resolve_launch_prefix(scope))
        new_scope = scope.new_node(name, pkg, exec, ns=ns, machine=machine,
            required=required, respawn=respawn, respawn_delay=delay, args=args,
            prefix=prefix, output=output, cwd=cwd)
        self._interpret_tree(tag, new_scope)

    def _remap_tag(self, tag, scope, condition):
        assert not tag.children
        if condition is False:
            return
        if condition is not True:
            raise SanityError.conditional_tag(tag, condition.unknown)
        source = tag.resolve_from(scope).as_string()
        target = tag.resolve_to(scope).as_string()
        scope.set_remap(source, target)

    def _param_tag(self, tag, scope, condition):
        assert not tag.children
        name = tag.resolve_name(scope).as_string()
        param_type = _literal(tag.resolve_type(scope)) #!
        value = reason = None
        if tag.is_value_param:
            result = tag.resolve_value(scope)
            if result.is_resolved:
                value = result.value
            else:
                reason = SanityError.cannot_resolve(result.unknown)
        elif tag.is_textfile_param:
            result = tag.resolve_textfile(scope)
            if result.is_resolved:
                try:
                    # system check - if tag.textfile_attr.startswith('$(find ')
                    value = self.system.read_text_file(result.value)
                except EnvironmentError as err:
                    reason = err
            else:
                reason = SanityError.cannot_resolve(result.unknown)
        elif tag.is_binfile_param:
            result = tag.resolve_binfile(scope)
            if result.is_resolved:
                try:
                    # system check - if tag.binfile_attr.startswith('$(find ')
                    value = self.system.read_binary_file(result.value)
                except EnvironmentError as err:
                    reason = err
            else:
                reason = SanityError.cannot_resolve(result.unknown)
        else:
            assert tag.is_command_param
            result = tag.resolve_command(scope)
            if result.is_resolved:
                try:
                    value = self.system.execute_command(result.value)
                except EnvironmentError as err:
                    reason = err
            else:
                reason = SanityError.cannot_resolve(result.unknown)
        assert value is None or isinstance(value, basestring)
        assert (reason is None) is (value is not None)
        if value is not None:
            value = convert_value(value, param_type=param_type) #!
        location = _launch_location(scope.filepath, tag)
        scope.set_param(name, value, param_type, condition, location,
                        reason=reason)

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
        if condition is False:
            return
        if condition is not True:
            raise SanityError.conditional_tag(tag, condition.unknown)
        ns = _string_or_None(tag.resolve_ns(scope))
        param = _string_or_None(tag.resolve_param(scope))
        cmd = _RosparamDelete(ns, param)
        self.rosparam_cmds.append(cmd)

    def _rosparam_tag_dump(self, tag, scope, condition):
        if condition is False:
            return
        ns = _string_or_None(tag.resolve_ns(scope))
        param = _string_or_None(tag.resolve_param(scope))
        filepath = _literal(tag.resolve_file(scope)) #!
        cmd = _RosparamDump(filepath, ns, param, condition)
        self.rosparam_cmds.append(cmd)

    def _include_tag(self, tag, scope, condition):
        filepath = _literal(tag.resolve_file(scope)) #!
        pass_all_args = _literal(tag.resolve_pass_all_args(scope)) #!
        clear = _literal(tag.resolve_clear_params(scope)) #!
        ns = _literal_or_None(tag.resolve_ns(scope))
        new_scope = scope.new_include(filepath, pass_all_args, ns=ns)
        self._interpret_tree(tag, new_scope)
        new_scope = new_scope.new_launch()
        tree = self.system.request_parse_tree(filepath)
        assert tree.tag == 'launch'
        tree.check_schema()
        self._interpret_tree(tree, scope)

    def _group_tag(self, tag, scope, condition):
        clear = _literal(tag.resolve_clear_params(scope))
        if clear:
            ns = _literal(tag.resolve_ns(scope))
        else:
            ns = _literal_or_None(tag.resolve_ns(scope))
        # TODO warn if global ns
        new_scope = scope.new_group(ns, clear, condition) # default=scope.ns
        self._interpret_tree(tag, new_scope)

    def _env_tag(self, tag, scope, condition):
        assert not tag.children
        if condition is False:
            return
        if condition is not True:
            raise SanityError.conditional_tag(tag, condition.unknown)
        name = _literal(tag.resolve_name(scope)) #!
        value = tag.resolve_value(scope).as_string() # allow wildcards
        scope.set_env(name, value)

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
        test_name = tag.resolve_test_name(scope).as_string()
        name = tag.resolve_name(scope).as_string()
        # RosName.check_valid_name(name, ns=False, wildcards=True)
        clear = _literal(tag.resolve_clear_params(scope)) #!
        if clear and not name:
            raise _empty_value('name')
        ns = _string_or_None(tag.resolve_ns(scope))
        pkg = _literal(tag.resolve_pkg(scope)) #!
        exec = _literal(tag.resolve_type(scope)) #!
        args = _literal_or_None(tag.resolve_args(scope))
        cwd = _literal_or_None(tag.resolve_cwd(scope))
        prefix = _literal_or_None(tag.resolve_launch_prefix(scope))
        retry = _literal_or_None(tag.resolve_retry(scope))
        time_limit = _literal_or_None(tag.resolve_time_limit(scope))
        new_scope = scope.new_test(name, pkg, exec, ns=ns, args=args,
            prefix=prefix, cwd=cwd, retry=retry, time_limit=time_limit)
        self._interpret_tree(tag, new_scope)

    def _fail(self, tag, scope, err):
        msg = str(err) or type(err).__name__
        raise LaunchInterpreterError('in {} <{}> [{}:{}]: {}'.format(
            scope.filepath, tag.tag, tag.line, tag.column, msg))
