from pickle import POP, PROTO, STOP
from pickletools import optimize

from pytest import raises
from six import int2byte

from pikara import analysis as a

from .test_parse import ops


try:
    from pickle import DEFAULT_PROTOCOL
except ImportError:
    # Only py3 exports DEFAULT_PROTOCOL; the default on py2 is v0
    DEFAULT_PROTOCOL = 0


# TODO: parametrize all of these and see what happens
def proto_op(proto=DEFAULT_PROTOCOL):
    """
    The PROTO message in a pickle. If the version is too old to include a PROTO
    instruction, return an empty bytestring instead.
    """
    if proto >= 2:
        return PROTO + int2byte(proto)
    else:
        return b""


def test_proto_op():
    assert proto_op(0) == proto_op(1) == b""
    assert proto_op(2) == b"\x80\x02"
    assert proto_op(3) == b"\x80\x03"
    assert proto_op(4) == b"\x80\x04"


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
    p = proto_op() + string_op + STOP
    assert optimize(p) == a.critique(p)


def test_unused_string():
    """
    Critiques a pickle consisting of a start, a string literal, a new string
    literal, and a stop. Should fail because the stack isn't empty at the end
    of parsing.
    """
    double_string = proto_op() + string_op * 2 + STOP
    critique_raises(a.PickleException, double_string)
    # TODO: test something useful here about the critique output?


def test_last_instruction_isnt_stop():
    """
    Produces a pickle that has a proto header and a string, but no STOP.
    """
    critique_raises(a.PickleException, proto_op() + string_op)
    # TODO: test something useful here about the critique output?


def test_stack_underflow():
    """
    Tests that critique correctly catches a stack underflow.
    """
    underflow = proto_op() + POP + STOP
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
