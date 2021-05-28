# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from builtins import range
from pathlib import Path

from hypothesis import given
from hypothesis.strategies import (
    builds, fixed_dictionaries, integers, just, lists, sampled_from,
    text, tuples
)

from haroslaunch.launch_xml_parser import (
    LaunchParserError, parse, parse_from_file, from_JSON_object
)

###############################################################################
# Strategies
###############################################################################

NAME_CHAR = 'abcdefghijklmnopqrstuvwxyz0123456789_'
NORMAL_CHAR = NAME_CHAR + ' ()!#$%=?+-/*.,:;'

def _start_with_letter(s):
    return s[0].isalpha()

def var_names():
    return text(NAME_CHAR, min_size=1).filter(_start_with_letter)

def rl_booleans():
    return sampled_from(('1', '0', 'true', 'false'))

def rl_doubles():
    return builds('{}.{}'.format, integers(min_value=0), integers(min_value=0))

def rl_types():
    return sampled_from(('bool', 'int', 'double', 'string', 'yaml'))


def _any_tag_attr_filter(attributes):
    return not ('if' in attributes and 'unless' in attributes)

def _arg_attr_filter(attributes):
    return (_any_tag_attr_filter(attributes)
            and not ('value' in attributes and 'default' in attributes))

def arg_tags():
    tag = just('arg')
    inner_text = just('')
    req = {'name': var_names(),}
    opt = {
        'if': rl_booleans(),
        'unless': rl_booleans(),
        'value': text(NORMAL_CHAR),
        'default': text(NORMAL_CHAR),
        'doc': text(NORMAL_CHAR),
    }
    attrs = fixed_dictionaries(req, optional=opt).filter(_arg_attr_filter)
    children = just(())
    return tuples(tag, inner_text, attrs, children)


def node_tags():
    tag = just('node')
    inner_text = just('')
    req = {
        'name': var_names(),
        'pkg': var_names(),
        'type': var_names(),
    }
    opt = {
        'if': rl_booleans(),
        'unless': rl_booleans(),
        'args': text(NORMAL_CHAR),
        'machine': var_names(),
        'respawn': rl_booleans(),
        'respawn_delay': rl_doubles(),
        'required': rl_booleans(),
        'ns': var_names(),
        'clear_params': rl_booleans(),
        'output': sampled_from(('screen', 'log')),
        'cwd': sampled_from(('ROS_HOME', 'node')),
        'launch-prefix': text(NORMAL_CHAR),
    }
    attrs = fixed_dictionaries(req, optional=opt).filter(_any_tag_attr_filter)
    children = lists(remap_tags() | param_tags() | rosparam_tags() | env_tags())
    return tuples(tag, inner_text, attrs, children)


def remap_tags():
    tag = just('remap')
    inner_text = just('')
    req = {
        'from': var_names(),
        'to': var_names(),
    }
    opt = {
        'if': rl_booleans(),
        'unless': rl_booleans(),
    }
    attrs = fixed_dictionaries(req, optional=opt).filter(_any_tag_attr_filter)
    children = just(())
    return tuples(tag, inner_text, attrs, children)


def _param_attr_filter(attributes):
    if not _any_tag_attr_filter(attributes):
        return False
    p = [key for key in ('value', 'textfile', 'binfile', 'command')
         if key in attributes]
    return len(p) == 1

def param_tags():
    tag = just('param')
    inner_text = just('')
    req = {
        'name': var_names(),
    }
    opt = {
        'if': rl_booleans(),
        'unless': rl_booleans(),
        'value': text(NORMAL_CHAR),
        'type': rl_types(),
        'textfile': text(NORMAL_CHAR),
        'binfile': text(NORMAL_CHAR),
        'command': text(NORMAL_CHAR),
    }
    attrs = fixed_dictionaries(req, optional=opt).filter(_param_attr_filter)
    children = just(())
    return tuples(tag, inner_text, attrs, children)


def _rosparam_attr_filter(attributes):
    if not _any_tag_attr_filter(attributes):
        return False
    cmd = attributes.get('command', 'load')
    if cmd == 'dump' and not 'file' in attributes:
        return False
    return (cmd != 'delete'
            or ('param' in attributes and 'file' not in attributes))

def rosparam_tags():
    tag = just('rosparam')
    inner_text = text(NORMAL_CHAR)
    req = {}
    opt = {
        'if': rl_booleans(),
        'unless': rl_booleans(),
        'param': var_names(),
        'command': sampled_from(('load', 'delete', 'dump')),
        'file': text(NORMAL_CHAR),
        'ns': var_names(),
        'subst_value': rl_booleans(),
    }
    attrs = fixed_dictionaries(req, optional=opt).filter(_rosparam_attr_filter)
    children = just(())
    return tuples(tag, inner_text, attrs, children)


def env_tags():
    tag = just('env')
    inner_text = just('')
    req = {
        'name': var_names(),
        'value': text(NORMAL_CHAR),
    }
    opt = {
        'if': rl_booleans(),
        'unless': rl_booleans(),
    }
    attrs = fixed_dictionaries(req, optional=opt).filter(_any_tag_attr_filter)
    children = just(())
    return tuples(tag, inner_text, attrs, children)


def launch_tags():
    tag = just('launch')
    inner_text = just('')
    attributes = just({})
    children = lists(arg_tags())
    return tuples(tag, inner_text, attributes, children)


def launch_files():
    return builds(_tag_to_xml, launch_tags())


###############################################################################
# XML Printer
###############################################################################

def _tag_to_xml(data):
    tag, inner_text, attributes, children = data
    ss = [tag]
    ss.extend('{}="{}"'.format(k, v) for k, v in attributes.items())
    ss = ' '.join(ss)
    if not children and not inner_text:
        return '<{} />'.format(ss)
    si = [inner_text] if inner_text else []
    si.extend(_tag_to_xml(child) for child in children)
    si = '\n'.join(si)
    return '<{}>\n{}\n</{}>'.format(ss, si, tag)


###############################################################################
# Test Invalid Launch XML
###############################################################################

def test_malformed_xml():
    try:
        parse('<launch><arg name="a" />')
        assert False, '<launch> is not closed'
    except LaunchParserError:
        pass

def test_no_launch_root():
    try:
        parse('<arg name="a" value="1" />')
        assert False, 'no <launch> at root'
    except LaunchParserError:
        pass

def test_unknown_tag():
    try:
        parse('<launch><dummy><arg name="a"/></dummy></launch>')
        assert False, '<dummy> tag should not be accepted'
    except LaunchParserError:
        pass

# TODO: tests for SchemaError wrapped in LaunchParserError

def test_json_missing_key():
    try:
        ast = from_JSON_object({})
        assert False, 'missing schema keys'
    except KeyError:
        pass

def test_json_bad_value_type():
    try:
        ast = from_JSON_object({
            'tag': 'launch',
            'text': '',
            'line': '1',
            'column': '1',
            'attributes': {},
            'children': []
        })
        assert False, 'line and column should be int'
    except TypeError:
        pass

def test_json_unknown_tag():
    try:
        ast = from_JSON_object({
            'tag': 'dummy',
            'text': '',
            'line': 1,
            'column': 1,
            'attributes': {},
            'children': []
        })
        assert False, 'unknown <dummy> tag'
    except KeyError:
        pass


###############################################################################
# Test Valid Launch XML
###############################################################################

def _test_valid_ast(ast):
    assert ast.tag == 'launch'
    assert not ast.text
    assert not ast.attributes
    assert ast.line >= 1 and ast.column >= 1
    # --------------------------------------
    json_ast = ast.to_JSON_object()
    assert json_ast['tag'] == 'launch'
    assert not json_ast['text']
    assert not json_ast['attributes']
    assert json_ast['line'] >= 1 and json_ast['column'] >= 1
    assert len(json_ast['children']) == len(ast.children)
    assert all(json_ast['children'][i]['tag'] == ast.children[i].tag
               for i in range(len(ast.children)))
    # --------------------------------------
    other = from_JSON_object(json_ast)
    assert ast == other

@given(launch_files())
def test_parse_valid_xml(xml_code):
    ast = parse(xml_code)
    _test_valid_ast(ast)

def test_parse_all_files():
    launch = Path(__file__).parent.parent / 'launch'
    for child in launch.iterdir():
        if child.is_file():
            fp = str(child)
            if fp.endswith('.launch'):
                ast = parse_from_file(fp)
                _test_valid_ast(ast)
