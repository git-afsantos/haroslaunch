# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from string import printable

from hypothesis import given

from haroslaunch.launch_xml_parser import (
    LaunchParserError, parse, parse_from_file, from_JSON_object
)

###############################################################################
# Strategies
###############################################################################

NAME_CHAR = 'abcdefghijklmnopqrstuvwxyz0123456789_'

def _start_with_letter(s):
    return s[0].isalpha()

def var_names():
    return text(NAME_CHAR, min_size=1).filter(_start_with_letter)

def rl_booleans():
    return sampled_from('1', '0', 'true', 'false')

def arg_tags():
    tag = just('arg')
    inner_text = just('')
    req = {
        'name': var_names(),
    }
    opt = {
        'if': rl_booleans(),
        'unless': rl_booleans(),
        'value': text(printable),
        'default': text(printable),
        'doc': text(printable),
    }
    attributes = fixed_dictionaries(req, optional=opt)
    children = just(())
    return tuples(tag, inner_text, attributes, children)
