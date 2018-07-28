from pickletools import pybool, pyint, pylist, pynone, pytuple, pyunicode

import pytest

from pikara.analysis import (
    pickled_bool, pickled_int, pickled_list, pickled_none, pickled_string,
    pickled_tuple
)


@pytest.mark.parametrize(
    "ourtype,theirtype",
    [
        (pickled_none, pynone),
        (pickled_string, pyunicode),
        (pickled_list, pylist),
        (pickled_int, pyint),
        (pickled_tuple, pytuple),
        (pickled_bool, pybool),
    ],
)
def test_typematchers(ourtype, theirtype):
    assert ourtype == theirtype
