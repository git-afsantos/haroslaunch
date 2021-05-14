# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from __future__ import print_function
import sys

sys.modules['_elementtree'] = None
import xml.etree.ElementTree as ET

from .sub_parser import (
    TYPE_BOOL, TYPE_INT, TYPE_DOUBLE, TYPE_STRING, TYPE_YAML, TYPE_AUTO,
    SubstitutionParser
)

###############################################################################
# Errors and Exceptions
###############################################################################

class LaunchParserError(Exception):
    @classmethod
    def with_xml_tag(cls, xml_tag, err):
        line = xml_tag._start_line_number
        col = xml_tag._start_column_number
        msg = str(err) or type(err).__name__
        return cls('in <{}> [{}:{}]: {}'.format(xml_tag.tag, line, col, msg))

    @classmethod
    def invalid_root(cls, tag_name):
        return cls('invalid root tag <{}>'.format(tag_name))

    @classmethod
    def unknown_tag(cls, tag):
        return cls('unknown tag {tag.tag!r}')


class SchemaError(Exception):
    @classmethod
    def missing_attr(cls, attr):
        return cls('missing required attribute {!r}'.format(attr))

    @classmethod
    def unknown_attr(cls, attr):
        return cls('unknown attribute {!r}'.format(attr))

    @classmethod
    def both_if_unless(cls):
        return cls('cannot declare both "if" and "unless" at the same time.')

    @classmethod
    def incompatible(cls, attr1, attr2):
        return cls('{!r} is incompatible with {!r}'.format(attr1, attr2))

    @classmethod
    def no_children(cls, tag_name):
        return cls('<{}> does not allow child tags'.format(tag_name))

    @classmethod
    def invalid_child(cls, child_tag_name, parent_tag_name):
        return cls('<{}> cannot be a child of <{}>'.format(
            child_tag_name, parent_tag_name))


def _invalid_value(attr, value):
    return ValueError('{!r} is not a valid value for {!r}'.format(value, attr))

def _empty_value(attr):
    return ValueError('{!r} must not be empty'.format(attr))


###############################################################################
# Launch XML Tags
###############################################################################

class BaseLaunchTag(object):
    CHILDREN = ()
    REQUIRED = ()
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL
    }
    ENUMS = {}

    def __init__(self, text, attributes, line, col):
        self.text = text or ''
        self.line = line or 1
        self.column = col or 1
        self.attributes = dict(attributes) if attributes is not None else {}
        self.children = []
        self.check_schema()

    @property
    def tag(self):
        raise NotImplementedError('subclasses must override "tag"')

    @property
    def is_conditional(self):
        return 'if' in self.attributes or 'unless' in self.attributes

    @property
    def conditional_statement(self):
        if 'if' in self.attributes:
            return 'if'
        if 'unless' in self.attributes:
            return 'unless'
        return None

    @property
    def if_attr(self):
        return self.attributes.get('if', 'true')

    @property
    def unless_attr(self):
        return self.attributes.get('unless', 'false')

    def append(self, child):
        if child.tag not in self.CHILDREN:
            raise SchemaError.invalid_child(child.tag, self.tag)
        self.children.append(child)

    def resolve_if(self, scope):
        return self._resolve_attr('if', scope)

    def resolve_unless(self, scope):
        return self._resolve_attr('unless', scope)

    def _resolve_req_attr(self, attr, scope, no_empty=False):
        # always returns a `SubstitutionResult`
        result = self._resolve_attr(attr, scope, no_empty=no_empty)
        if result is None:
            raise SchemaError.missing_attr(attr)
        return result

    def _resolve_attr(self, attr, scope, default=None, no_empty=False):
        # returns `None` if `attr` is not defined in XML
        #   and no `default` is provided
        # returns `SubstitutionResult` otherwise
        xml_value = self.attributes.get(attr, default)
        if xml_value is None:
            return None
        param_type = self.ATTRIBUTES[attr]
        unresolved = SubstitutionParser(xml_value, param_type=param_type)
        result = unresolved.resolve(scope)
        if result.is_resolved:
            value = result.value
            if no_empty and value == '':
                raise _empty_value(attr)
            enum = self.ENUMS.get(attr)
            if enum and value not in enum:
                raise _invalid_value(attr, value)
        else: # not resolved
            assert result.unknown # there must be variables
        return result

    def check_schema(self):
        self._check_base_schema()
        self._check_tag_schema()

    def _check_base_schema(self):
        attrs = self.attributes
        for key in self.REQUIRED:
            if not attrs.get(key):
                raise SchemaError.missing_attr(key)
        for key, value in attrs.items():
            if key not in self.ATTRIBUTES:
                raise SchemaError.unknown_attr(key)
        if 'if' in attrs and 'unless' in attrs:
            raise SchemaError.both_if_unless()
        if not self.CHILDREN and self.children:
            raise SchemaError.no_children(self.tag)
        for child in self.children:
            if child.tag not in self.CHILDREN:
                raise SchemaError.invalid_child(child.tag, self.tag)

    def _check_tag_schema(self):
        pass

    def to_JSON_object(self):
        return {
            'tag': self.tag,
            'text': self.text,
            'line': self.line,
            'column': self.column,
            'attributes': dict(self.attributes),
            'children': [child.to_JSON_object() for child in self.children]
        }

    def __str__(self):
        attrs = [self.tag]
        for key, value in self.attributes.items():
            attrs.append('{}={!r}'.format(key, value))
        return '<{}>'.format(' '.join(attrs))


class LaunchTag(BaseLaunchTag):
    CHILDREN = ('node', 'include', 'remap', 'param', 'rosparam',
                'group', 'arg', 'env', 'machine', 'test')
    ATTRIBUTES = {}

    @property
    def tag(self):
        return 'launch'

    @property
    def if_attr(self):
        raise AttributeError('<launch> does not have "if"')

    @property
    def unless_attr(self):
        raise AttributeError('<launch> does not have "unless"')


class ArgTag(BaseLaunchTag):
    REQUIRED = ('name',)
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'name': TYPE_STRING,
        'value': TYPE_STRING,
        'default': TYPE_STRING,
        'doc': TYPE_STRING
    }

    @property
    def tag(self):
        return 'arg'

    @property
    def name_attr(self):
        return self.attributes['name']

    @property
    def value_attr(self):
        return self.attributes.get('value')

    @property
    def default_attr(self):
        return self.attributes.get('default')

    @property
    def doc_attr(self):
        return self.attributes.get('doc')

    def resolve_name(self, scope):
        return self._resolve_req_attr('name', scope)

    def resolve_value(self, scope):
        return self._resolve_attr('value', scope)

    def resolve_default(self, scope):
        return self._resolve_attr('default', scope)

    def resolve_doc(self, scope):
        return self._resolve_attr('doc', scope)

    def _check_tag_schema(self):
        if self.value_attr is not None and self.default_attr is not None:
            raise SchemaError.incompatible('value', 'default')


class NodeTag(BaseLaunchTag):
    CHILDREN = ('remap', 'param', 'rosparam', 'env')
    REQUIRED = ('name', 'pkg', 'type')
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'pkg': TYPE_STRING,
        'type': TYPE_STRING,
        'name': TYPE_STRING,
        'args': TYPE_STRING,
        'machine': TYPE_STRING,
        'respawn': TYPE_BOOL,
        'respawn_delay': TYPE_DOUBLE,
        'required': TYPE_BOOL,
        'ns': TYPE_STRING,
        'clear_params': TYPE_BOOL,
        'output': TYPE_STRING,
        'cwd': TYPE_STRING,
        'launch-prefix': TYPE_STRING
    }
    ENUMS = {
        'output': ('screen', 'log'),
        'cwd': ('ROS_HOME', 'node')
    }

    @property
    def tag(self):
        return 'node'

    @property
    def pkg_attr(self):
        return self.attributes['pkg']

    @property
    def type_attr(self):
        return self.attributes['type']

    @property
    def name_attr(self):
        return self.attributes['name']

    @property
    def args_attr(self):
        return self.attributes.get('args')

    @property
    def machine_attr(self):
        return self.attributes.get('machine')

    @property
    def respawn_attr(self):
        return self.attributes.get('respawn', 'false')

    @property
    def respawn_delay_attr(self):
        return self.attributes.get('respawn_delay', '0.0')

    @property
    def required_attr(self):
        return self.attributes.get('required', 'false')

    @property
    def ns_attr(self):
        return self.attributes.get('ns')

    @property
    def clear_params_attr(self):
        return self.attributes.get('clear_params', 'false')

    @property
    def output_attr(self):
        return self.attributes.get('output', 'log')

    @property
    def cwd_attr(self):
        return self.attributes.get('cwd', 'ROS_HOME')

    @property
    def launch_prefix_attr(self):
        return self.attributes.get('launch-prefix')

    def resolve_pkg(self, scope):
        return self._resolve_req_attr('pkg', scope, no_empty=True)

    def resolve_type(self, scope):
        return self._resolve_req_attr('type', scope, no_empty=True)

    def resolve_name(self, scope):
        return self._resolve_req_attr('name', scope)

    def resolve_args(self, scope):
        return self._resolve_attr('args', scope)

    def resolve_machine(self, scope):
        return self._resolve_attr('machine', scope)

    def resolve_respawn(self, scope):
        return self._resolve_attr('respawn', scope, default='false')

    def resolve_respawn_delay(self, scope):
        return self._resolve_attr('respawn_delay', scope, default='0.0')

    def resolve_required(self, scope):
        return self._resolve_attr('required', scope, default='false')

    def resolve_ns(self, scope):
        return self._resolve_attr('ns', scope, no_empty=True)

    def resolve_clear_params(self, scope):
        result = self._resolve_attr('clear_params', scope, default='false')
        if result.value is True:
            if self.name_attr == '':
                raise _empty_value('name')
        return result

    def resolve_output(self, scope):
        return self._resolve_attr('output', scope, default='log')

    def resolve_cwd(self, scope):
        return self._resolve_attr('cwd', scope, default='ROS_HOME')

    def resolve_launch_prefix(self, scope):
        return self._resolve_attr('launch-prefix', scope)


class IncludeTag(BaseLaunchTag):
    CHILDREN = ('arg', 'env')
    REQUIRED = ('file',)
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'file': TYPE_STRING,
        'ns': TYPE_STRING,
        'clear_params': TYPE_BOOL,
        'pass_all_args': TYPE_BOOL
    }

    @property
    def tag(self):
        return 'include'

    @property
    def file_attr(self):
        return self.attributes['file']

    @property
    def ns_attr(self):
        return self.attributes.get('ns')

    @property
    def clear_params_attr(self):
        return self.attributes.get('clear_params', 'false')

    @property
    def pass_all_args_attr(self):
        return self.attributes.get('pass_all_args', 'false')

    def resolve_file(self, scope):
        return self._resolve_req_attr('file', scope)

    def resolve_ns(self, scope):
        return self._resolve_attr('ns', scope)

    def resolve_clear_params(self, scope):
        result = self._resolve_attr('clear_params', scope, default='false')
        if result.is_resolved and result.value:
            if self.ns_attr is None:
                raise SchemaError.missing_attr('ns')
        return result

    def resolve_pass_all_args(self, scope):
        return self._resolve_attr('pass_all_args', scope, default='false')


class RemapTag(BaseLaunchTag):
    REQUIRED = ('from', 'to')
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'from': TYPE_STRING,
        'to': TYPE_STRING
    }

    @property
    def tag(self):
        return 'remap'

    @property
    def from_attr(self):
        return self.attributes['from']

    @property
    def to_attr(self):
        return self.attributes['to']

    def resolve_from(self, scope):
        return self._resolve_req_attr('from', scope, no_empty=True)

    def resolve_to(self, scope):
        return self._resolve_req_attr('to', scope, no_empty=True)


class ParamTag(BaseLaunchTag):
    REQUIRED = ('name',)
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'name': TYPE_STRING,
        'value': TYPE_STRING,
        'type': TYPE_STRING,
        'textfile': TYPE_STRING,
        'binfile': TYPE_STRING,
        'command': TYPE_STRING
    }
    ENUMS = {
        'type': (TYPE_BOOL, TYPE_STR, TYPE_STRING, TYPE_INT,
                 TYPE_DOUBLE, TYPE_YAML, TYPE_AUTO)
    }

    @property
    def tag(self):
        return 'param'

    @property
    def name_attr(self):
        return self.attributes['name']

    @property
    def value_attr(self):
        return self.attributes.get('value')

    @property
    def type_attr(self):
        return self.attributes.get('type')

    @property
    def textfile_attr(self):
        return self.attributes.get('textfile')

    @property
    def binfile_attr(self):
        return self.attributes.get('binfile')

    @property
    def command_attr(self):
        return self.attributes.get('command')

    @property
    def is_value_param(self):
        return self.attributes.get('value') is not None

    @property
    def is_textfile_param(self):
        return self.attributes.get('textfile') is not None

    @property
    def is_binfile_param(self):
        return self.attributes.get('binfile') is not None

    @property
    def is_command_param(self):
        return self.attributes.get('command') is not None

    def resolve_name(self, scope):
        return self._resolve_req_attr('name', scope)

    def resolve_value(self, scope):
        return self._resolve_attr('value', scope)

    def resolve_type(self, scope):
        return self._resolve_attr('type', scope, default=TYPE_AUTO)

    def resolve_textfile(self, scope):
        return self._resolve_attr('textfile', scope, no_empty=True)

    def resolve_binfile(self, scope):
        return self._resolve_attr('binfile', scope, no_empty=True)

    def resolve_command(self, scope):
        return self._resolve_attr('command', scope, no_empty=True)

    def _check_tag_schema(self):
        defined = None
        for attr in ('value', 'textfile', 'binfile', 'command'):
            value = self.attributes.get(attr)
            if value is None:
                continue
            if defined:
                raise SchemaError.incompatible(attr, defined)
            defined = attr
        if not defined:
            raise SchemaError.missing_attr('value')


class RosparamTag(BaseLaunchTag):
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'command': TYPE_STRING,
        'file': TYPE_STRING,
        'param': TYPE_STRING,
        'ns': TYPE_STRING,
        'subst_value': TYPE_BOOL
    }
    ENUMS = {
        'command': ('load', 'delete', 'dump')
    }

    @property
    def tag(self):
        return 'rosparam'

    @property
    def command_attr(self):
        return self.attributes.get('command', 'load')

    @property
    def file_attr(self):
        return self.attributes.get('file')

    @property
    def param_attr(self):
        return self.attributes.get('param')

    @property
    def ns_attr(self):
        return self.attributes.get('ns')

    @property
    def subst_value_attr(self):
        return self.attributes.get('subst_value', 'false')

    def resolve_command(self, scope):
        result = self._resolve_attr('command', scope, default='load')
        if result.is_resolved:
            if result.value == 'load':
                if self.file_attr is None and not self.text:
                    raise SchemaError.missing_attr('file')
            elif result.value == 'dump':
                if self.file_attr is None:
                    raise SchemaError.missing_attr('file')
            elif result.value == 'delete':
                if self.param_attr is None:
                    raise SchemaError.missing_attr('param')
                if self.file_attr is not None:
                    raise SchemaError.incompatible('file', 'delete')
        return result

    def resolve_file(self, scope):
        return self._resolve_attr('file', scope, no_empty=True)

    def resolve_param(self, scope):
        return self._resolve_attr('param', scope)

    def resolve_ns(self, scope):
        return self._resolve_attr('ns', scope)

    def resolve_subst_value(self, scope):
        return self._resolve_attr('subst_value', scope, default='false')

    def resolve_yaml_text(self, scope):
        # returns `SubstitutionResult`
        unresolved = SubstitutionParser(self.text, param_type=TYPE_YAML)
        return unresolved.resolve(scope)

    def _check_tag_schema(self):
        if self.command_attr == 'load':
            if self.file_attr is None and not self.text:
                raise SchemaError.missing_attr('file')
        elif self.command_attr == 'dump':
            if self.file_attr is None:
                raise SchemaError.missing_attr('file')
        elif self.command_attr == 'delete':
            if self.param_attr is None:
                raise SchemaError.missing_attr('param')
            if self.file_attr is not None:
                raise SchemaError.incompatible('file', 'delete')


class GroupTag(BaseLaunchTag):
    CHILDREN = ('node', 'include', 'remap', 'param', 'rosparam',
                'group', 'arg', 'env', 'machine', 'test')
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'ns': TYPE_STRING,
        'clear_params': TYPE_BOOL
    }

    @property
    def tag(self):
        return 'group'

    @property
    def ns_attr(self):
        return self.attributes.get('ns')

    @property
    def clear_params_attr(self):
        return self.attributes.get('clear_params', 'false')

    def resolve_ns(self, scope):
        return self._resolve_attr('ns', scope)

    def resolve_clear_params(self, scope):
        result = self._resolve_attr('clear_params', scope, default='false')
        if result.is_resolved and result.value:
            if self.ns_attr is None:
                raise SchemaError.missing_attr('ns')
        return result


class EnvTag(BaseLaunchTag):
    REQUIRED = ('name', 'value')
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'name': TYPE_STRING,
        'value': TYPE_STRING
    }

    @property
    def tag(self):
        return 'env'

    @property
    def name_attr(self):
        return self.attributes['name']

    @property
    def value_attr(self):
        return self.attributes['value']

    def resolve_name(self, scope):
        return self._resolve_req_attr('name', scope, no_empty=True)

    def resolve_value(self, scope):
        return self._resolve_req_attr('value', scope)


class MachineTag(BaseLaunchTag):
    REQUIRED = ('name', 'address')
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'name': TYPE_STRING,
        'address': TYPE_STRING,
        'ssh-port': TYPE_INT,
        'env-loader': TYPE_STRING,
        'default': TYPE_BOOL,
        'user': TYPE_STRING,
        'password': TYPE_STRING,
        'timeout': TYPE_DOUBLE
    }

    @property
    def tag(self):
        return 'machine'

    @property
    def name_attr(self):
        return self.attributes['name']

    @property
    def address_attr(self):
        return self.attributes['address']

    @property
    def shh_port_attr(self):
        return self.attributes.get('ssh-port', '22')

    @property
    def env_loader_attr(self):
        return self.attributes.get('env-loader')

    @property
    def default_attr(self):
        return self.attributes.get('default', 'false')

    @property
    def user_attr(self):
        return self.attributes.get('user')

    @property
    def password_attr(self):
        return self.attributes.get('password')

    @property
    def timeout_attr(self):
        return self.attributes.get('timeout', '10.0')

    def resolve_name(self, scope):
        return self._resolve_req_attr('name', scope)

    def resolve_address(self, scope):
        return self._resolve_req_attr('address', scope)

    def resolve_ssh_port(self, scope):
        return self._resolve_attr('ssh-port', scope, default='22')

    def resolve_env_loader(self, scope):
        return self._resolve_attr('env-loader', scope)

    def resolve_default(self, scope):
        return self._resolve_attr('default', scope, default='false')

    def resolve_user(self, scope):
        return self._resolve_attr('user', scope)

    def resolve_password(self, scope):
        return self._resolve_attr('password', scope)

    def resolve_timeout(self, scope):
        result = self._resolve_attr('timeout', scope, default='10.0',
                                    no_empty=True)
        if result.is_resolved and result.value <= 0.0:
            raise _invalid_value('timeout', result.value)
        return result


class TestTag(BaseLaunchTag):
    CHILDREN = ('remap', 'param', 'rosparam', 'env')
    REQUIRED = ('test-name', 'pkg', 'type')
    ATTRIBUTES = {
        'if': TYPE_BOOL,
        'unless': TYPE_BOOL,
        'test-name': TYPE_STRING,
        'pkg': TYPE_STRING,
        'type': TYPE_STRING,
        'name': TYPE_STRING,
        'args': TYPE_STRING,
        'ns': TYPE_STRING,
        'clear_params': TYPE_BOOL,
        'cwd': TYPE_STRING,
        'launch-prefix': TYPE_STRING,
        'retry': TYPE_INT,
        'time-limit': TYPE_DOUBLE
    }
    ENUMS = {
        'cwd': ('ROS_HOME', 'node')
    }

    @property
    def tag(self):
        return 'test'

    @property
    def test_name_attr(self):
        return self.attributes['test-name']

    @property
    def pkg_attr(self):
        return self.attributes['pkg']

    @property
    def type_attr(self):
        return self.attributes['type']

    @property
    def name_attr(self):
        return self.attributes.get('name', self.test_name_attr)

    @property
    def args_attr(self):
        return self.attributes.get('args')

    @property
    def ns_attr(self):
        return self.attributes.get('ns')

    @property
    def clear_params_attr(self):
        return self.attributes.get('clear_params', 'false')

    @property
    def cwd_attr(self):
        return self.attributes.get('cwd', 'ROS_HOME')

    @property
    def launch_prefix_attr(self):
        return self.attributes.get('launch-prefix')

    @property
    def retry_attr(self):
        return self.attributes.get('retry', '0')

    @property
    def time_limit_attr(self):
        return self.attributes.get('time-limit', '60.0')

    def resolve_test_name(self, scope):
        return self._resolve_req_attr('test-name', scope)

    def resolve_pkg(self, scope):
        return self._resolve_req_attr('pkg', scope, no_empty=True)

    def resolve_type(self, scope):
        return self._resolve_req_attr('type', scope, no_empty=True)

    def resolve_name(self, scope):
        return self._resolve_attr('name', scope, default=self.test_name_attr)

    def resolve_args(self, scope):
        return self._resolve_attr('args', scope)

    def resolve_ns(self, scope):
        return self._resolve_attr('ns', scope)

    def resolve_clear_params(self, scope):
        result = self._resolve_attr('clear_params', scope, default='false')
        if result.value is True:
            if self.name_attr == '':
                raise _empty_value('name')
        return result

    def resolve_cwd(self, scope):
        return self._resolve_attr('cwd', scope, default='ROS_HOME')

    def resolve_launch_prefix(self, scope):
        return self._resolve_attr('launch-prefix', scope)

    def resolve_retry(self, scope):
        return self._resolve_attr('retry', scope, default='0')

    def resolve_time_limit(self, scope):
        result = self._resolve_attr('time-limit', scope, default='60.0')
        if result.is_resolved and result.value <= 0.0:
            raise _invalid_value('time-limit', result.value)
        return result


###############################################################################
# Launch XML Parser
###############################################################################

# courtesy of https://stackoverflow.com/a/36430270
class LineNumberingParser(ET.XMLParser):
    def _start_list(self, *args, **kwargs):
        # Here we assume the default XML parser which is expat
        # and copy its element position attributes into output Elements
        element = super(self.__class__, self)._start_list(*args, **kwargs)
        element._start_line_number = self.parser.CurrentLineNumber
        element._start_column_number = self.parser.CurrentColumnNumber + 1
        element._start_byte_index = self.parser.CurrentByteIndex
        return element

    def _start(self, *args, **kwargs):
        # Here we assume the default XML parser which is expat
        # and copy its element position attributes into output Elements
        element = super(self.__class__, self)._start(*args, **kwargs)
        element._start_line_number = self.parser.CurrentLineNumber
        element._start_column_number = self.parser.CurrentColumnNumber + 1
        element._start_byte_index = self.parser.CurrentByteIndex
        return element

    def _end(self, *args, **kwargs):
        element = super(self.__class__, self)._end(*args, **kwargs)
        element._end_line_number = self.parser.CurrentLineNumber
        element._end_column_number = self.parser.CurrentColumnNumber + 1
        element._end_byte_index = self.parser.CurrentByteIndex
        return element


TAGS = {
    'launch': LaunchTag,
    'node': NodeTag,
    'include': IncludeTag,
    'remap': RemapTag,
    'param': ParamTag,
    'rosparam': RosparamTag,
    'group': GroupTag,
    'arg': ArgTag,
    'env': EnvTag,
    'machine': MachineTag,
    'test': TestTag
}


def parse_from_file(filepath):
    with open(filepath, 'r') as fh:
        xml_code = fh.read()
    return parse(xml_code)

def parse(xml_text):
    try:
        xml_root = ET.fromstring(xml_text, parser=LineNumberingParser())
    except ET.ParseError as e:
        raise LaunchParserError(e)
    if not xml_root.tag == 'launch':
        raise LaunchParserError.invalid_root(xml_root.tag)
    return _parse_tag(xml_root)


def _parse_tag(xml_tag):
    if not xml_tag.tag in TAGS:
        raise LaunchParserError('unknown tag: <{}>'.format(xml_tag.tag))
    cls = TAGS[xml_tag.tag]
    text = xml_tag.text if xml_tag.text else ''
    if xml_tag.tag != 'rosparam':
        text = text.strip()
    try:
        element = cls(text, xml_tag.attrib,
            xml_tag._start_line_number, xml_tag._start_column_number)
    except SchemaError as err:
        raise LaunchParserError.with_xml_tag(xml_tag, err)
    for child in xml_tag:
        element.append(_parse_tag(child))
    return element


JSON_SCHEMA = {
    'tag': str,
    'text': str,
    'line': int,
    'column': int,
    'attributes': dict,
    'children': list
}

def from_JSON_object(data):
    for key, datatype in JSON_SCHEMA.items():
        if not isinstance(data[key], datatype):
            raise TypeError('"{}" expects type {}'.format(key, datatype))
    cls = TAGS[data['tag']]
    ast = cls(data['text'], data['attributes'], data['line'], data['column'])
    for subdata in data['children']:
        ast.append(from_JSON_object(subdata))
    return ast


if __name__ == '__main__':
    import json
    with open('Agrob_feup_nodered.launch', 'r') as fh:
        text = fh.read()
    ast = parse(text).to_JSON_object()
    text1 = json.dumps(ast)
    print(text1)
    ast = from_JSON_object(ast)
    ast = ast.to_JSON_object()
    text2 = json.dumps(ast)
    assert text1 == text2
