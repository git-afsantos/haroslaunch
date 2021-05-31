# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from __future__ import print_function
from argparse import ArgumentParser
import json
import errno
from sys import exit

from .launch_interpreter import LaunchInterpreter, LaunchInterpreterError
from .launch_xml_parser import parse_from_file
from .ros_iface import SimpleRosInterface

###############################################################################
# Workflow
###############################################################################

def workflow_parse_xml(args):
    trees = {}
    for filepath in args.launch_files:
        try:
            tree = parse_from_file(filepath)
            trees[filepath] = tree.to_JSON_object()
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise
            pass # log file not found error
    return trees

def workflow_interpret_xml(args):
    system = SimpleRosInterface()
    lfi = LaunchInterpreter(system, include_absent=True)
    for filepath in args.launch_files:
        lfi.interpret(filepath)
    return lfi.to_JSON_object()


###############################################################################
# Arguments
###############################################################################

def parse_args(argv):
    parser = ArgumentParser(prog='haroslaunch',
        description='ROS launch file parser and interpreter')
    parser.add_argument('launch_files', metavar='file', nargs='+',
        help='target ROS launch files')
    return parser.parse_args(argv)


###############################################################################
# Entry Point
###############################################################################

def main(argv=None):
    args = parse_args(argv)
    result = workflow_interpret_xml(args)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    exit(main())
