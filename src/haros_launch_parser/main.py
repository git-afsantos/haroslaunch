# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Imports
###############################################################################

from argparse import ArgumentParser
import errno
from sys import exit

import .launch_xml_parser as LaunchXmlParser

###############################################################################
# Workflow
###############################################################################

def workflow_parse_xml(args):
    trees = {}
    for filepath in args.launch_files:
        tree = _parse_launch_xml_from_file(filepath)
        trees[filepath] = tree.to_JSON_object()
    return trees

def workflow_interpret_xml(args):
    pass


###############################################################################
# Helper Functions
###############################################################################

def _parse_launch_xml_from_file(filepath):
    try:
        with open(filepath, 'r') as fh:
            xml_code = fh.read()
        return LaunchXmlParser.parse(xml_code)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        pass # log file not found error


###############################################################################
# Arguments
###############################################################################

def parse_args(argv):
    parser = ArgumentParser(prog = 'haroslaunch',
                            description = 'ROS launch parser.')
    return parser.parse_args(argv)


###############################################################################
# Entry Point
###############################################################################

def main(argv=None):
    args = parse_args(argv)
    args.launch_files
    return 0


if __name__ == '__main__':
    exit(main())
