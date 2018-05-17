from pickle import dumps

from pikara.analysis import (
    _Brine,
    pickled_string,
    pickled_tuple,
    pickled_bool,
    pickled_none,
    pickled_int,
    pickled_list,
    analyze_pickle,
)

_MISSING = object()


def test_string():
    expected = _Brine(shape=pickled_string, maxproto=2)
    actual = analyze_pickle(dumps(u"a", protocol=3)).brine
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


def test_list_of_three_ints():
    expected = _Brine(
        shape=[pickled_list, [pickled_int, pickled_int, pickled_int]],
        maxproto=2,
    )
    actual = analyze_pickle(dumps([1, 2, 3], protocol=3)).brine
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


def test_list_of_three_ints_p0():
    expected = _Brine(
        shape=[pickled_list, [pickled_int, pickled_int, pickled_int]],
        maxproto=0,
    )
    actual = analyze_pickle(dumps([1, 2, 3], protocol=0)).brine
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
    actual = analyze_pickle(dumps(outer, protocol=3)).brine
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


class NullReduce(object):

    def __reduce__(self):
        return NullReduce, ()


def test_reduce():
    actual = analyze_pickle(dumps(NullReduce(), protocol=3)).brine
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


def test_reduce_sentinel():
    actual = analyze_pickle(dumps(ReduceSentinel(Ellipsis), protocol=3)).brine
    expected = _Brine(
        shape=[
            actual.global_objects["tests.test_brine ReduceSentinel"],
            [actual.global_objects["builtins Ellipsis"]],
        ],
        maxproto=2,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


def test_reduce_sentinel_list():
    actual = analyze_pickle(
        dumps(
            [
                ReduceSentinel(Ellipsis),
                ReduceSentinel(True),
                ReduceSentinel(None),
            ],
            protocol=3,
        )
    ).brine
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


def test_reduce_ex():
    actual = analyze_pickle(dumps(NullReduceEx(), protocol=3)).brine
    expected = _Brine(
        shape=[
            actual.global_objects["tests.test_brine NullReduceEx"],
            pickled_tuple,
        ],
        maxproto=2,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto
