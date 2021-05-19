# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

###############################################################################
# Logic
###############################################################################

class LogicValue(object):
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

    @property
    def is_not(self):
        return False

    @property
    def is_and(self):
        return False

    @property
    def is_or(self):
        return False

    def join(self, value):
        if value.is_true:
            return self
        if value.is_false:
            return value
        if value.is_and:
            return value.join(self)
        return LogicAnd((self, value))

    def disjoin(self, value):
        if value.is_true:
            return value
        if value.is_false:
            return self
        if value.is_or:
            return value.disjoin(self)
        return LogicOr((self, value))

    def simplify(self):
        return self


class LogicTrue(LogicValue):
    __slots__ = ()

    @property
    def is_true(self):
        return True

    def join(self, value):
        return value

    def disjoin(self, value):
        return self

    def __repr__(self):
        return '{}()'.format(type(self).__name__)

    def __str__(self):
        return 'True'

    def __hash__(self):
        return hash(True)

    def __eq__(self, other):
        return isinstance(other, LogicTrue)

LogicValue.T = LogicTrue()


class LogicFalse(LogicValue):
    __slots__ = ()

    @property
    def is_false(self):
        return True

    def join(self, value):
        return self

    def disjoin(self, value):
        return value

    def __repr__(self):
        return '{}()'.format(type(self).__name__)

    def __str__(self):
        return 'False'

    def __hash__(self):
        return hash(False)

    def __eq__(self, other):
        return isinstance(other, LogicFalse)

LogicValue.F = LogicFalse()


class LogicVariable(LogicValue):
    __slots__ = ('name', 'text', 'data')

    id_counter = 0

    def __init__(self, text, data, name=None):
        self.text = text # original string value
        self.data = data # anything (e.g., ScopeCondition)
        self.name = name if name else LogicVariable.get_new_name()

    @classmethod
    def get_new_name(cls):
        n = cls.id_counter + 1
        cls.id_counter = n
        return '@' + str(n)

    @property
    def is_variable(self):
        return True

    def __repr__(self):
        return '{}({!r}, {!r}, name={!r})'.format(type(self).__name__,
            self.text, self.data, self.name)

    def __str__(self):
        return self.name or self.text

    def __hash__(self):
        return hash(self.text)

    def __eq__(self, other):
        if not isinstance(other, LogicVariable):
            return False
        return self.text == other.text


class LogicNot(LogicValue):
    __slots__ = ('operand',)

    def __init__(self, arg):
        if not isinstance(arg, LogicValue):
            raise TypeError('expected LogicValue, got ' + type(arg).__name__)
        self.operand = arg

    @property
    def is_not(self):
        return True

    def simplify(self):
        if self.operand.is_not:
            return self.operand.operand.simplify()
        operand = self.operand.simplify()
        if operand.is_true:
            return LogicValue.F
        if operand.is_false:
            return LogicValue.T
        return self

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.operand)

    def __str__(self):
        return '(not {})'.format(self.operand)

    def __hash__(self):
        return hash(self.operand)

    def __eq__(self, other):
        if not isinstance(other, LogicNot):
            return False
        return self.operand == other.operand


class LogicAnd(LogicValue):
    __slots__ = ('operands',)

    def __init__(self, args):
        for x in args:
            if not isinstance(x, LogicValue):
                raise TypeError('expected LogicValue, got ' + type(x).__name__)
        self.operands = tuple(args)

    @property
    def is_and(self):
        return True

    def join(self, value):
        if value.is_true:
            return self
        if value.is_false:
            return value
        operands = list(self.operands)
        if value.is_and:
            operands.extend(value.operands)
        else:
            operands.append(value)
        return LogicAnd(operands)

    def simplify(self):
        operands = set()
        for x in self.operands:
            y = x.simplify()
            if y.is_true:
                continue
            if y.is_false:
                return LogicValue.F
            if y.is_and:
                operands.update(y.operands)
            else:
                operands.add(y)
        if not operands:
            return LogicValue.T
        if len(operands) == 1:
            for x in operands:
                return x
        return LogicAnd(operands)

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.operands)

    def __str__(self):
        if not self.operands:
            return 'True'
        if len(self.operands) == 1:
            for x in self.operands:
                return str(x)
        return ' and '.join(str(x for x in self.operands))

    def __hash__(self):
        return hash(self.operands)

    def __eq__(self, other):
        if not isinstance(other, LogicAnd):
            return False
        return set(self.operands) == set(other.operands)


class LogicOr(LogicValue):
    __slots__ = ('operands',)

    def __init__(self, args):
        for x in args:
            if not isinstance(x, LogicValue):
                raise TypeError('expected LogicValue, got ' + type(x).__name__)
        self.operands = tuple(args)

    @property
    def is_or(self):
        return True

    def disjoin(self, value):
        if value.is_true:
            return value
        if value.is_false:
            return self
        operands = list(self.operands)
        if value.is_or:
            operands.extend(value.operands)
        else:
            operands.append(value)
        return LogicOr(operands)

    def simplify(self):
        operands = set()
        for x in self.operands:
            y = x.simplify()
            if y.is_false:
                continue
            if y.is_true:
                return LogicValue.T
            if y.is_or:
                operands.update(y.operands)
            else:
                operands.add(y)
        if not operands:
            return LogicValue.T
        if len(operands) == 1:
            for x in operands:
                return x
        return LogicOr(operands)

    def __repr__(self):
        return '{}({!r})'.format(type(self).__name__, self.operands)

    def __str__(self):
        if not self.operands:
            return 'True'
        if len(self.operands) == 1:
            for x in self.operands:
                return str(x)
        return ' or '.join(str(x for x in self.operands))

    def __hash__(self):
        return hash(self.operands)

    def __eq__(self, other):
        if not isinstance(other, LogicOr):
            return False
        return set(self.operands) == set(other.operands)
