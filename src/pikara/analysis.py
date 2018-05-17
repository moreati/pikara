import pickletools
from pickletools import StackObject
from pickletools import markobject
from pickletools import pybool, pyint, pylist, pynone, pytuple, pyunicode

import attr
from six import next

proto_opcode_names = ["PROTO", "FRAME", "STOP", "GLOBAL", "STACK_GLOBAL"]

exec_opcode_names = [
    "INST",  # v0
    "OBJ",  # v1
    "REDUCE",
    "NEWOBJ",  # v2; [cls, args] -> [cls.__new__(*args)]
    "NEWOBJ_EX",  # v4; NEWOBJ, but with kwargs
    "BUILD",  # __setstate__ or __dict__ update
]

persid_opcode_names = ["PERSID", "BINPERSID"]

ext_opcode_names = ["EXT1", "EXT2", "EXT4"]

safe_opcode_names = [
    "INT",
    "BININT",
    "BININT1",
    "BININT2",
    "LONG",
    "LONG1",
    "LONG4",
    "STRING",
    "BINSTRING",
    "SHORT_BINSTRING",
    "BINBYTES",
    "SHORT_BINBYTES",
    "BINBYTES8",
    "NONE",
    "NEWTRUE",
    "NEWFALSE",
    "UNICODE",
    "SHORT_BINUNICODE",
    "BINUNICODE",
    "BINUNICODE8",
]

float_opcode_names = ["FLOAT", "BINFLOAT"]

list_opcode_names = ["EMPTY_LIST", "APPEND", "APPENDS", "LIST"]

tuple_opcode_names = ["EMPTY_TUPLE", "TUPLE", "TUPLE1", "TUPLE2", "TUPLE3"]

dict_opcode_names = ["EMPTY_DICT", "DICT", "SETITEM", "SETITEMS"]

set_opcode_names = ["EMPTY_SET", "ADDITEMS", "FROZENSET"]

stack_opcode_names = ["POP", "DUP", "MARK", "POP_MARK"]

memo_opcode_names = [
    "GET", "BINGET", "LONG_BINGET", "PUT", "BINPUT", "LONG_BINPUT", "MEMOIZE"
]

pickled_string = pyunicode
pickled_int = pyint
pickled_list = pylist
pickled_tuple = pytuple
pickled_bool = pybool
pickled_none = pynone


def _last(stack):
    if stack:
        return stack[-1]


def _rfind(stack, elem, default=None):
    """
    Like _find but starts from the back.
    """
    for i in reversed(range(len(stack))):
        if stack[i] == elem:
            return i
    else:
        return default


@attr.s(str=True)
class PickleException(RuntimeError):
    msg = attr.ib()


@attr.s(str=True)
class PickleParseException(PickleException):
    current_parse_entry = attr.ib()
    current_parse_result = attr.ib()


@attr.s(str=True)
class StackException(PickleException):
    pass


@attr.s(str=True)
class StackUnderflowException(StackException, PickleParseException):
    stackdepth = attr.ib()
    numtopop = attr.ib()


@attr.s(str=True)
class PickleTailException(PickleParseException):
    """
    The pickle has a tail (some content after the STOP instruction).
    """
    pickle_length = attr.ib()
    tail = attr.ib()


@attr.s(str=True)
class MemoException(PickleException):
    memoidx = attr.ib(default=None)


@attr.s
class _ParseResult(object):
    parsed = attr.ib(default=list)
    maxproto = attr.ib(default=None)
    stack = attr.ib(default=list)
    memo = attr.ib(default=dict)
    issues = attr.ib(default=list)
    global_objects = attr.ib(default=dict)


@attr.s
class _ParseEntry(object):
    op = attr.ib()
    arg = attr.ib()
    pos = attr.ib()
    stackslice = attr.ib()


def _just_the_instructions(pickle):
    """
    Get the instruction stream of a pickle.

    This is sort-of like genops, except genops occasionally errors out on
    certain structural pickle errors. We don't want that, because we want to
    figure out as much as we can about the pickle.
    """
    ops = pickletools.genops(pickle)
    while True:
        try:
            yield next(ops)
        except ValueError as e:
            if e.args == ("pickle exhausted before seeing STOP",):
                break
            else:
                raise
        except StopIteration:
            break


def _parse(pickle, fail_fast=False):
    """
    Parses a pickle into a sequence of opcodes. Walks through the opcodes to
    build the memo and pickle stack without actually executing anything.
    Produces a parse tree that includes opcodes, positions, the memo at the
    end, any errors that were encountered along the way. Each opcode is
    annotated with the stackslice it operates on (if any); for example: an
    APPENDS instruction will have the list, a mark object, and the elements
    being appended to a list.
    """
    parsed = []
    issues = []
    stack = []
    markstack = []
    stackslice = None
    memo = {}
    maxproto = -1
    op = arg = pos = None
    global_objects = {}

    def get_global_stack_object(arg, objtype=object):
        if arg not in global_objects:
            global_objects[arg] = StackObject(
                name=arg,
                obtype=objtype,
                doc="Object of type {typename}.".format(typename=arg),
            )
        return global_objects[arg]

    def _maybe_raise(E, msg, **kwargs):
        """
        Tiny helper for raising exceptions with lots of context.
        """
        entry = _ParseEntry(op=op, arg=arg, pos=pos, stackslice=stackslice)
        result = _ParseResult(
            parsed=parsed, maxproto=maxproto, stack=stack, memo=memo
        )
        issue = E(
            msg=msg,
            current_parse_entry=entry,
            current_parse_result=result,
            **kwargs
        )
        if fail_fast:
            raise issue
        else:
            issues.append(issue)

    for (op, arg, pos) in _just_the_instructions(pickle):
        markidx = stackslice = None
        top = _last(stack)
        maxproto = max(maxproto, op.proto)

        before, after = op.stack_before, op.stack_after
        numtopop = len(before)

        # Should we pop a MARK?
        if markobject in before or (op.name == "POP" and top is markobject):
            # instructions that take a stackslice claim to take only 1 object
            # off the stack, but that's really "anything up to a MARK
            # instruction" so it can be any number; this corrects the stack to
            # reflect that
            try:
                markstack.pop()  # markpos; position in the _opcode stream_
                markidx = _rfind(stack, markobject)  # position in the _stack_
                stack = stack[:markidx] + [markobject, stack[markidx + 1:]]
            except IndexError:
                _maybe_raise(StackException, "unexpected empty markstack")
            except ValueError:
                _maybe_raise(StackException, "expected markobject on stack")

        if op.name in ("PUT", "BINPUT", "LONG_BINPUT", "MEMOIZE"):
            memoidx = len(memo) if op.name == "MEMOIZE" else arg
            if memoidx in memo:
                _maybe_raise(
                    MemoException, "double memo assignment", memoidx=memoidx
                )
            elif not stack:
                _maybe_raise(
                    StackException, "empty stack when attempting to memoize"
                )
            elif stack[-1] is markobject:
                _maybe_raise(MemoException, "can't store markobject in memo")
            else:
                memo[memoidx] = stack[-1]
        elif op.name in ("GET", "BINGET", "LONG_BINGET"):
            try:
                after = [memo[arg]]
            except KeyError:
                _maybe_raise(MemoException, "missing memo element {arg}")
        elif op.name == "GLOBAL":
            after = [get_global_stack_object(arg)]

        if numtopop:
            if len(stack) >= numtopop:
                stackslice = stack[-numtopop:]
                del stack[-numtopop:]
            else:
                _maybe_raise(
                    StackUnderflowException,
                    msg="tried to pop more elements than the stack had",
                    stackdepth=len(stack),
                    numtopop=numtopop,
                )
        else:
            stackslice = None

        if op.name == "APPEND":
            list_object, addend = stackslice
            if issubclass(getattr(list_object, "obtype", object), list):
                base_list = []
            else:
                list_object, base_list = list_object
            after = [[list_object, base_list + [addend]]]
        elif op.name == "APPENDS":
            list_object, mo, stack_list = stackslice
            after = [[list_object, stack_list]]
        elif op.name == "LIST":
            after = [[pylist, []]]
        if op.name == "MARK":
            markstack.append(pos)

        if (
                len(after) == 1
                and stackslice
                and op.name not in ("APPEND", "LIST", "APPENDS")
        ):
            stack.append(stackslice)
        else:
            stack.extend(after)

        parsed.append(
            _ParseEntry(op=op, arg=arg, pos=pos, stackslice=stackslice)
        )

    if pos != (len(pickle) - 1):
        _maybe_raise(
            PickleTailException,
            msg="extra content after pickle end",
            pickle_length=len(pickle),
            tail=pickle[pos:],
        )

    return _ParseResult(
        parsed=parsed,
        stack=stack,
        maxproto=maxproto,
        memo=memo,
        issues=issues,
        global_objects=global_objects,
    )


@attr.s
class Brine(object):
    shape = attr.ib(default=None)
    maxproto = attr.ib(default=None)
    global_objects = attr.ib(default=dict)


def extract_brine(pickle):
    parsed = _parse(pickle)

    return Brine(
        maxproto=parsed.maxproto,
        shape=parsed.parsed[-1].stackslice[0],
        global_objects=parsed.global_objects,
    )


_critiquers = []


def _critiquer(f):
    """
    Decorator to add a critiquer fn.
    """
    if f not in _critiquers:
        _critiquers.append(f)
    return f


@_critiquer
def _ends_with_stop_instruction(parse_result):
    """
    The STOP opcode is the last thing in the stream.
    """
    if parse_result.parsed[-1].op.name != "STOP":
        raise PickleException("last opcode wasn't STOP")


@_critiquer
def _empty_stack(parse_result):
    if parse_result.stack:
        raise PickleException("stack not empty after last opcode")


@attr.s
class CritiqueReport(object):
    """
    A report of all the issues critiquing raised.
    """
    issues = attr.ib()


@attr.s(str=True)
class CritiqueException(RuntimeError):
    """
    An exception that says something bad happened in the critique.

    This is just a exception wrapper for CritiqueReport.
    """
    report = attr.ib()

    @classmethod
    def for_report(cls, *args, **kwargs):
        """
        Creates a CritiqueReport with given args, kwargs and wraps it with a
        CritiqueException, then returns that exception.
        """
        return cls(report=CritiqueReport(*args, **kwargs))


def critique(pickle, brine=None, fail_fast=True):
    """
    Critiques a pickle.
    """
    # optimize will fail on certain malformed pickles because it uses genops
    # internally which does that.
    try:
        optimized = pickletools.optimize(pickle)
    except ValueError as e:
        if e.args == ("pickle exhausted before seeing STOP",):
            optimized = pickle
        else:
            raise

    parse_result = _parse(optimized, fail_fast=fail_fast)
    issues = list(parse_result.issues)
    for critiquer in _critiquers:
        try:
            critiquer(parse_result)
        except PickleException as e:
            if fail_fast:
                raise
            else:
                issues.append(e)
    if issues:
        raise CritiqueException.for_report(issues=issues)
    else:
        return optimized


def sample(pickle):
    """
    Given a pickle, return an abstraction ("brine") that can be used to see if
    a different pickle has a sufficiently similar structure.
    """
    raise NotImplementedError()


def safe_loads(pickle, brine):
    """
    Loads a pickle as safely as possible by using as much information as
    possible from the given distillate.
    """
    raise NotImplementedError()

# Tasting notes:

# POP, POP_MARK never occur in legitimate pickles, but they are an effective
# way of hiding a malicious object (created for side effects) from the
# algorithm that checks if the stack is fully consumed.

# In optimized pickles, PUTs/GETs only exist to support recursive structures.
# They also exist in non-optimized pickles, so we should optimize the pickle
# first. DUP is never used, even though it could work the same way.

# declaredproto < maxproto
