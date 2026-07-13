"""Errors the pipeline raises deliberately.

The API maps these to 4xx. Anything not derived from NormalizeError is a bug and is
reported as 500 — which is why builtin exception types are never mapped: KeyError and
ValueError are raised by library and internal code as readily as by validation, and a
blanket mapping reports our own failures as the caller's.
"""

from __future__ import annotations


class NormalizeError(Exception):
    """Base for every deliberate, caller-facing error."""


class InvalidRequestError(NormalizeError):
    """The request itself is invalid, independent of the source file."""


class SourceError(InvalidRequestError):
    """The source file cannot be read as declared."""


class InstanceNotFoundError(NormalizeError):
    """No run exists for the requested instance id."""


class InvalidStateError(NormalizeError):
    """The run is not in a state where the requested phase can run."""
