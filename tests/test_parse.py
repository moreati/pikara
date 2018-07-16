import datetime
import pickle
import pickletools
from pickletools import (
    markobject,
    pybool,
    pyint,
    pylist,
    pynone,
    pytuple,
    pyunicode,
)

import attr
import zodbpickle.pickle

import pikara.analysis as a
from pikara.analysis import _ParseEntry as _PE
from pikara.analysis import _ParseResult as _PR
from pikara.analysis import _parse


def fake_dumps(obj, protocol):
    """
    Return the pickled representation obj, using the explicitly specified
    protocol.

    This function is a verified, restricted fake of pickle.dumps().

    Protocol must be specified. If protocol is specified as a negative number,
    pickle.HIGHEST_PROTOCOL is selected.

    If protocol is specified higher than pickle.HIGHEST_PROTOCOL, the value
    returned by zodbpickle is used directly. Otherwise the value returned by
    zodbpickle is checked against the value returned by pickle.dumps(), before
    it is returned.
    """
    assert isinstance(protocol, int)
    if protocol < 0:
        protocol = pickle.HIGHEST_PROTOCOL

    zo_pickle = zodbpickle.pickle.dumps(obj, protocol=protocol)

    # Python's stdlib pickle does not support this protocol, trust zodbpickle
    if protocol >= pickle.HIGHEST_PROTOCOL:
        return zo_pickle

    # Python's stdlib pickle supports this protocol, verify zodbpickle
    # On Python 3.x pickle.dumps() accepts an extra keyword-only argument
    py_pickle = pickle.dumps(obj, protocol=protocol)
    assert zo_pickle == py_pickle

    return zo_pickle


def test_rfind():
    my_sentinel = object()
    assert a._rfind([], 1, my_sentinel) is my_sentinel
    assert a._rfind([1], 1, my_sentinel) == 0
    assert a._rfind([1, 1, 1, 1], 1, my_sentinel) == 3


ops_by_name = {opcode.name: opcode for opcode in pickletools.opcodes}
ops = type("Opcodes", (), ops_by_name)

_MISSING = object()

if getattr(pickletools, "_RawOpcodeInfo", _MISSING) is _MISSING:
    pickletools._RawOpcodeInfo = pickletools.OpcodeInfo
    pickletools.OpcodeInfo = attr.s(
        these={
            "name": attr.ib(),
            "code": attr.ib(),
            "arg": attr.ib(),
            "stack_before": attr.ib(),
            "stack_after": attr.ib(),
            "proto": attr.ib(),
        },
        init=False,
    )(
        pickletools.OpcodeInfo
    )

if getattr(pickletools, "_RawArgumentDescriptor", _MISSING) is _MISSING:
    pickletools._RawArgumentDescriptor = pickletools.ArgumentDescriptor
    pickletools.ArgumentDescriptor = attr.s(
        these={"name": attr.ib(), "n": attr.ib()}, init=False
    )(
        pickletools.ArgumentDescriptor
    )


def test_string():
    expected = _PR(
        parsed=[
            _PE(op=ops.PROTO, arg=3, pos=0, stackslice=None),
            _PE(
                op=ops.BINUNICODE, arg="a", pos=2, stackslice=None
            ),  # this will be str on py2 and unicode on py3
            _PE(op=ops.BINPUT, arg=0, pos=8, stackslice=None),
            _PE(op=ops.STOP, arg=None, pos=10, stackslice=[pyunicode]),
        ],
        maxproto=2,
        stack=[],
        memo={0: pyunicode},
    )
    actual = a._parse(fake_dumps(u"a", protocol=3))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


def test_list_of_three_ints():
    list_of_three_ints_slice = [pylist, [pyint, pyint, pyint]]
    expected = _PR(
        parsed=[
            _PE(op=ops.PROTO, arg=3, pos=0, stackslice=None),
            _PE(op=ops.EMPTY_LIST, arg=None, pos=2, stackslice=None),
            _PE(op=ops.BINPUT, arg=0, pos=3, stackslice=None),
            _PE(op=ops.MARK, arg=None, pos=5, stackslice=None),
            _PE(op=ops.BININT1, arg=1, pos=6, stackslice=None),
            _PE(op=ops.BININT1, arg=2, pos=8, stackslice=None),
            _PE(op=ops.BININT1, arg=3, pos=10, stackslice=None),
            _PE(
                op=ops.APPENDS,
                arg=None,
                pos=12,
                stackslice=[pylist, markobject, [pyint, pyint, pyint]],
            ),
            _PE(
                op=ops.STOP,
                arg=None,
                pos=13,
                stackslice=[list_of_three_ints_slice],
            ),
        ],
        maxproto=2,
        stack=[],
        memo={0: pylist},
    )
    actual = a._parse(fake_dumps([1, 2, 3], protocol=3))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


def test_list_of_three_ints_p0():
    expected = _PR(
        parsed=[
            _PE(op=ops.MARK, arg=None, pos=0, stackslice=None),
            _PE(op=ops.LIST, arg=None, pos=1, stackslice=[markobject, []]),
            _PE(op=ops.PUT, arg=0, pos=2, stackslice=None),
            _PE(op=ops.LONG, arg=1, pos=5, stackslice=None),
            _PE(
                op=ops.APPEND,
                arg=None,
                pos=9,
                stackslice=[[pylist, []], pyint],
            ),  # after stack to [pyint]
            _PE(op=ops.LONG, arg=2, pos=10, stackslice=None),
            _PE(
                op=ops.APPEND,
                arg=None,
                pos=14,
                stackslice=[[pylist, [pyint]], pyint],
            ),
            _PE(op=ops.LONG, arg=3, pos=15, stackslice=None),
            _PE(
                op=ops.APPEND,
                arg=None,
                pos=19,
                stackslice=[[pylist, [pyint, pyint]], pyint],
            ),
            _PE(
                op=ops.STOP,
                arg=None,
                pos=20,
                stackslice=[[pylist, [pyint, pyint, pyint]]],
            ),
        ],
        maxproto=0,
        stack=[],
        memo={0: [pylist, []]},
    )
    actual = _parse(fake_dumps([1, 2, 3], protocol=0))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


def test_nested_list():
    inner = [1]
    middle = [2, inner]
    outer = [3, middle]

    innerslice = [pylist, [pyint]]  # no markobject because plain append,
    # not appends
    middleslice = [pylist, markobject, [pyint, innerslice]]
    outerslice = [
        pylist,
        markobject,
        [pyint, [so for so in middleslice if so != markobject]],
    ]

    expected = _PR(
        parsed=[
            _PE(op=ops.PROTO, arg=3, pos=0, stackslice=None),
            # Outer list
            _PE(op=ops.EMPTY_LIST, arg=None, pos=2, stackslice=None),
            _PE(op=ops.BINPUT, arg=0, pos=3, stackslice=None),
            _PE(op=ops.MARK, arg=None, pos=5, stackslice=None),
            _PE(op=ops.BININT1, arg=3, pos=6, stackslice=None),
            # Middle list
            _PE(op=ops.EMPTY_LIST, arg=None, pos=8, stackslice=None),
            _PE(op=ops.BINPUT, arg=1, pos=9, stackslice=None),
            _PE(op=ops.MARK, arg=None, pos=11, stackslice=None),
            _PE(op=ops.BININT1, arg=2, pos=12, stackslice=None),
            # Inner list
            _PE(op=ops.EMPTY_LIST, arg=None, pos=14, stackslice=None),
            _PE(op=ops.BINPUT, arg=2, pos=15, stackslice=None),
            _PE(op=ops.BININT1, arg=1, pos=17, stackslice=None),
            # Build inner, middle, outer lists
            _PE(op=ops.APPEND, arg=None, pos=19, stackslice=[pylist, pyint]),
            _PE(op=ops.APPENDS, arg=None, pos=20, stackslice=middleslice),
            _PE(op=ops.APPENDS, arg=None, pos=21, stackslice=outerslice),
            _PE(
                op=ops.STOP,
                arg=None,
                pos=22,
                stackslice=[[so for so in outerslice if so != markobject]],
            ),
        ],
        maxproto=2,
        stack=[],
        memo={0: pylist, 1: pylist, 2: pylist},
    )
    actual = a._parse(fake_dumps(outer, protocol=3))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


class NullReduce(object):

    def __reduce__(self):
        return NullReduce, ()


def test_reduce():
    actual = a._parse(fake_dumps(NullReduce(), protocol=3))
    expected = _PR(
        parsed=[
            _PE(op=ops.PROTO, arg=3, pos=0, stackslice=None),
            _PE(
                op=ops.GLOBAL,
                arg="tests.test_parse NullReduce",
                pos=2,
                stackslice=None,
            ),
            _PE(op=ops.BINPUT, arg=0, pos=31, stackslice=None),
            _PE(op=ops.EMPTY_TUPLE, arg=None, pos=33, stackslice=None),
            _PE(
                op=ops.REDUCE,
                arg=None,
                pos=34,
                stackslice=[
                    actual.global_objects["tests.test_parse NullReduce"],
                    pytuple,
                ],
            ),
            _PE(op=ops.BINPUT, arg=1, pos=35, stackslice=None),
            _PE(
                op=ops.STOP,
                arg=None,
                pos=37,
                stackslice=[
                    [
                        actual.global_objects["tests.test_parse NullReduce"],
                        pytuple,
                    ]
                ],
            ),
        ],
        maxproto=2,
        stack=[],
        memo={
            0: actual.global_objects["tests.test_parse NullReduce"],
            1: [actual.global_objects["tests.test_parse NullReduce"], pytuple],
        },
    )
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


class ReduceSentinel(object):

    def __init__(self, s):
        self.s = s

    def __reduce__(self):
        return ReduceSentinel, (self.s,)


def test_reduce_sentinel():
    pickled = fake_dumps(ReduceSentinel(datetime.datetime), protocol=3)
    actual = a._parse(pickled)
    expected = _PR(
        parsed=[
            _PE(op=ops.PROTO, arg=3, pos=0, stackslice=None),
            _PE(
                op=ops.GLOBAL,
                arg="tests.test_parse ReduceSentinel",
                pos=2,
                stackslice=None,
            ),
            _PE(op=ops.BINPUT, arg=0, pos=35, stackslice=None),
            _PE(
                op=ops.GLOBAL, arg="datetime datetime", pos=37, stackslice=None
            ),
            _PE(op=ops.BINPUT, arg=1, pos=56, stackslice=None),
            _PE(
                op=ops.TUPLE1,
                arg=None,
                pos=58,
                stackslice=[actual.global_objects["datetime datetime"]],
            ),
            _PE(op=ops.BINPUT, arg=2, pos=59, stackslice=None),
            _PE(
                op=ops.REDUCE,
                arg=None,
                pos=61,
                stackslice=[
                    actual.global_objects["tests.test_parse ReduceSentinel"],
                    [actual.global_objects["datetime datetime"]],
                ],
            ),
            _PE(op=ops.BINPUT, arg=3, pos=62, stackslice=None),
            _PE(
                op=ops.STOP,
                arg=None,
                pos=64,
                stackslice=[
                    [
                        actual.global_objects[
                            "tests.test_parse " "ReduceSentinel"
                        ],
                        [actual.global_objects["datetime datetime"]],
                    ]
                ],
            ),
        ],
        maxproto=2,
        stack=[],
        memo={
            0: actual.global_objects["tests.test_parse ReduceSentinel"],
            1: actual.global_objects["datetime datetime"],
            2: [actual.global_objects["datetime datetime"]],
            3: [
                actual.global_objects["tests.test_parse ReduceSentinel"],
                [actual.global_objects["datetime datetime"]],
            ],
        },
    )
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


def test_reduce_sentinel_list():
    actual = a._parse(
        fake_dumps(
            [
                ReduceSentinel(datetime.datetime),
                ReduceSentinel(True),
                ReduceSentinel(None),
            ],
            protocol=3,
        )
    )
    expected = _PR(
        parsed=[
            _PE(op=ops.PROTO, arg=3, pos=0, stackslice=None),
            _PE(op=ops.EMPTY_LIST, arg=None, pos=2, stackslice=None),
            _PE(op=ops.BINPUT, arg=0, pos=3, stackslice=None),
            _PE(op=ops.MARK, arg=None, pos=5, stackslice=None),
            _PE(
                op=ops.GLOBAL,
                arg="tests.test_parse ReduceSentinel",
                pos=6,
                stackslice=None,
            ),
            _PE(op=ops.BINPUT, arg=1, pos=39, stackslice=None),
            _PE(
                op=ops.GLOBAL, arg="datetime datetime", pos=41, stackslice=None
            ),
            _PE(op=ops.BINPUT, arg=2, pos=60, stackslice=None),
            _PE(
                op=ops.TUPLE1,
                arg=None,
                pos=62,
                stackslice=[actual.global_objects["datetime datetime"]],
            ),
            _PE(op=ops.BINPUT, arg=3, pos=63, stackslice=None),
            _PE(
                op=ops.REDUCE,
                arg=None,
                pos=65,
                stackslice=[
                    actual.global_objects["tests.test_parse ReduceSentinel"],
                    [actual.global_objects["datetime datetime"]],
                ],
            ),
            _PE(op=ops.BINPUT, arg=4, pos=66, stackslice=None),
            _PE(op=ops.BINGET, arg=1, pos=68, stackslice=None),
            _PE(op=ops.NEWTRUE, arg=None, pos=70, stackslice=None),
            _PE(op=ops.TUPLE1, arg=None, pos=71, stackslice=[pybool]),
            _PE(op=ops.BINPUT, arg=5, pos=72, stackslice=None),
            _PE(
                op=ops.REDUCE,
                arg=None,
                pos=74,
                stackslice=[
                    actual.global_objects["tests.test_parse ReduceSentinel"],
                    [pybool],
                ],
            ),
            _PE(op=ops.BINPUT, arg=6, pos=75, stackslice=None),
            _PE(op=ops.BINGET, arg=1, pos=77, stackslice=None),
            _PE(op=ops.NONE, arg=None, pos=79, stackslice=None),
            _PE(op=ops.TUPLE1, arg=None, pos=80, stackslice=[pynone]),
            _PE(op=ops.BINPUT, arg=7, pos=81, stackslice=None),
            _PE(
                op=ops.REDUCE,
                arg=None,
                pos=83,
                stackslice=[
                    actual.global_objects["tests.test_parse ReduceSentinel"],
                    [pynone],
                ],
            ),
            _PE(op=ops.BINPUT, arg=8, pos=84, stackslice=None),
            _PE(
                op=ops.APPENDS,
                arg=None,
                pos=86,
                stackslice=[
                    pylist,
                    markobject,
                    [
                        [
                            actual.global_objects[
                                "tests.test_parse " "ReduceSentinel"
                            ],
                            [actual.global_objects["datetime datetime"]],
                        ],
                        [
                            actual.global_objects[
                                "tests.test_parse " "ReduceSentinel"
                            ],
                            [pybool],
                        ],
                        [
                            actual.global_objects[
                                "tests.test_parse " "ReduceSentinel"
                            ],
                            [pynone],
                        ],
                    ],
                ],
            ),
            _PE(
                op=ops.STOP,
                arg=None,
                pos=87,
                stackslice=[
                    [
                        pylist,
                        [
                            [
                                actual.global_objects[
                                    "tests.test_parse ReduceSentinel"
                                ],
                                [actual.global_objects["datetime datetime"]],
                            ],
                            [
                                actual.global_objects[
                                    "tests.test_parse ReduceSentinel"
                                ],
                                [pybool],
                            ],
                            [
                                actual.global_objects[
                                    "tests.test_parse ReduceSentinel"
                                ],
                                [pynone],
                            ],
                        ],
                    ]
                ],
            ),
        ],
        maxproto=2,
        stack=[],
        memo={
            0: pylist,
            1: actual.global_objects["tests.test_parse ReduceSentinel"],
            2: actual.global_objects["datetime datetime"],
            3: [actual.global_objects["datetime datetime"]],
            4: [
                actual.global_objects["tests.test_parse ReduceSentinel"],
                [actual.global_objects["datetime datetime"]],
            ],
            5: [pybool],
            6: [
                actual.global_objects["tests.test_parse ReduceSentinel"],
                [pybool],
            ],
            7: [pynone],
            8: [
                actual.global_objects["tests.test_parse ReduceSentinel"],
                [pynone],
            ],
        },
    )
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


class NullReduceEx(object):

    def __reduce_ex__(self, protocol):
        return NullReduceEx, ()


def test_reduce_ex():
    actual = a._parse(fake_dumps(NullReduceEx(), protocol=3))
    expected = _PR(
        parsed=[
            _PE(op=ops.PROTO, arg=3, pos=0, stackslice=None),
            _PE(
                op=ops.GLOBAL,
                arg="tests.test_parse NullReduceEx",
                pos=2,
                stackslice=None,
            ),
            _PE(op=ops.BINPUT, arg=0, pos=33, stackslice=None),
            _PE(op=ops.EMPTY_TUPLE, arg=None, pos=35, stackslice=None),
            _PE(
                op=ops.REDUCE,
                arg=None,
                pos=36,
                stackslice=[
                    actual.global_objects["tests.test_parse NullReduceEx"],
                    pytuple,
                ],
            ),
            _PE(op=ops.BINPUT, arg=1, pos=37, stackslice=None),
            _PE(
                op=ops.STOP,
                arg=None,
                pos=39,
                stackslice=[
                    [
                        actual.global_objects["tests.test_parse NullReduceEx"],
                        pytuple,
                    ]
                ],
            ),
        ],
        maxproto=2,
        stack=[],
        memo={
            0: actual.global_objects["tests.test_parse NullReduceEx"],
            1: [
                actual.global_objects["tests.test_parse NullReduceEx"], pytuple
            ],
        },
    )
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo
