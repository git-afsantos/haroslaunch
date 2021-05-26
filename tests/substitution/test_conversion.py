# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from string import printable

from hypothesis import given
from hypothesis.strategies import (
    booleans, dictionaries, floats, integers, lists, none, one_of, recursive,
    text
)

from haroslaunch.sub_parser import (
    convert_value, convert_to_bool, convert_to_int, convert_to_double,
    convert_to_yaml
)

if not hasattr(__builtins__, 'basestring'):
    basestring = (str, bytes)

###############################################################################
# Strategies
###############################################################################

json_literals = one_of(booleans(), floats(), text(printable))

json = recursive(
    (none() | booleans() | floats() | text(printable)),
    (lambda children: lists(children, 1)
        | dictionaries(text(printable), children, min_size=1))
)

###############################################################################
# convert_to_bool
###############################################################################

@given(booleans())
def test_convert_bool_to_bool(b):
    assert convert_to_bool(str(b)) is b

@given(text(printable))
def test_convert_text_to_bool(s):
    s = s.lower().strip()
    is_bool = s in ('true', 'false', '1', '0')
    try:
        convert_to_bool(s)
        assert is_bool
    except ValueError:
        assert not is_bool

###############################################################################
# convert_to_int
###############################################################################

@given(integers())
def test_convert_int_to_int(i):
    assert convert_to_int(str(i)) == i

@given(text(printable))
def test_convert_text_to_int(s):
    try:
        int(s)
        is_int = True
    except ValueError:
        is_int = False
    try:
        convert_to_int(s)
        assert is_int
    except ValueError:
        assert not is_int

###############################################################################
# convert_to_double
###############################################################################

@given(floats())
def test_convert_float_to_double(f):
    assert convert_to_double(str(f)) == f

@given(text(printable))
def test_convert_text_to_double(s):
    try:
        float(s)
        is_float = True
    except ValueError:
        is_float = False
    try:
        convert_to_double(s)
        assert is_float
    except ValueError:
        assert not is_float

###############################################################################
# convert_to_yaml
###############################################################################

@given(json)
def test_convert_json_to_yaml(data):
    assert convert_to_yaml(str(data)) == data

###############################################################################
# convert_value
###############################################################################

@given(json_literals)
def test_convert_literal_to_value(v):
    s = v if isinstance(v, basestring) else repr(v)
    assert convert_value(s) == v
