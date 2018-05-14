import pickletools
from pickle import dumps
from pickletools import markobject, pyint, pylist, pyunicode, pytuple, anyobject

import attr

from pikara.analysis import _parse, _ParseEntry, _ParseResult

for opcode in pickletools.opcodes:
    globals()[opcode.name] = opcode

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
        init=False
    )(pickletools.OpcodeInfo)

if getattr(pickletools, "_RawArgumentDescriptor", _MISSING) is _MISSING:
    pickletools._RawArgumentDescriptor = pickletools.ArgumentDescriptor
    pickletools.ArgumentDescriptor = attr.s(
        these={
            "name": attr.ib(),
            "n": attr.ib()
        },
        init=False
    )(pickletools.ArgumentDescriptor)


def test_string():
    expected = _ParseResult(
        parsed=[
            _ParseEntry(op=PROTO, arg=3, pos=0, stackslice=None),
            _ParseEntry(op=BINUNICODE, arg='a', pos=2, stackslice=None),  # this will be str on py2 and unicode on py3
            _ParseEntry(op=BINPUT, arg=0, pos=8, stackslice=None),
            _ParseEntry(op=STOP, arg=None, pos=10, stackslice=[pyunicode])
        ],
        maxproto=2,
        stack=[],
        memo={0: pyunicode}
    )
    actual = _parse(dumps(u"a", protocol=3))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


def test_list_of_three_ints():
    list_of_three_ints_slice = [pylist, markobject, [pyint, pyint, pyint]]
    expected = _ParseResult(
        parsed=[
            _ParseEntry(op=PROTO, arg=3, pos=0, stackslice=None),
            _ParseEntry(op=EMPTY_LIST, arg=None, pos=2, stackslice=None),
            _ParseEntry(op=BINPUT, arg=0, pos=3, stackslice=None),
            _ParseEntry(op=MARK, arg=None, pos=5, stackslice=None),
            _ParseEntry(op=BININT1, arg=1, pos=6, stackslice=None),
            _ParseEntry(op=BININT1, arg=2, pos=8, stackslice=None),
            _ParseEntry(op=BININT1, arg=3, pos=10, stackslice=None),
            _ParseEntry(op=APPENDS, arg=None, pos=12, stackslice=list_of_three_ints_slice),
            _ParseEntry(op=STOP, arg=None, pos=13, stackslice=[list_of_three_ints_slice])],
        maxproto=2,
        stack=[],
        memo={0: pylist}
    )
    actual = _parse(dumps([1, 2, 3], protocol=3))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


def test_nested_list():
    inner = [1]
    middle = [2, inner]
    outer = [3, middle]

    innerslice = [pylist, pyint] # no markobject because plain append, not appends
    middleslice = [pylist, markobject, [pyint, innerslice]]
    outerslice = [pylist, markobject, [pyint, middleslice]]

    expected = _ParseResult(
        parsed=[
            _ParseEntry(op=PROTO, arg=3, pos=0, stackslice=None),

            # Outer list
            _ParseEntry(op=EMPTY_LIST, arg=None, pos=2, stackslice=None),
            _ParseEntry(op=BINPUT, arg=0, pos=3, stackslice=None),
            _ParseEntry(op=MARK, arg=None, pos=5, stackslice=None),
            _ParseEntry(op=BININT1, arg=3, pos=6, stackslice=None),

            # Middle list
            _ParseEntry(op=EMPTY_LIST, arg=None, pos=8, stackslice=None),
            _ParseEntry(op=BINPUT, arg=1, pos=9, stackslice=None),
            _ParseEntry(op=MARK, arg=None, pos=11, stackslice=None),
            _ParseEntry(op=BININT1, arg=2, pos=12, stackslice=None),

            # Inner list
            _ParseEntry(op=EMPTY_LIST, arg=None, pos=14, stackslice=None),
            _ParseEntry(op=BINPUT, arg=2, pos=15, stackslice=None),
            _ParseEntry(op=BININT1, arg=1, pos=17, stackslice=None),

            # Build inner, middle, outer lists
            _ParseEntry(op=APPEND, arg=None, pos=19, stackslice=innerslice),
            _ParseEntry(op=APPENDS, arg=None, pos=20, stackslice=middleslice),
            _ParseEntry(op=APPENDS, arg=None, pos=21, stackslice=outerslice),

            _ParseEntry(op=STOP, arg=None, pos=22, stackslice=[outerslice])
        ],
        maxproto=2,
        stack=[],
        memo={0: pylist, 1: pylist, 2: pylist}
    )
    actual = _parse(dumps(outer, protocol=3))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


class NullReduce():
    def __reduce__(self):
        return NullReduce, ()


def test_reduce():
    expected = _ParseResult(
        parsed=[
            _ParseEntry(op=PROTO, arg=3, pos=0, stackslice=None),
            _ParseEntry(op=GLOBAL, arg='tests.test_parse NullReduce', pos=2, stackslice=None),
            # is this unicode or bytes'
            _ParseEntry(op=BINPUT, arg=0, pos=31, stackslice=None),
            _ParseEntry(op=EMPTY_TUPLE, arg=None, pos=33, stackslice=None),
            _ParseEntry(op=REDUCE, arg=None, pos=34, stackslice=[anyobject, pytuple]),
            _ParseEntry(op=BINPUT, arg=1, pos=35, stackslice=None),
            _ParseEntry(op=STOP, arg=None, pos=37, stackslice=[[anyobject, pytuple]])
        ],
        maxproto=2,
        stack=[],
        memo={0: anyobject, 1: [anyobject, pytuple]}
    )
    actual = _parse(dumps(NullReduce(), protocol=3))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo


class NullReduceEx():
    def __reduce_ex__(self, protocol):
        return NullReduceEx, ()


def test_reduce_ex():
    expected = _ParseResult(
        parsed=[
            _ParseEntry(op=PROTO, arg=3, pos=0, stackslice=None),
            _ParseEntry(op=GLOBAL, arg='tests.test_parse NullReduceEx', pos=2, stackslice=None),
            # is this unicode or bytes'
            _ParseEntry(op=BINPUT, arg=0, pos=33, stackslice=None),
            _ParseEntry(op=EMPTY_TUPLE, arg=None, pos=35, stackslice=None),
            _ParseEntry(op=REDUCE, arg=None, pos=36, stackslice=[anyobject, pytuple]),
            _ParseEntry(op=BINPUT, arg=1, pos=37, stackslice=None),
            _ParseEntry(op=STOP, arg=None, pos=39, stackslice=[[anyobject, pytuple]])
        ],
        maxproto=2,
        stack=[],
        memo={0: anyobject, 1: [anyobject, pytuple]}
    )
    actual = _parse(dumps(NullReduceEx(), protocol=3))
    assert expected.parsed == actual.parsed
    assert expected.maxproto == actual.maxproto
    assert expected.stack == actual.stack
    assert expected.memo == actual.memo
