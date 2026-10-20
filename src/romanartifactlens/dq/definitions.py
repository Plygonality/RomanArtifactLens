"""Pixel DQ names, bits, and review policies.

The installed ``roman_datamodels.dqflags.pixel`` table is authoritative when
that package is importable. The snapshot is the table in roman_datamodels
1.2.0, which matches the pixel column of the romancal reference-file DQ table
retrieved on 2026-10-16. Bit 14 is unnamed in both. GROUPDQ uses bit 7 for
``WFI18_TRANSIENT``; L2 image DQ uses that bit for ``OUTLIER``. This module
does not apply group-flag names to image DQ.
"""

from __future__ import annotations

from dataclasses import dataclass

# name -> value. GOOD (0) is intentionally absent.
DOCUMENTED_PIXEL_FLAGS: dict[str, int] = {
    "DO_NOT_USE": 2**0,
    "SATURATED": 2**1,
    "JUMP_DET": 2**2,
    "DROPOUT": 2**3,
    "GW_AFFECTED_DATA": 2**4,
    "PERSISTENCE": 2**5,
    "AD_FLOOR": 2**6,
    "OUTLIER": 2**7,
    "UNRELIABLE_ERROR": 2**8,
    "NON_SCIENCE": 2**9,
    "DEAD": 2**10,
    "HOT": 2**11,
    "WARM": 2**12,
    "LOW_QE": 2**13,
    "TELEGRAPH": 2**15,
    "NONLINEAR": 2**16,
    "BAD_REF_PIXEL": 2**17,
    "NO_FLAT_FIELD": 2**18,
    "NO_GAIN_VALUE": 2**19,
    "NO_LIN_CORR": 2**20,
    "NO_SAT_CHECK": 2**21,
    "UNRELIABLE_BIAS": 2**22,
    "UNRELIABLE_DARK": 2**23,
    "UNRELIABLE_SLOPE": 2**24,
    "UNRELIABLE_FLAT": 2**25,
    "RESERVED_5": 2**26,
    "RESERVED_6": 2**27,
    "UNRELIABLE_RESET": 2**28,
    "RESERVED_7": 2**29,
    "OTHER_BAD_PIXEL": 2**30,
    "REFERENCE_PIXEL": 2**31,
}

SNAPSHOT_ID = "roman_datamodels-1.2.0-pixel-dq-2026-10-16"
SNAPSHOT_NOTE = (
    "Documented snapshot of roman_datamodels.dqflags.pixel from version 1.2.0, "
    "cross-checked with the romancal reference-file DQ table. Bit 14 is unassigned. "
    "RC, inverse-RC, and open-pixel families described in the Roman DQ handbook are "
    "not separate names in this enum."
)

# How a set bit should be talked about. This is not a severity score.
POLICIES: dict[str, str] = {
    "DO_NOT_USE": "EXCLUSION",
    "SATURATED": "EXPOSURE_CONDITION",
    "JUMP_DET": "EXPOSURE_CONDITION",
    "DROPOUT": "EXPOSURE_CONDITION",
    "GW_AFFECTED_DATA": "EXPOSURE_CONDITION",
    "PERSISTENCE": "EXPOSURE_CONDITION",
    "AD_FLOOR": "EXPOSURE_CONDITION",
    "OUTLIER": "EXPOSURE_CONDITION",
    "UNRELIABLE_ERROR": "RELIABILITY",
    "NON_SCIENCE": "GEOMETRIC",
    "DEAD": "DETECTOR_REFERENCE",
    "HOT": "DETECTOR_REFERENCE",
    "WARM": "DETECTOR_REFERENCE",
    "LOW_QE": "DETECTOR_REFERENCE",
    "TELEGRAPH": "DETECTOR_REFERENCE",
    "NONLINEAR": "DETECTOR_REFERENCE",
    "BAD_REF_PIXEL": "DETECTOR_REFERENCE",
    "NO_FLAT_FIELD": "DETECTOR_REFERENCE",
    "NO_GAIN_VALUE": "DETECTOR_REFERENCE",
    "NO_LIN_CORR": "DETECTOR_REFERENCE",
    "NO_SAT_CHECK": "DETECTOR_REFERENCE",
    "UNRELIABLE_BIAS": "RELIABILITY",
    "UNRELIABLE_DARK": "RELIABILITY",
    "UNRELIABLE_SLOPE": "RELIABILITY",
    "UNRELIABLE_FLAT": "RELIABILITY",
    "RESERVED_5": "RESERVED",
    "RESERVED_6": "RESERVED",
    "UNRELIABLE_RESET": "RELIABILITY",
    "RESERVED_7": "RESERVED",
    "OTHER_BAD_PIXEL": "DETECTOR_REFERENCE",
    "REFERENCE_PIXEL": "GEOMETRIC",
}

FLAG_MEANINGS: dict[str, str] = {
    "DO_NOT_USE": (
        "Pipeline bit recommending that the pixel be left out of science measurements, "
        "including when it is combined with other bits. It does not name a single physical cause."
    ),
    "SATURATED": (
        "The exposure-level saturation step recorded saturation. Saturated pixels can distort "
        "shape and brightness. The flag does not classify the candidate."
    ),
    "JUMP_DET": (
        "Ramp fitting recorded a jump. Jumps are associated with cosmic-ray hits and with other "
        "discontinuities. A jump flag does not prove that this candidate is a cosmic ray."
    ),
    "DROPOUT": "Data were marked lost in transmission.",
    "GW_AFFECTED_DATA": (
        "The pixel lies in a region affected by the guide-window readout. "
        "The handbook notes that this condition is one of those that may also set DO_NOT_USE."
    ),
    "PERSISTENCE": "High persistence was flagged (this bit was previously reserved).",
    "AD_FLOOR": "The pixel was flagged as below the A/D floor.",
    "OUTLIER": (
        "Pixel DQ bit 7: flagged by outlier detection. This is not the GROUPDQ WFI18_TRANSIENT bit."
    ),
    "UNRELIABLE_ERROR": "The quoted uncertainty was flagged as unreliable.",
    "NON_SCIENCE": "The pixel is not on the science portion of the detector.",
    "DEAD": "Reference data marked the pixel dead.",
    "HOT": "Reference data marked the pixel hot.",
    "WARM": "Reference data marked the pixel warm.",
    "LOW_QE": "Reference data marked the pixel as low quantum efficiency.",
    "TELEGRAPH": "Reference data marked the pixel as a telegraph pixel.",
    "NONLINEAR": "The pixel was marked highly nonlinear.",
    "BAD_REF_PIXEL": "A reference pixel was marked unusable.",
    "NO_FLAT_FIELD": "A flat field could not be measured.",
    "NO_GAIN_VALUE": "A gain could not be measured.",
    "NO_LIN_CORR": "A linearity correction was not available.",
    "NO_SAT_CHECK": "A saturation check was not available.",
    "UNRELIABLE_BIAS": "Bias variance was marked large.",
    "UNRELIABLE_DARK": "Dark variance was marked large.",
    "UNRELIABLE_SLOPE": "Slope variance was marked large.",
    "UNRELIABLE_FLAT": "Flat variance was marked large.",
    "RESERVED_5": "Reserved bit. No scientific meaning is assigned.",
    "RESERVED_6": "Reserved bit. No scientific meaning is assigned.",
    "UNRELIABLE_RESET": "The pixel was marked sensitive to the reset anomaly.",
    "RESERVED_7": "Reserved bit. No scientific meaning is assigned.",
    "OTHER_BAD_PIXEL": "Catch-all bad-pixel bit. The specific cause is not in the flag name.",
    "REFERENCE_PIXEL": "The pixel is a reference pixel.",
}


@dataclass(frozen=True)
class FlagBit:
    name: str
    value: int
    bit: int
    policy: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "value": self.value,
            "bit": self.bit,
            "policy": self.policy,
            "meaning": FLAG_MEANINGS.get(self.name, ""),
        }


@dataclass(frozen=True)
class FlagDictionary:
    flags: tuple[FlagBit, ...]
    source: str
    package_version: str | None
    snapshot_matches_installed: bool | None
    notes: tuple[str, ...]

    def by_name(self) -> dict[str, FlagBit]:
        return {flag.name: flag for flag in self.flags}

    def known_mask(self) -> int:
        mask = 0
        for flag in self.flags:
            mask |= flag.value
        return mask & 0xFFFFFFFF

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "package_version": self.package_version,
            "snapshot_id": SNAPSHOT_ID,
            "snapshot_matches_installed": self.snapshot_matches_installed,
            "notes": list(self.notes),
            "flags": [flag.to_dict() for flag in self.flags],
        }


def _bits_from_mapping(mapping: dict[str, int]) -> tuple[FlagBit, ...]:
    flags: list[FlagBit] = []
    for name, value in mapping.items():
        if name == "GOOD" or int(value) == 0:
            continue
        ivalue = int(value)
        if ivalue < 0 or ivalue > 0xFFFFFFFF or (ivalue & (ivalue - 1)) != 0:
            # A flag value that is not a single bit is preserved under its name
            # only when it is a single bit. Multi-bit aliases are rejected so
            # they cannot hide unknown bits.
            continue
        flags.append(
            FlagBit(
                name=name,
                value=ivalue,
                bit=ivalue.bit_length() - 1,
                policy=POLICIES.get(name, "UNLISTED"),
            )
        )
    flags.sort(key=lambda flag: flag.bit)
    return tuple(flags)


def documented_dictionary() -> FlagDictionary:
    return FlagDictionary(
        flags=_bits_from_mapping(DOCUMENTED_PIXEL_FLAGS),
        source="documented_snapshot",
        package_version=None,
        snapshot_matches_installed=None,
        notes=(SNAPSHOT_NOTE, "roman_datamodels was not imported; the snapshot was used."),
    )


def load_flag_dictionary() -> FlagDictionary:
    """Prefer the installed enum. Fall back to the verified snapshot."""

    try:
        from importlib.metadata import version

        from roman_datamodels import dqflags
    except ImportError:
        return documented_dictionary()

    installed: dict[str, int] = {}
    for member in dqflags.pixel:
        installed[member.name] = int(member.value)
    installed.pop("GOOD", None)
    package_version = version("roman_datamodels")
    matches = installed == DOCUMENTED_PIXEL_FLAGS
    notes = [
        SNAPSHOT_NOTE,
        "Named flags were read from roman_datamodels.dqflags.pixel at runtime.",
    ]
    if not matches:
        notes.append(
            "The installed enum differs from the roman_datamodels 1.2.0 snapshot. "
            "Installed names are used. Bits the installed enum does not name stay UNKNOWN_DQ_BIT."
        )
    return FlagDictionary(
        flags=_bits_from_mapping(installed),
        source="roman_datamodels.dqflags.pixel",
        package_version=package_version,
        snapshot_matches_installed=matches,
        notes=tuple(notes),
    )
