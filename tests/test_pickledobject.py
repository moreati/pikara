import pickletools as pt

import pikara.analysis as pa

from .test_parse import ops


def test_NONE():
    po = pa.PickledObject.for_parsed_op(ops.NONE, None)
    assert po.pickletools_type is pt.pynone
    assert po.value is None


def test_NEWFALSE():
    po = pa.PickledObject.for_parsed_op(ops.NEWFALSE, None)
    assert po.pickletools_type is pt.pybool
    assert po.value is False


def test_NEWTRUE():
    po = pa.PickledObject.for_parsed_op(ops.NEWTRUE, None)
    assert po.pickletools_type is pt.pybool
    assert po.value is True


def test_INT():
    po = pa.PickledObject.for_parsed_op(ops.INT, 15)
    assert po.pickletools_type is pt.pyinteger_or_bool
    assert po.value == 15


def test_BININT():
    po = pa.PickledObject.for_parsed_op(ops.BININT, 15)
    assert po.pickletools_type is pt.pyint
    assert po.value == 15


def test_eq_same_type_and_value():
    po1 = pa.PickledObject.for_parsed_op(ops.BININT, 15)
    po2 = pa.PickledObject.for_parsed_op(ops.BININT, 15)
    assert po1 == po2


def test_eq_same_type_different_value():
    po1 = pa.PickledObject.for_parsed_op(ops.BININT, 15)
    po2 = pa.PickledObject.for_parsed_op(ops.BININT, 18)
    assert po1 == po2


def test_eq_different_type():
    po1 = pa.PickledObject.for_parsed_op(ops.BININT, 15)
    po2 = pa.PickledObject.for_parsed_op(ops.NEWTRUE, None)
    assert po1 != po2


def test_eq_against_value():
    assert pa.PickledObject.for_parsed_op(ops.BININT, 15) == 15


def test_eq_against_different_value():
    assert pa.PickledObject.for_parsed_op(ops.BININT, 15) != 16


def test_eq_against_type():
    po = pa.PickledObject.for_parsed_op(ops.BININT, 15)
    assert po == pt.pyint


def test_eq_against_different_type():
    po = pa.PickledObject.for_parsed_op(ops.BININT, 15)
    assert po == pt.pyint
