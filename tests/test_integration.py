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
# Mock ROS Interface
###############################################################################

class MockInterface(object):
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
    iface = MockInterface()
    lfi = LaunchInterpreter(iface, include_absent=True)
    lfi.interpret(fp)
    assert not lfi.machines
    assert not lfi.rosparam_cmds
    assert len(lfi.nodes) == 3
    assert len(lfi.parameters) == 34
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
        '/diagnostic_aggregator/pub_rate': 1.0,
        '/diagnostic_aggregator/base_path': '',
        '/diagnostic_aggregator/analyzers/power/type': 'diagnostic_aggregator/GenericAnalyzer',
        '/diagnostic_aggregator/analyzers/power/path': 'Power System',
        '/diagnostic_aggregator/analyzers/power/timeout': 5.0,
        '/diagnostic_aggregator/analyzers/power/contains': ['Battery'],
        '/diagnostic_aggregator/analyzers/power/remove_prefix': 'mobile_base_nodelet_manager',
        '/diagnostic_aggregator/analyzers/kobuki/type': 'diagnostic_aggregator/GenericAnalyzer',
        '/diagnostic_aggregator/analyzers/kobuki/path': 'Kobuki',
        '/diagnostic_aggregator/analyzers/kobuki/timeout': 5.0,
        '/diagnostic_aggregator/analyzers/kobuki/contains': ['Watchdog', 'Motor State'],
        '/diagnostic_aggregator/analyzers/kobuki/remove_prefix': 'mobile_base_nodelet_manager',
        '/diagnostic_aggregator/analyzers/sensors/type': 'diagnostic_aggregator/GenericAnalyzer',
        '/diagnostic_aggregator/analyzers/sensors/path': 'Sensors',
        '/diagnostic_aggregator/analyzers/sensors/timeout': 5.0,
        '/diagnostic_aggregator/analyzers/sensors/contains': ['Cliff Sensor',
            'Wall Sensor', 'Wheel Drop', 'Motor Current', 'Gyro Sensor'],
        '/diagnostic_aggregator/analyzers/sensors/remove_prefix': 'mobile_base_nodelet_manager',
        '/diagnostic_aggregator/analyzers/input_ports/type': 'diagnostic_aggregator/GenericAnalyzer',
        '/diagnostic_aggregator/analyzers/input_ports/path': 'Input Ports',
        '/diagnostic_aggregator/analyzers/input_ports/timeout': 5.0,
        '/diagnostic_aggregator/analyzers/input_ports/contains': ['Digital Input', 'Analog Input'],
        '/diagnostic_aggregator/analyzers/input_ports/remove_prefix': 'mobile_base_nodelet_manager',
    }
    for p in lfi.parameters:
        assert p.namespace.full.startswith(('/mobile_base', '/diagnostic_aggregator'))
        assert p.system is None
        assert p.condition.is_true
        assert p.traceability.filepath.endswith('/kobuki_minimal.launch')
        assert p.traceability.line in (6, 7, 13)
        assert p.traceability.column == 5
        assert p.value.value == params[p.name.full]


###############################################################################
# Test Kobuki Safe Teleoperation
###############################################################################

def test_kobuki_safe_keyop():
    fp = Path(__file__).parent / 'launch' / 'kobuki_safe_keyop.launch'
    iface = MockInterface()
    lfi = LaunchInterpreter(iface, include_absent=True)
    lfi.interpret(fp)
    assert not lfi.machines
    assert not lfi.rosparam_cmds
    assert len(lfi.nodes) == 4
    assert len(lfi.parameters) == 12
    # Node 0 -------------------------------
    node = lfi.nodes[0]
    assert not node.is_test_node
    assert node.name.own == 'cmd_vel_mux'
    assert node.name.full == '/cmd_vel_mux'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_safe_keyop.launch')
    assert node.traceability.line == 5
    assert node.traceability.column == 3
    assert node.package == 'nodelet'
    assert node.executable == 'nodelet'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == 'load yocs_cmd_vel_mux/CmdVelMuxNodelet mobile_base_nodelet_manager'
    assert node.output.value == 'log'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 1
    assert node.remaps['/cmd_vel_mux/output'].get_value() == '/mobile_base/commands/velocity'
    assert len(node.environment) == 0
    # Node 1 -------------------------------
    node = lfi.nodes[1]
    assert not node.is_test_node
    assert node.name.own == 'kobuki_safety_controller'
    assert node.name.full == '/kobuki_safety_controller'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_safe_keyop.launch')
    assert node.traceability.line == 10
    assert node.traceability.column == 3
    assert node.package == 'nodelet'
    assert node.executable == 'nodelet'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == 'load kobuki_safety_controller/SafetyControllerNodelet mobile_base_nodelet_manager'
    assert node.output.value == 'log'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 4
    assert node.remaps['/kobuki_safety_controller/cmd_vel'].get_value() == '/cmd_vel_mux/safety_controller'
    assert node.remaps['/kobuki_safety_controller/events/bumper'].get_value() == '/mobile_base/events/bumper'
    assert node.remaps['/kobuki_safety_controller/events/cliff'].get_value() == '/mobile_base/events/cliff'
    assert node.remaps['/kobuki_safety_controller/events/wheel_drop'].get_value() == '/mobile_base/events/wheel_drop'
    assert len(node.environment) == 0
    # Node 2 -------------------------------
    node = lfi.nodes[2]
    assert not node.is_test_node
    assert node.name.own == 'keyop_vel_smoother'
    assert node.name.full == '/keyop_vel_smoother'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_safe_keyop.launch')
    assert node.traceability.line == 17
    assert node.traceability.column == 3
    assert node.package == 'nodelet'
    assert node.executable == 'nodelet'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == 'load yocs_velocity_smoother/VelocitySmootherNodelet mobile_base_nodelet_manager'
    assert node.output.value == 'log'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 3
    assert node.remaps['/keyop_vel_smoother/smooth_cmd_vel'].get_value() == '/cmd_vel_mux/keyboard_teleop'
    assert node.remaps['/keyop_vel_smoother/odometry'].get_value() == '/odom'
    assert node.remaps['/keyop_vel_smoother/robot_cmd_vel'].get_value() == '/mobile_base/commands/velocity'
    assert len(node.environment) == 0
    # Node 3 -------------------------------
    node = lfi.nodes[3]
    assert not node.is_test_node
    assert node.name.own == 'keyop'
    assert node.name.full == '/keyop'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_safe_keyop.launch')
    assert node.traceability.line == 26
    assert node.traceability.column == 3
    assert node.package == 'kobuki_keyop'
    assert node.executable == 'keyop'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == ''
    assert node.output.value == 'screen'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 2
    assert node.remaps['/keyop/motor_power'].get_value() == '/mobile_base/commands/motor_power'
    assert node.remaps['/keyop/cmd_vel'].get_value() == '/keyop_vel_smoother/raw_cmd_vel'
    assert len(node.environment) == 0
    # Parameters ---------------------------
    params = {
        '/cmd_vel_mux/yaml_cfg_file': str(Path(__file__).parent / 'param' / 'keyop_mux.yaml'),
        '/keyop_vel_smoother/speed_lim_v': 0.8,
        '/keyop_vel_smoother/speed_lim_w': 5.4,
        '/keyop_vel_smoother/accel_lim_v': 1.0,
        '/keyop_vel_smoother/accel_lim_w': 7.0,
        '/keyop_vel_smoother/frequency': 20.0,
        '/keyop_vel_smoother/decel_factor': 1.0,
        '/keyop/linear_vel_step': 0.05,
        '/keyop/linear_vel_max': 1.5,
        '/keyop/angular_vel_step': 0.33,
        '/keyop/angular_vel_max': 6.6,
        '/keyop/wait_for_connection_': True,
    }
    for p in lfi.parameters:
        assert p.namespace.full.startswith(('/cmd_vel_mux', '/keyop'))
        assert p.system is None
        assert p.condition.is_true
        assert p.traceability.filepath.endswith('/kobuki_safe_keyop.launch')
        assert p.traceability.line in (6, 18, 29, 30, 31, 32, 33)
        assert p.traceability.column == 5
        assert p.value.value == params[p.name.full]


###############################################################################
# Test Kobuki Safe Teleoperation (Full)
###############################################################################

def test_kobuki_minimal_safe_keyop():
    fp = Path(__file__).parent / 'launch' / 'kobuki_minimal.launch'
    iface = MockInterface()
    lfi = LaunchInterpreter(iface, include_absent=True)
    lfi.interpret(fp)
    fp = Path(__file__).parent / 'launch' / 'kobuki_safe_keyop.launch'
    lfi.interpret(fp)
    assert not lfi.machines
    assert not lfi.rosparam_cmds
    assert len(lfi.nodes) == 7
    assert len(lfi.parameters) == 46
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
    # Node 3 -------------------------------
    node = lfi.nodes[3]
    assert not node.is_test_node
    assert node.name.own == 'cmd_vel_mux'
    assert node.name.full == '/cmd_vel_mux'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_safe_keyop.launch')
    assert node.traceability.line == 5
    assert node.traceability.column == 3
    assert node.package == 'nodelet'
    assert node.executable == 'nodelet'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == 'load yocs_cmd_vel_mux/CmdVelMuxNodelet mobile_base_nodelet_manager'
    assert node.output.value == 'log'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 1
    assert node.remaps['/cmd_vel_mux/output'].get_value() == '/mobile_base/commands/velocity'
    assert len(node.environment) == 0
    # Node 4 -------------------------------
    node = lfi.nodes[4]
    assert not node.is_test_node
    assert node.name.own == 'kobuki_safety_controller'
    assert node.name.full == '/kobuki_safety_controller'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_safe_keyop.launch')
    assert node.traceability.line == 10
    assert node.traceability.column == 3
    assert node.package == 'nodelet'
    assert node.executable == 'nodelet'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == 'load kobuki_safety_controller/SafetyControllerNodelet mobile_base_nodelet_manager'
    assert node.output.value == 'log'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 4
    assert node.remaps['/kobuki_safety_controller/cmd_vel'].get_value() == '/cmd_vel_mux/safety_controller'
    assert node.remaps['/kobuki_safety_controller/events/bumper'].get_value() == '/mobile_base/events/bumper'
    assert node.remaps['/kobuki_safety_controller/events/cliff'].get_value() == '/mobile_base/events/cliff'
    assert node.remaps['/kobuki_safety_controller/events/wheel_drop'].get_value() == '/mobile_base/events/wheel_drop'
    assert len(node.environment) == 0
    # Node 5 -------------------------------
    node = lfi.nodes[5]
    assert not node.is_test_node
    assert node.name.own == 'keyop_vel_smoother'
    assert node.name.full == '/keyop_vel_smoother'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_safe_keyop.launch')
    assert node.traceability.line == 17
    assert node.traceability.column == 3
    assert node.package == 'nodelet'
    assert node.executable == 'nodelet'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == 'load yocs_velocity_smoother/VelocitySmootherNodelet mobile_base_nodelet_manager'
    assert node.output.value == 'log'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 3
    assert node.remaps['/keyop_vel_smoother/smooth_cmd_vel'].get_value() == '/cmd_vel_mux/keyboard_teleop'
    assert node.remaps['/keyop_vel_smoother/odometry'].get_value() == '/odom'
    assert node.remaps['/keyop_vel_smoother/robot_cmd_vel'].get_value() == '/mobile_base/commands/velocity'
    assert len(node.environment) == 0
    # Node 6 -------------------------------
    node = lfi.nodes[6]
    assert not node.is_test_node
    assert node.name.own == 'keyop'
    assert node.name.full == '/keyop'
    assert node.system is None
    assert node.condition.is_true
    assert node.traceability.filepath.endswith('/kobuki_safe_keyop.launch')
    assert node.traceability.line == 26
    assert node.traceability.column == 3
    assert node.package == 'kobuki_keyop'
    assert node.executable == 'keyop'
    assert node.machine is None
    assert node.is_required.value is False
    assert node.respawns.value is False
    assert node.respawn_delay.value == 0.0
    assert node.args.value == ''
    assert node.output.value == 'screen'
    assert node.working_dir.value == 'ROS_HOME'
    assert node.launch_prefix is None
    assert len(node.remaps) == 2
    assert node.remaps['/keyop/motor_power'].get_value() == '/mobile_base/commands/motor_power'
    assert node.remaps['/keyop/cmd_vel'].get_value() == '/keyop_vel_smoother/raw_cmd_vel'
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
        '/diagnostic_aggregator/pub_rate': 1.0,
        '/diagnostic_aggregator/base_path': '',
        '/diagnostic_aggregator/analyzers/power/type': 'diagnostic_aggregator/GenericAnalyzer',
        '/diagnostic_aggregator/analyzers/power/path': 'Power System',
        '/diagnostic_aggregator/analyzers/power/timeout': 5.0,
        '/diagnostic_aggregator/analyzers/power/contains': ['Battery'],
        '/diagnostic_aggregator/analyzers/power/remove_prefix': 'mobile_base_nodelet_manager',
        '/diagnostic_aggregator/analyzers/kobuki/type': 'diagnostic_aggregator/GenericAnalyzer',
        '/diagnostic_aggregator/analyzers/kobuki/path': 'Kobuki',
        '/diagnostic_aggregator/analyzers/kobuki/timeout': 5.0,
        '/diagnostic_aggregator/analyzers/kobuki/contains': ['Watchdog', 'Motor State'],
        '/diagnostic_aggregator/analyzers/kobuki/remove_prefix': 'mobile_base_nodelet_manager',
        '/diagnostic_aggregator/analyzers/sensors/type': 'diagnostic_aggregator/GenericAnalyzer',
        '/diagnostic_aggregator/analyzers/sensors/path': 'Sensors',
        '/diagnostic_aggregator/analyzers/sensors/timeout': 5.0,
        '/diagnostic_aggregator/analyzers/sensors/contains': ['Cliff Sensor',
            'Wall Sensor', 'Wheel Drop', 'Motor Current', 'Gyro Sensor'],
        '/diagnostic_aggregator/analyzers/sensors/remove_prefix': 'mobile_base_nodelet_manager',
        '/diagnostic_aggregator/analyzers/input_ports/type': 'diagnostic_aggregator/GenericAnalyzer',
        '/diagnostic_aggregator/analyzers/input_ports/path': 'Input Ports',
        '/diagnostic_aggregator/analyzers/input_ports/timeout': 5.0,
        '/diagnostic_aggregator/analyzers/input_ports/contains': ['Digital Input', 'Analog Input'],
        '/diagnostic_aggregator/analyzers/input_ports/remove_prefix': 'mobile_base_nodelet_manager',

        '/cmd_vel_mux/yaml_cfg_file': str(Path(__file__).parent / 'param' / 'keyop_mux.yaml'),
        '/keyop_vel_smoother/speed_lim_v': 0.8,
        '/keyop_vel_smoother/speed_lim_w': 5.4,
        '/keyop_vel_smoother/accel_lim_v': 1.0,
        '/keyop_vel_smoother/accel_lim_w': 7.0,
        '/keyop_vel_smoother/frequency': 20.0,
        '/keyop_vel_smoother/decel_factor': 1.0,
        '/keyop/linear_vel_step': 0.05,
        '/keyop/linear_vel_max': 1.5,
        '/keyop/angular_vel_step': 0.33,
        '/keyop/angular_vel_max': 6.6,
        '/keyop/wait_for_connection_': True,
    }
    for p in lfi.parameters:
        assert p.namespace.full.startswith(('/mobile_base', '/cmd_vel_mux',
            '/keyop', '/diagnostic_aggregator'))
        assert p.system is None
        assert p.condition.is_true
        assert p.traceability.filepath.endswith(('/kobuki_minimal.launch',
            '/kobuki_safe_keyop.launch'))
        assert p.traceability.line in (6, 7, 13, 18, 29, 30, 31, 32, 33)
        assert p.traceability.column == 5
        assert p.value.value == params[p.name.full]
