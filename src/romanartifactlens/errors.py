"""Exit-code exceptions.

0  completed; individual checks may still be NOT_EVALUATED
1  unexpected internal failure
2  invalid input (missing coordinates, bad shapes, inconsistent units)
3  unsupported datamodel or data level
4  an explicitly requested optional dependency is not installed
5  ``--strict`` and the packet is short of required evidence
"""

from __future__ import annotations


class RomanArtifactLensError(Exception):
    """Base error. ``exit_code`` is what the CLI returns."""

    exit_code = 1


class InvalidDataError(RomanArtifactLensError):
    """The inputs cannot be analysed as specified."""

    exit_code = 2


class UnsupportedDatamodelError(RomanArtifactLensError):
    """The file is not a supported Roman datamodel for this version."""

    exit_code = 3


class OptionalDependencyError(RomanArtifactLensError):
    """A requested extra (Roman I/O or STPSF) is not installed."""

    exit_code = 4


class PartialEvidenceError(RomanArtifactLensError):
    """``--strict`` refused a packet that still has required gaps."""

    exit_code = 5
