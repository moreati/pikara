import pickletools as pt

import attr

from six import next


proto_opcode_names = ["PROTO", "FRAME", "STOP", "GLOBAL", "STACK_GLOBAL"]

exec_opcode_names = [
    "REDUCE",  # v0
    "INST",  # v0
    "OBJ",  # v1
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

pickled_string = pt.pyunicode
pickled_int = pt.pyint
pickled_int_or_bool = pt.pyinteger_or_bool  # p0 only
pickled_bool = pt.pybool
pickled_list = pt.pylist
pickled_tuple = pt.pytuple
pickled_dict = pt.pydict
pickled_none = pt.pynone


@attr.s(cmp=False)
class PickledObject(object):
    """
    An object in a Pickle stream with fuzzy equality constraints.
    """
    pickletools_type = attr.ib()
    value = attr.ib()

    def __eq__(self, other):
        if isinstance(other, PickledObject):
            return self.pickletools_type == other.pickletools_type
        else:
            return self.pickletools_type == other or self.value == other

    @classmethod
    def for_parsed_op(cls, op, arg):
        pickled_type, = op.stack_after
        artificial_values = {"NONE": None, "NEWTRUE": True, "NEWFALSE": False}
        if op.name in artificial_values:
            arg = artificial_values[op.name]

        return cls(pickletools_type=pickled_type, value=arg)


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
    """
    Something went wrong when attempting to parse a pickle.
    """
    current_parse_entry = attr.ib()
    current_parse_result = attr.ib()


@attr.s(str=True)
class StackException(PickleException):
    """
    During parsing or analysis, something went wrong with the stack.

    See subclasses for more specific stack issues.
    """


@attr.s(str=True)
class StackUnderflowException(StackException, PickleParseException):
    """
    During pickle parsing, the virtual stack underflowed (attempted to pop more
    items than were available).
    """
    stackdepth = attr.ib()
    numtopop = attr.ib()


@attr.s(str=True)
class MissingDictValueException(StackException, PickleParseException):
    """Attempted to create a new dictionary or add to an existing dictionary with
    an incorrect stack structure for doing so.

    DICT and SETITEMS require an even number of items in the stack slice (K1,
    V1, K2, V2...). This exception gets raised when there is an odd number of
    elements in the stack slice.

    SETITEM (singular) takes d, k, v off the stack, so it's not as obvious if
    the stack is malformed, unless it underflows, in which case
    StackUnderflowException is raised.

    """
    kvlist = attr.ib()


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
    parse_entries = attr.ib(default=list)
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


_globals_cache = {}


def _make_global(module_name, global_name):
    cached = _globals_cache.get((module_name, global_name))
    if cached is not None:
        return cached

    attrs = {
        "__new__": _Instance,
        "__module__": module_name,
        "__repr__": lambda _: "{}.{}".format(module_name, global_name),
    }
    t = type(global_name, (), attrs)
    _globals_cache[(module_name, global_name)] = t
    return t


@attr.s(init=False)
class _Instance(object):
    klass = attr.ib()
    args = attr.ib()
    kwargs = attr.ib()
    state = attr.ib()

    def __init__(self, klass, *args, **kwargs):
        self.klass = klass
        self.args = args
        self.kwargs = kwargs

    def __setstate__(self, state):
        self.state = state

    def __repr__(self):
        template = "{mod}.{cls}(args={a}, kwargs={kw}, state={state})"
        return template.format(
            mod=self.klass.__module__,
            cls=self.klass.__name__,
            a=self.args,
            kw=self.kwargs,
            state=self.state,
        )


def _just_the_instructions(pickle):
    """
    Get the instruction stream of a pickle.

    This is sort-of like genops, except genops occasionally errors out on
    certain structural pickle errors. We don't want that, because we want to
    figure out as much as we can about the pickle.
    """
    ops = pt.genops(pickle)
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
    parse_entries = []
    issues = []
    stack = []
    markstack = []
    stackslice = None
    memo = {}
    maxproto = -1
    op = arg = pos = None
    global_objects = {}

    def _maybe_raise(E, msg, **kwargs):
        """
        Tiny helper for raising exceptions with lots of context.
        """
        entry = _ParseEntry(op=op, arg=arg, pos=pos, stackslice=stackslice)
        result = _ParseResult(
            parse_entries=parse_entries, maxproto=maxproto, stack=stack, memo=memo
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
        if op.name == "MEMOIZE":
            # MEMOIZE annoyingly sets before = after = [any], but it doesn't
            # have a stack side effect. PUT/BINPUT do this correctly and set
            # before and after to be empty.
            # TODO: file a Python bug for this?
            before = after = []
        numtopop = len(before)

        # Should we pop a MARK?
        marked = pt.markobject in before
        poppable_mark = op.name == "POP" and top is pt.markobject
        if marked or poppable_mark:
            # instructions that take a stackslice claim to take only 1 object
            # off the stack, but that's really "anything up to a MARK
            # instruction" so it can be any number; this corrects the stack to
            # reflect that
            try:
                markstack.pop()  # markpos; position in the _opcode stream_
                markidx = _rfind(stack, pt.markobject)  # position in the stack
                stack = stack[:markidx] + [pt.markobject, stack[markidx + 1:]]
            except IndexError:
                _maybe_raise(StackException, "unexpected empty markstack")
            except ValueError:
                _maybe_raise(StackException, "expected markobject on stack")

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

        if op.name in ("PUT", "BINPUT", "LONG_BINPUT", "MEMOIZE"):
            memoidx = len(memo) if op.name == "MEMOIZE" else arg
            if memoidx in memo:
                _maybe_raise(
                    MemoException, "double memo assignment", memoidx=memoidx
                )
            elif not stack:
                _maybe_raise(StackException, "memoize with empty stack")
            elif stack[-1] is pt.markobject:
                _maybe_raise(MemoException, "can't store markobject in memo")
            else:
                memo[memoidx] = stack[-1]
        elif op.name in ("GET", "BINGET", "LONG_BINGET"):
            try:
                after = [memo[arg]]
            except KeyError:
                _maybe_raise(MemoException, "missing memo element", arg=arg)
        elif op.name == "GLOBAL":
            mod, name = arg.split(" ", 1)
            g = _make_global(mod, name)
            global_objects[(mod, name)] = g
            after = [g]
        elif op.name == "APPEND":
            list_obj, addend = stackslice
            after = [list_obj + [addend]]
        elif op.name == "APPENDS":
            list_object, markobject, stack_list = stackslice
            after = [list_object + stack_list]
        elif op.name == "LIST":
            markobject, stack_list = stackslice
            after = [stack_list]
        elif op.name == "EMPTY_LIST":
            after = [[]]
        elif op.name == "TUPLE":
            markobject, stack_list = stackslice
            after = [tuple(stack_list)]
        elif op.name.startswith("TUPLE"):  # TUPLEn
            after = [tuple(stackslice)]
        elif op.name == "EMPTY_TUPLE":
            after = [()]
        elif op.name in ("DICT", "SETITEMS"):
            if op.name == "DICT":
                d = {}
                markobject, kvlist = stackslice
            elif op.name == "SETITEMS":
                d, markobject, kvlist = stackslice
            kviter = iter(kvlist)
            try:
                for k in kviter:
                    d[k.value] = next(kviter)
            except StopIteration:
                _maybe_raise(
                    MissingDictValueException,
                    "uneven number of dict k, v entries",
                    kvlist=kvlist
                )
            after = [d]
        elif op.name == "EMPTY_DICT":
            after = [{}]
        elif op.name == "SETITEM":
            d, k, v = stackslice
            d[k.value] = v
            after = [d]
        elif op.name == "MARK":
            markstack.append(pos)
        elif op.name == "STOP":
            # STOP and POP don't add things back to the stack.
            after = []
        elif stackslice is not None:
            after = [stackslice]
        elif not before and len(after) == 1:  # new atom
            after = [PickledObject.for_parsed_op(op, arg)]

        stack.extend(after)
        parse_entries.append(
            _ParseEntry(op=op, arg=arg, pos=pos, stackslice=stackslice)
        )

    if pos != (len(pickle) - 1):
        _maybe_raise(
            PickleTailException,
            msg="extra content after pickle end",
            pickle_length=len(pickle),
            tail=pickle[pos + 1:],
        )

    return _ParseResult(
        parse_entries=parse_entries,
        stack=stack,
        maxproto=maxproto,
        memo=memo,
        issues=issues,
        global_objects=global_objects,
    )


@attr.s
class _Brine(object):
    """The essential characteristics of a pickle.

    This is essentially morally equivalent to a ParseResult, though a
    ParseResult may include additional internal details that shouldn't matter
    to a Brine. For example: the memo object.
    """
    shape = attr.ib(default=None)
    maxproto = attr.ib(default=None)
    global_objects = attr.ib(default=dict)


def _extract_brine(pickle, fail_fast=False):
    """Attempts to extract a brine from a (string) pickle.

    If the pickle has any issues that show up via parsing or critique, raises
    an exception.
    """
    parse_result = _parse(pickle, fail_fast=fail_fast)
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
        raise CritiqueException(issues=issues)
    return _Brine(
        maxproto=parse_result.maxproto,
        shape=parse_result.parse_entries[-1].stackslice[0],
        global_objects=parse_result.global_objects,
    )


_critiquers = set()


def _critiquer(f):
    """
    Decorator to add a critiquer fn.
    """
    _critiquers.add(f)
    return f


@_critiquer
def _ends_with_stop_instruction(parse_result):
    """
    The STOP opcode is the last thing in the stream.
    """
    if parse_result.parse_entries[-1].op.name != "STOP":
        raise PickleException("last opcode wasn't STOP")


@_critiquer
def _empty_stack(parse_result):
    if parse_result.stack:
        raise PickleException("stack not empty after last opcode")


@attr.s(str=True)
class CritiqueException(RuntimeError):
    """
    An exception that says something bad happened in the critique.
    """
    issues = attr.ib()


def critique(pickle, reference_brine=None, fail_fast=True):
    """
    Critiques a pickle.
    """
    _extract_brine(pickle, fail_fast=fail_fast)
    # TODO: compare against reference brine


def sample(pickle):
    """
    Given a pickle, return an abstraction ("brine") that can be used to see if
    a different pickle has a sufficiently similar structure.
    """
    return _extract_brine(pickle, fail_fast=True)


def safe_loads(pickle, reference_brine):
    """
    Loads a pickle as safely as possible by using as much information as
    possible from the given distillate.
    """
    raise NotImplementedError()


# Tasting notes:

# POP, POP_MARK never occur in legitimate pickles, but they are an effective
# way of hiding a malicious object (created for side effects) from the
# algorithm that checks if the stack is fully consumed.

# declaredproto < maxproto
