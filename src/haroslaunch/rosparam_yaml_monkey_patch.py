# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

import base64
import math
import re

try:
    from xmlrpc.client import Binary
except ImportError:
    from xmlrpclib import Binary

import yaml

###############################################################################
# Constants
###############################################################################

TAG_YAML_BINARY = u'tag:yaml.org,2002:binary'
YAML_RAD = u'!radians'
YAML_DEG = u'!degrees'

RAD_START = 'rad('
DEG_START = 'deg('

RAD_PATTERN = re.compile(r'^rad\([^\)]*\)$')
DEG_PATTERN = re.compile(r'^deg\([^\)]*\)$')

###############################################################################
# Errors and Exceptions
###############################################################################

class RosParamException(Exception):
    pass

###############################################################################
# YAML Binary Data
###############################################################################

def represent_xml_binary(loader, data):
    data = base64.b64encode(data.data)
    return loader.represent_scalar(TAG_YAML_BINARY, data, style='|')

def construct_yaml_binary(loader, node):
    return Binary(loader.construct_yaml_binary(node))

###############################################################################
# YAML Angle Data
###############################################################################

# python-yaml utility for converting rad(num) into float value
def construct_angle_radians(loader, node):
    value = loader.construct_scalar(node).strip()
    exprvalue = value.replace('pi', 'math.pi')
    if exprvalue.startswith(RAD_START):
        exprvalue = exprvalue[4:-1]
    try:
        return float(eval(exprvalue))
    except SyntaxError as e:
        raise RosParamException('invalid radian expression: ' + str(value))

# python-yaml utility for converting deg(num) into float value
def construct_angle_degrees(loader, node):
    value = loader.construct_scalar(node)
    exprvalue = value
    if exprvalue.startswith(DEG_START):
        exprvalue = exprvalue.strip()[4:-1]
    try:
        return float(exprvalue) * math.pi / 180.0
    except ValueError:
        raise RosParamException('invalid degree value: ' + str(value))

###############################################################################
# Monkey Patch
###############################################################################

# binary data
yaml.add_representer(Binary, represent_xml_binary)
yaml.add_constructor(TAG_YAML_BINARY, construct_yaml_binary)
yaml.SafeLoader.add_constructor(TAG_YAML_BINARY, construct_yaml_binary)

# radians (allow !radians 2*pi)
yaml.add_constructor(YAML_RAD, construct_angle_radians)
yaml.SafeLoader.add_constructor(YAML_RAD, construct_angle_radians)
yaml.add_implicit_resolver(YAML_RAD, RAD_PATTERN, first=RAD_START)
yaml.SafeLoader.add_implicit_resolver(YAML_RAD, RAD_PATTERN, first=RAD_START)

# degrees (allow !degrees 180)
yaml.add_constructor(YAML_DEG, construct_angle_degrees)
yaml.SafeLoader.add_constructor(YAML_DEG, construct_angle_degrees)
yaml.add_implicit_resolver(YAML_DEG, DEG_PATTERN, first=DEG_START)
yaml.SafeLoader.add_implicit_resolver(YAML_DEG, DEG_PATTERN, first=DEG_START)
