from collections import Counter
from pickletools import opcodes

from six import iteritems

from pikara import analysis as a


all_opcode_names = (
    a.proto_opcode_names
    + a.exec_opcode_names
    + a.persid_opcode_names
    + a.ext_opcode_names
    + a.safe_opcode_names
    + a.float_opcode_names
    + a.list_opcode_names
    + a.tuple_opcode_names
    + a.dict_opcode_names
    + a.set_opcode_names
    + a.stack_opcode_names
    + a.memo_opcode_names
)


def test_all_opcodes_are_known():
    """
    We know about every opcode pickletools knows about.
    """
    unknown = [op.name for op in opcodes if op.name not in all_opcode_names]
    assert not unknown


def test_no_duplicate_opcodes():
    """
    Every opcode we have listed occurs exactly once.
    """
    for (opcode_name, count) in iteritems(Counter(all_opcode_names)):
        assert 1 == count, opcode_name
