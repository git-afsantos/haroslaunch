# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from .launch_scope import (
    new_if, new_unless,
    ArgError, LaunchScope, NodeScope, GroupScope
)
from .launch_xml_parser import SchemaError
from .sub_parser import (
    convert_to_bool, convert_value,
    SubstitutionError, UnresolvedValue
)

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
    if substitution_result is None:
        return None
    if not substitution_result.is_resolved:
        raise SanityError.cannot_resolve(substitution_result.unknown)
    return substitution_result.value

def _literal_or_None(substitution_result):
    if substitution_result is None or not substitution_result.is_resolved:
        return None
    return substitution_result.value

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
    unresolved = UnresolvedValue.of_string(original)
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
    unresolved = UnresolvedValue.of_string(original)
    value = unresolved.resolve(scope)
    #if no_empty and value == '':
    #    raise SanityError.no_empty(tag, attr)
    if value is None and not unknown:
        raise SanityError.need_value(tag, attr, unresolved.unknown)
    return value

def _resolve_opt_value(original_value, scope):
    unresolved = UnresolvedValue.of_string(original_value)
    value = unresolved.resolve(scope)
    if value is None:
        pass # TODO log unknown
    return value


###############################################################################
# Launch Interpreter
###############################################################################

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
        pass

    def _remap_tag(self, tag, scope, condition):
        assert not tag.children
        if condition is False:
            return
        if condition is not True:
            raise SanityError.conditional_tag(tag, condition.unknown)
        source = _resolve_strict(tag, scope, 'from')
        target = _require(tag, 'to')
        target = _resolve_opt_value(target, scope)
        scope.set_remap(source, target)

    def _param_tag(self, tag, scope, condition):
        assert not tag.children
        name = _require(tag, 'name')
        name = _resolve_opt_value(name, scope)
        ptype = _resolve_opt(tag, scope, 'type')
        if 'value' in tag.attributes:
            value = _resolve_opt_value(tag.value, scope)
        elif 'textfile' in tag.attributes:
            value = tag.textfile
            if not value.startswith('$(find '):
                self._fail(tag, scope, 'unsafe file access: ' + value)
            value = _resolve_opt_value(value, scope)
            if value is not None:
                value = self.system.read_text_file(value)
                # `None` if unable
        elif 'binfile' in tag.attributes:
            value = tag.binfile
            if not value.startswith('$(find '):
                self._fail(tag, scope, 'unsafe file access: ' + value)
            value = _resolve_opt_value(value, scope)
            if value is not None:
                value = self.system.read_binary_file(value)
                # `None` if unable
        elif 'command' in tag.attributes:
            value = _resolve_opt_value(tag.command, scope)
            if value is not None:
                value = self.system.execute_command(value)
                # `None` if unable
        else:
            raise SanityError.miss_attr(tag, 'value')
        if value is not None:
            value = convert_value(value, param_type=ptype)
        location = _launch_location(scope.filepath, tag)
        scope.set_param(name, value, ptype, condition, location)

    def _rosparam_tag(self, tag, scope, condition):
        assert not tag.children
        command = _resolve_opt(tag, scope, 'command',
                               default='load', unknown=False)
        ns = _resolve_opt(tag, scope, 'ns', default=scope.ns)
        if command == 'load':
            filepath = _resolve_opt(tag, scope, 'file')
        elif command == 'delete':
            if 'file' in tag.attributes:
                raise SanityError.invalid_attr(tag, 'file')
        elif command == 'dump':
        else:
            raise SanityError.invalid_value(tag, 'command', value)
        # https://github.com/ros/ros_comm/blob/f5fa3a168760d62e9693f10dcb9adfffc6132d22/tools/roslaunch/src/roslaunch/loader.py#L371
        name = sub.resolve(tag.name, strict = True)
        if command == "load":
            if filepath:
                try:
                    with open(filepath) as f:
                        value = f.read()
                except IOError as e:
                    raise ConfigurationError("cannot read file: " + filepath)
            else:
                value = tag.text
                if sub.resolve(tag.substitute, strict = True):
                    value = sub.sub(value)
                    value = sub.resolve(value, strict = True)
            scope.make_rosparam(name, ns, value, condition,
                                line=tag.line, col=tag.column)
        elif command == "delete":
            scope.remove_param(name, ns, condition)

    def _include_tag(self, tag, scope, condition):
        pass

    def _group_tag(self, tag, scope, condition):
        clear = _resolve_opt(tag, scope, 'clear_params',
                             default='false', unknown=False)
        clear = convert_to_bool(clear)
        if clear:
            ns = _resolve_strict(tag, scope, 'ns')
        else:
            # ns may be None if unable to resolve
            ns = _resolve_opt(tag, scope, 'ns', default=scope.ns)
        # TODO warn if global ns
        new_scope = scope.new_group(ns, clear, condition)
        self._interpret_tree(tag, new_scope)

    def _env_tag(self, tag, scope, condition):
        assert not tag.children
        if condition is False:
            return
        if condition is not True:
            raise SanityError.conditional_tag(tag, condition.unknown)
        name = _resolve_strict(tag, scope, 'name')
        if not name:
            raise SanityError.no_empty(tag, 'name')
        value = _require(tag, 'value')
        value = _resolve_opt_value(value, scope)
        scope.set_env(name, value)

    def _machine_tag(self, tag, scope, condition):
        pass

    def _test_tag(self, tag, scope, condition):
        pass

    def _fail(self, tag, scope, err):
        msg = str(err) or type(err).__name__
        raise LaunchInterpreterError('in {} <{}> [{}:{}]: {}'.format(
            scope.filepath, tag.tag, tag.line, tag.column, msg))
