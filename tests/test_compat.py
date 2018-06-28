from . import compat

import pytest


@pytest.mark.parametrize(
    "proto,maxproto_fn",
    [(proto, maxproto_fn)
     for proto in compat.all_protos
     for maxproto_fn in [compat.py2_compat_maxproto,
                         compat.maxproto_same_as_proto]]
)
def test_maxproto_less_than_proto(proto, maxproto_fn):
    assert proto >= maxproto_fn(proto)
