pikara
======

Safer pickles.

It's no secret Python's ``pickle`` module is unsafe. It's also enormously
popular. Most applications should really just use something else (like JSON).
Some really are best served by pickles, such as most uses of scientific Python.

This library can't fix the fundamental issues with pickle, but it can make
unpickling objects as safe as it ever is going to be. If you can, you should use
something else. If you can't, you should use this.

How does it work?
-----------------

This library gives you tools to specify a set of constraints around how a pickle
should behave and some general sniff checks for pickles. It then lets you apply
those checks to do entirely static analysis on a pickle on the one hand, as well
as apply some of the constraints to a real unpickler object so they're also
checked when you're actually unpickling.

**WARNING**: This project can't save you if the model pickles you give it do
something dangerous. For example, if you're saving a machine learning model that
includes a numpy ndarray, and it turns out ndarray actually has a code execution
vulnerability in it on deserialization, this package will not help you catch
that.

Misc
----

"Pikara" is the Maori word for pickle.
