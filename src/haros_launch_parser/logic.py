# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Logic
###############################################################################

class LogicalValue(object):
    __slots__ = ()

    @property
    def is_true(self):
        return False

    @property
    def is_false(self):
        return False

    @property
    def is_variable(self):
        return False

LogicLiteral

LogicVariable

LogicNot

LogicAnd

class LogicOr(LogicalValue):
    __slots__ = ('args',)

    def __init__(self, *args):
        self.args = list(args)

    def disjoin(self, value):
        if value.is_true:
            return LogicTrue()
        self.args
