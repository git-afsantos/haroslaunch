# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from errno import EACCES
from pathlib import Path
try:
    from xmlrpc.client import Binary
except ImportError:
    from xmlrpclib import Binary

from haroslaunch.data_structs import STRING_TYPES
from haroslaunch.launch_interpreter import LaunchInterpreter
from haroslaunch.launch_xml_parser import parse_from_file

###############################################################################
# Mock System
###############################################################################

class MockSystem(object):
    def __init__(self):
        self.ast_cache = {}
        self.env = {}

    @property
    def ros_distro(self):
        return 'melodic'

    def get_environment_variable(self, name):
        return self.env.get(name)

    def get_package_path(self, name):
        return Path(__file__).parent

    def request_parse_tree(self, filepath):
        if isinstance(filepath, STRING_TYPES):
            filepath = Path(filepath)
        assert isinstance(filepath, Path)
        launch = Path(__file__).parent / 'launch'
        if filepath.parent != launch:
            raise ValueError(filepath)
        ast = self.ast_cache.get(filepath)
        if ast is None:
            ast = parse_from_file(filepath) #!
            self.ast_cache[filepath] = ast
        return ast

    def read_text_file(self, filepath):
        if isinstance(filepath, STRING_TYPES):
            filepath = Path(filepath)
        assert isinstance(filepath, Path)
        safe_dir = Path(__file__).parent
        if not safe_dir in filepath.parents:
            raise ValueError(filepath)
        return filepath.read_text()

    def read_binary_file(self, filepath):
        if isinstance(filepath, STRING_TYPES):
            filepath = Path(filepath)
        assert isinstance(filepath, Path)
        safe_dir = Path(__file__).parent
        if not safe_dir in filepath.parents:
            raise ValueError(filepath)
        return Binary(filepath.read_bytes()).data

    def execute_command(self, cmd):
        raise EnvironmentError(EACCES, cmd)


###############################################################################
# Test Kobuki Minimal
###############################################################################

def test_kobuki_minimal():
    fp = Path(__file__).parent / 'launch' / 'kobuki_minimal.launch'
    system = MockSystem()
    lfi = LaunchInterpreter(system, include_absent=True)
    lfi.interpret(fp)
    assert not lfi.machines
    assert not lfi.rosparam_cmds
    assert len(lfi.nodes) > 0
    assert len(lfi.parameters) > 0
