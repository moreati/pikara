from pickletools import optimize

from pytest import raises
from six import int2byte

from pikara import analysis as a
from .test_parse import ops


def proto(version=3):
    """
    The PROTO message in a pickle.
    """
    return b"\x80" + int2byte(3)


stop = b"."
string_op = b"X\x03\x00\x00\x00abc"


def test_idempotent_critiquer():
    """
    Adding a critiquer twice is idempotent.
    """
    before = list(a._critiquers)
    assert before[0] == a._critiquer(before[0])
    after = list(a._critiquers)
    assert before == after


def test_just_a_string():
    p = proto() + string_op + stop
    assert optimize(p) == a.critique(p)


def test_unused_string():
    """
    Critiques a pickle consisting of a start, a string literal, a new string
    literal, and a stop. Should fail because the stack isn't empty at the end
    of parsing.
    """
    double_string = proto() + string_op * 2 + stop
    critique_raises(a.PickleException, double_string)
    # TODO: test something useful here about the critique output?


def test_last_instruction_isnt_stop():
    """
    Produces a pickle that has a proto header and a string, but no STOP.
    """
    critique_raises(a.PickleException, proto() + string_op)
    # TODO: test something useful here about the critique output?


def test_stack_underflow():
    """
    Tests that critique correctly catches a stack underflow.
    """
    underflow = proto() + ops.POP.code.encode("latin1") + stop
    critique_raises(a.StackUnderflowException, underflow)


def critique_raises(exception_class, pickle, *args, **kwargs):
    """
    Verifies that critiquing the raises the given exception and returns all
    exceptions the critique produces.

    Tries to run both as normal critique (fail fast) and slow critique (collect
    as many errors as possible). Returns the CritiqueException raised by the
    latter for inspection.
    """
    with raises(exception_class) as excinfo:
        a.critique(pickle, *args, **kwargs)
    assert not isinstance(excinfo.value, a.CritiqueException)

    with raises(a.CritiqueException) as excinfo:
        a.critique(pickle, *args, **dict(kwargs, fail_fast=False))
    assert isinstance(excinfo.value, a.CritiqueException)
    report = excinfo.value.report
    assert all(isinstance(i, a.PickleException) for i in report.issues)
    assert isinstance(report.issues[0], exception_class)
    return report
