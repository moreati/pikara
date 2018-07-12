import pickletools

from pickle import dumps
from pickletools import (
    markobject, pybool, pyint, pylist, pynone, pytuple, pyunicode
)

import attr

import pikara.analysis as a

from pikara.analysis import _parse
from pikara.analysis import _ParseEntry
from pikara.analysis import _ParseResult as _PR

from .compat import parametrize_proto


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


class _Wildcard(object):
    """
    A wildcard object, equal to any other object.

    This helps us preserve some position data in our tests without actually
    checking that value.
    """
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False


WILDCARD = _Wildcard()


def _PE(**kw):
    kw["pos"] = WILDCARD
    return _ParseEntry(**kw)


@parametrize_proto()
def test_string(proto, maxproto):
    expected = _PR(
        parsed=[
            _PE(op=ops.PROTO, arg=3, pos=0, stackslice=None),
            _PE(
                op=ops.BINUNICODE, arg="a", pos=2, stackslice=None
            ),  # this will be str on py2 and unicode on py3
            _PE(op=ops.BINPUT, arg=0, pos=8, stackslice=None),
            _PE(op=ops.STOP, arg=None, pos=10, stackslice=[pyunicode]),
        ],
        maxproto=maxproto,
        stack=[],
        memo={0: pyunicode},
    )
    actual = a._parse(dumps(u"a", protocol=proto))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


@parametrize_proto(protos=[1, 2, 3, 4])
def test_list_of_three_ints(proto, maxproto):
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
        maxproto=maxproto,
        stack=[],
        memo={0: pylist},
    )
    actual = a._parse(dumps([1, 2, 3], protocol=proto))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


def test_list_of_three_ints_p0():
    """
    A list of three ints, in protocol version zero.

    This structurally changes the list because p0 didn't have APPENDS, so each
    element is added manually.
    """
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
    actual = _parse(dumps([1, 2, 3], protocol=0))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


@parametrize_proto(protos=[1, 2, 3])
def test_nested_list(proto, maxproto):
    """
    A test for parsing nested lists.

    This test is not run on protocol version zero because the lack of
    MARK/APPENDS fundamentally changes the structure of the pickle. We skip
    version 4 because framing changes the structure of the pickle.
    """
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
        maxproto=maxproto,
        stack=[],
        memo={0: pylist, 1: pylist, 2: pylist},
    )
    actual = a._parse(dumps(outer, protocol=proto))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


# TODO: nested_lists_p4


class NullReduce(object):

    def __reduce__(self):
        return NullReduce, ()


def test_reduce():
    actual = a._parse(dumps(NullReduce(), protocol=3))
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
    # int isn't special except that it's a globally available builtin that maps
    # to the name int on py2 and py3.
    actual = a._parse(dumps(ReduceSentinel(int), protocol=3))
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
                op=ops.GLOBAL, arg="builtins int", pos=37, stackslice=None
            ),
            _PE(op=ops.BINPUT, arg=1, pos=56, stackslice=None),
            _PE(
                op=ops.TUPLE1,
                arg=None,
                pos=58,
                stackslice=[actual.global_objects["builtins int"]],
            ),
            _PE(op=ops.BINPUT, arg=2, pos=59, stackslice=None),
            _PE(
                op=ops.REDUCE,
                arg=None,
                pos=61,
                stackslice=[
                    actual.global_objects["tests.test_parse ReduceSentinel"],
                    [actual.global_objects["builtins int"]],
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
                        [actual.global_objects["builtins int"]],
                    ]
                ],
            ),
        ],
        maxproto=2,
        stack=[],
        memo={
            0: actual.global_objects["tests.test_parse ReduceSentinel"],
            1: actual.global_objects["builtins int"],
            2: [actual.global_objects["builtins int"]],
            3: [
                actual.global_objects["tests.test_parse ReduceSentinel"],
                [actual.global_objects["builtins int"]],
            ],
        },
    )
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


def test_reduce_sentinel_list():
    # int isn't special except that it's a globally available builtin that maps
    # to the name int on py2 and py3.
    actual = a._parse(
        dumps(
            [
                ReduceSentinel(int),
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
                op=ops.GLOBAL, arg="builtins int", pos=41, stackslice=None
            ),
            _PE(op=ops.BINPUT, arg=2, pos=60, stackslice=None),
            _PE(
                op=ops.TUPLE1,
                arg=None,
                pos=62,
                stackslice=[actual.global_objects["builtins int"]],
            ),
            _PE(op=ops.BINPUT, arg=3, pos=63, stackslice=None),
            _PE(
                op=ops.REDUCE,
                arg=None,
                pos=65,
                stackslice=[
                    actual.global_objects["tests.test_parse ReduceSentinel"],
                    [actual.global_objects["builtins int"]],
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
                            [actual.global_objects["builtins int"]],
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
                                [actual.global_objects["builtins int"]],
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
            2: actual.global_objects["builtins int"],
            3: [actual.global_objects["builtins int"]],
            4: [
                actual.global_objects["tests.test_parse ReduceSentinel"],
                [actual.global_objects["builtins int"]],
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


@parametrize_proto()
def test_reduce_ex(proto, maxproto):
    actual = a._parse(dumps(NullReduceEx(), protocol=proto))
    expected = _PR(
        parsed=[
            _PE(op=ops.PROTO, arg=proto, pos=0, stackslice=None),
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
        maxproto=maxproto,
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
