from pickletools import optimize

from pikara import analysis as a
from pytest import raises
from six import int2byte


def proto(version=3):
    """
    The PROTO message in a pickle.
    """
    return b"\x80" + int2byte(3)


stop = b"."
string_op = b"X\x03\x00\x00\x00abc"


def test_just_a_string():
    double_string = proto() +  string_op + stop
    assert optimize(double_string) == a.critique(double_string)


def test_double_string():
    double_string = proto() +  string_op * 2 + stop
    issues = critique_raises(a.PickleException, double_string)


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

    with raises(CritiqueException) as excinfo:
        a.critique(pickle, *args, **dict(kwargs, fail_fast=False))
    assert isinstance(excinfo.value, a.CritiqueException)
    assert all(
        isinstance(a.PickleException, i)
        for i in excinfo.value.issues
    )
    assert isinstance(exception_class, excinfo.value.issues[0])
    return excinfo.value
