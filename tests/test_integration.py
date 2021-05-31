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
        try:
            return filepath.read_text()
        except AttributeError: # Python 2
            with open(str(filepath), 'r') as fh:
                data = fh.read()
            return data

    def read_binary_file(self, filepath):
        if isinstance(filepath, STRING_TYPES):
            filepath = Path(filepath)
        assert isinstance(filepath, Path)
        safe_dir = Path(__file__).parent
        if not safe_dir in filepath.parents:
            raise ValueError(filepath)
        try:
            return Binary(filepath.read_bytes()).data
        except AttributeError: # Python 2
            with open(str(filepath), 'rb') as fh:
                data = fh.read()
            return Binary(data).data

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
    assert len(lfi.nodes) == 3
    assert len(lfi.parameters) > 0
    # Node 0 -------------------------------
    node = lfi.nodes[0]
    assert not node.is_test_node
    assert node.name.own == 'mobile_base_nodelet_manager'
    assert node.name.full == '/mobile_base_nodelet_manager'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_minimal.launch')
    assert node.traceability.line == 4
    assert node.traceability.column == 3
    assert node.package == 'nodelet'
    assert node.executable == 'nodelet'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == 'manager'
    assert node.output.value == 'log'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 0
    assert len(node.environment) == 0
    # Node 1 -------------------------------
    node = lfi.nodes[1]
    assert not node.is_test_node
    assert node.name.own == 'mobile_base'
    assert node.name.full == '/mobile_base'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_minimal.launch')
    assert node.traceability.line == 5
    assert node.traceability.column == 3
    assert node.package == 'nodelet'
    assert node.executable == 'nodelet'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == 'load kobuki_node/KobukiNodelet mobile_base_nodelet_manager'
    assert node.output.value == 'log'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 2
    assert node.remaps['/mobile_base/odom'].get_value() == '/odom'
    assert node.remaps['/mobile_base/joint_states'].get_value() == '/joint_states'
    assert len(node.environment) == 0
    # Node 2 -------------------------------
    node = lfi.nodes[2]
    assert not node.is_test_node
    assert node.name.own == 'diagnostic_aggregator'
    assert node.name.full == '/diagnostic_aggregator'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_minimal.launch')
    assert node.traceability.line == 12
    assert node.traceability.column == 3
    assert node.package == 'diagnostic_aggregator'
    assert node.executable == 'aggregator_node'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == ''
    assert node.output.value == 'log'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 0
    assert len(node.environment) == 0
    # Parameters ---------------------------
    params = {
        '/mobile_base/device_port': '/dev/kobuki',
        '/mobile_base/wheel_left_joint_name': 'wheel_left_joint',
        '/mobile_base/wheel_right_joint_name': 'wheel_right_joint',
        '/mobile_base/battery_capacity': 16.5,
        '/mobile_base/battery_low': 14.0,
        '/mobile_base/battery_dangerous': 13.2,
        '/mobile_base/cmd_vel_timeout': 0.6,
        '/mobile_base/publish_tf': True,
        '/mobile_base/use_imu_heading': True,
        '/mobile_base/odom_frame': 'odom',
        '/mobile_base/base_frame': 'base_footprint',
    }
    for p in lfi.parameters:
        assert p.namespace == '/mobile_base'
        assert p.system is None
        assert p.condition.is_true
        assert p.traceability.filepath.endswith('/kobuki_minimal.launch')
        assert p.traceability.line == 6 or (p.traceability.line == 7
            and p.name.full == '/mobile_base/publish_tf')
        assert p.traceability.column == 5
        assert p.value.value == params[p.name.full]


def test_kobuki_safe_keyop():
    fp = Path(__file__).parent / 'launch' / 'kobuki_safe_keyop.launch'
    system = MockSystem()
    lfi = LaunchInterpreter(system, include_absent=True)
    lfi.interpret(fp)
    assert not lfi.machines
    assert not lfi.rosparam_cmds
    assert len(lfi.nodes) > 0
    assert len(lfi.parameters) > 0


def test_kobuki_minimal_safe_keyop():
    fp = Path(__file__).parent / 'launch' / 'kobuki_minimal.launch'
    system = MockSystem()
    lfi = LaunchInterpreter(system, include_absent=True)
    lfi.interpret(fp)
    fp = Path(__file__).parent / 'launch' / 'kobuki_safe_keyop.launch'
    lfi.interpret(fp)
    assert not lfi.machines
    assert not lfi.rosparam_cmds
    assert len(lfi.nodes) > 0
    assert len(lfi.parameters) > 0
