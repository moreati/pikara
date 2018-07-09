import pickle

from .compat import parametrize_proto
from pikara.analysis import (
    _Brine, _extract_brine, pickled_bool, pickled_int, pickled_list,
    pickled_none, pickled_string, pickled_tuple, pickled_int_or_bool
)

from .compat import parametrize_proto

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
        maxproto=2,
    )
    actual = _extract_brine(dumps([1, 2, 3], protocol=3))
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


def test_list_of_three_ints_p0():
    expected = _Brine(
        shape=[pickled_list, [pickled_int, pickled_int, pickled_int]],
        maxproto=0,
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


def test_reduce():
    actual = _extract_brine(dumps(NullReduce(), protocol=3))
    expected = _Brine(
        shape=[
            actual.global_objects["tests.test_brine NullReduce"], pickled_tuple
        ],
        maxproto=2,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


class ReduceSentinel(object):

    def __init__(self, s):
        self.s = s

    def __reduce__(self):
        return ReduceSentinel, (self.s,)


    actual = _extract_brine(dumps(ReduceSentinel(Ellipsis), protocol=3))
@parametrize_proto()
def test_reduce_sentinel(proto, maxproto):
    expected = _Brine(
        shape=[
            actual.global_objects["tests.test_brine ReduceSentinel"],
            [actual.global_objects["builtins Ellipsis"]],
        ],
        maxproto=2,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


@parametrize_proto()
def test_reduce_sentinel_list(proto, maxproto):
    actual = _extract_brine(
        dumps(
            [
                ReduceSentinel(Ellipsis),
                ReduceSentinel(True),
                ReduceSentinel(None),
            ],
            protocol=3,
        )
    )
    expected = _Brine(
        shape=[
            pickled_list,
            [
                [
                    actual.global_objects["tests.test_brine ReduceSentinel"],
                    [actual.global_objects["builtins Ellipsis"]],
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
        maxproto=2,
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
        maxproto=2,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto
