from pickle import dumps

from pikara.analysis import extract_brine, Brine, pickled_string, pickled_tuple, \
    pickled_bool, pickled_none, pickled_int, pickled_list

_MISSING = object()


def test_string():
    expected = Brine(
        shape=pickled_string,
        maxproto=2,

    )
    actual = extract_brine(dumps(u"a", protocol=3))
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


def test_list_of_three_ints():
    expected = Brine(
        shape=[pickled_list, [pickled_int, pickled_int, pickled_int]],
        maxproto=2,

    )
    actual = extract_brine(dumps([1, 2, 3], protocol=3))
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


def test_list_of_three_ints_p0():
    expected = Brine(
        shape=[pickled_list, [pickled_int, pickled_int, pickled_int]],
        maxproto=0,

    )
    actual = extract_brine(dumps([1, 2, 3], protocol=0))
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


def test_nested_list():
    inner = [1]
    middle = [2, inner]
    outer = [3, middle]

    innerslice = [pickled_list, [pickled_int]]  # no markobject because plain append, not appends
    middleslice = [pickled_list, [pickled_int, innerslice]]
    outerslice = [pickled_list, [pickled_int, middleslice]]

    expected = Brine(
        shape=outerslice,
        maxproto=2,
    )
    actual = extract_brine(dumps(outer, protocol=3))
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


class NullReduce(object):
    def __reduce__(self):
        return NullReduce, ()


def test_reduce():
    actual = extract_brine(dumps(NullReduce(), protocol=3))
    expected = Brine(
        shape=[actual.global_objects['tests.test_brine NullReduce'], pickled_tuple],
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
    actual = extract_brine(dumps(ReduceSentinel(Ellipsis), protocol=3))
    expected = Brine(
        shape=[actual.global_objects['tests.test_brine ReduceSentinel'], [
            actual.global_objects['builtins Ellipsis']]],
        maxproto=2
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


def test_reduce_sentinel_list():
    actual = extract_brine(dumps([ReduceSentinel(Ellipsis), ReduceSentinel(True), ReduceSentinel(None)], protocol=3))
    expected = Brine(
        shape=[pickled_list, [[actual.global_objects['tests.test_brine ReduceSentinel'],
                               [actual.global_objects['builtins Ellipsis']]],
                              [actual.global_objects['tests.test_brine ReduceSentinel'],
                               [pickled_bool]],
                              [actual.global_objects['tests.test_brine ReduceSentinel'],
                               [pickled_none]]]],
        maxproto=2,
    )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto


class NullReduceEx(object):
    def __reduce_ex__(self, protocol):
        return NullReduceEx, ()


def test_reduce_ex():
    actual = extract_brine(dumps(NullReduceEx(), protocol=3))
    expected = Brine(shape=[actual.global_objects['tests.test_brine NullReduceEx'], pickled_tuple],
                     maxproto=2,
                     )
    assert expected.shape == actual.shape
    assert expected.maxproto == actual.maxproto
