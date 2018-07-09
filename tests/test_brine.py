import io
import pickle
from pickle import LIST, MARK, INT, STOP, TUPLE

from .compat import parametrize_proto
from pikara.analysis import (
    _Brine, _extract_brine, pickled_bool, pickled_int, pickled_list,
    pickled_none, pickled_string, pickled_tuple, pickled_int_or_bool
)

from .compat import parametrize_proto
from .test_critique import proto_op


@parametrize_proto()
def test_unicode_string(proto, maxproto):
    expected = _Brine(shape=pickled_string, maxproto=maxproto)
    actual = _extract_brine(pickle.dumps(u"a", protocol=proto))
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


@parametrize_proto()
def test_list_of_three_ints(proto, maxproto):
    expected = _Brine(
        shape=[pickled_list, [pickled_int, pickled_int, pickled_int]],
        maxproto=maxproto,
    )
    actual = _extract_brine(pickle.dumps([1, 2, 3], protocol=proto))
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


@parametrize_proto()
def test_explicit_list_instruction(proto, maxproto):
    instructions = [proto_op(proto), MARK, INT, b"1\n", LIST, STOP]
    pickle = b"".join(instructions)
    # v2 is the first protocol to introduce the PROTO instruction, the other
    # instructions are in every version. proto_op returns b"" for <2
    maxproto = 0 if proto < 2 else 2
    # this is unconditionally a list of a pickled_int_or_bool because it uses
    # the INT instruction.
    expected = _Brine(
        shape=[pickled_list, [pickled_int_or_bool]],
        maxproto=maxproto
    )
    actual = _extract_brine(pickle)
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto
    )
    actual = _extract_brine(dumps([1, 2, 3], protocol=0))
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


def test_nested_list():
    inner = [1]
    middle = [2, inner]
    outer = [3, middle]

    innerslice = [
        pickled_list, [pickled_int]
    ]  # no markobject because plain append, not appends
    middleslice = [pickled_list, [pickled_int, innerslice]]
    outerslice = [pickled_list, [pickled_int, middleslice]]

    expected = _Brine(shape=outerslice, maxproto=2)
    actual = _extract_brine(dumps(outer, protocol=3))
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


class NullReduce(object):
    """
    A simple object that uses __reduce__ to pickle itself.
    """
    def __reduce__(self):
        return NullReduce, ()


# TODO: we return the wrong structure for proto 0 (see #13)
# TODO: we don't know how to deal with STACK_GLOBAL in proto 4 (see #12)
@parametrize_proto(protos=[1, 2, 3])
def test_reduce(proto, maxproto):
    actual = _extract_brine(pickle.dumps(NullReduce(), protocol=proto))
    expected = _Brine(
        shape=[
            actual.global_objects["tests.test_brine NullReduce"], pickled_tuple
        ],
        maxproto=maxproto,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


class ReduceSentinel(object):

    def __init__(self, s):
        self.s = s

    def __reduce__(self):
        return ReduceSentinel, (self.s,)


@parametrize_proto()
def test_reduce_sentinel(proto, maxproto):
    # io.BytesIO isn't special except that it isn't rewritten via the
    # _pickle_compat module to enhance compatibility with Python 3. When
    # producing/consuming pickles <= v2, Python 3 knows to translate between
    # the two... sort of.
    actual = _extract_brine(pickle.dumps(ReduceSentinel(io.BytesIO), protocol=proto))
    expected = _Brine(
        shape=[
            actual.global_objects["tests.test_brine ReduceSentinel"],
            [actual.global_objects["_io BytesIO"]],
        ],
        maxproto=maxproto,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


@parametrize_proto()
def test_reduce_sentinel_list(proto, maxproto):
    # io.BytesIO isn't special except that it isn't rewritten via the
    # _pickle_compat module to enhance compatibility with Python 3. When
    # producing/consuming pickles <= v2, Python 3 knows to translate between
    # the two... sort of.
    actual = _extract_brine(
        dumps(
            [
                ReduceSentinel(io.BytesIO),
                ReduceSentinel(True),
                ReduceSentinel(None),
            ],
            protocol=proto,
        )
    )
    expected = _Brine(
        shape=[
            pickled_list,
            [
                [
                    actual.global_objects["tests.test_brine ReduceSentinel"],
                    [actual.global_objects["_io BytesIO"]],
                ],
                [
                    actual.global_objects["tests.test_brine ReduceSentinel"],
                    [pickled_bool],
                ],
                [
                    actual.global_objects["tests.test_brine ReduceSentinel"],
                    [pickled_none],
                ],
            ],
        ],
        maxproto=maxproto,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


class NullReduceEx(object):

    def __reduce_ex__(self, protocol):
        return NullReduceEx, ()


@parametrize_proto()
def test_reduce_ex(proto, maxproto):
    actual = _extract_brine(pickle.dumps(NullReduceEx(), protocol=proto))
    expected = _Brine(
        shape=[
            actual.global_objects["tests.test_brine NullReduceEx"],
            pickled_tuple,
        ],
        maxproto=maxproto,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto
