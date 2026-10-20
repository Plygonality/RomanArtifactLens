"""Bitwise DQ decoding. Equality with a single integer is never used."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from romanartifactlens.dq.definitions import FlagDictionary


@dataclass(frozen=True)
class DecodedValue:
    raw: int
    flags: tuple[str, ...]
    unknown_bits: tuple[int, ...]
    components: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "raw": self.raw,
            "flags": list(self.flags),
            "unknown_bits": list(self.unknown_bits),
            "components": [dict(item) for item in self.components],
        }


def _as_uint32(value: int) -> int:
    return int(np.uint32(int(value)))


def decompose(value: int, dictionary: FlagDictionary) -> DecodedValue:
    """Split one DQ integer into named bits and unnamed bits.

    ``DO_NOT_USE`` combined with other bits is reported as every set bit, not as
    a single code equal to the sum.
    """

    raw = _as_uint32(value)
    components: list[dict[str, object]] = []
    names: list[str] = []
    known = np.uint32(dictionary.known_mask())
    for flag in dictionary.flags:
        bit = np.uint32(flag.value)
        if raw & int(bit):
            names.append(flag.name)
            components.append(
                {
                    "name": flag.name,
                    "bit": flag.bit,
                    "value": flag.value,
                    "policy": flag.policy,
                }
            )
    unknown_bits: list[int] = []
    leftover = np.uint32(raw) & ~known
    for bit_index in range(32):
        bit_value = np.uint32(1 << bit_index)
        if int(leftover & bit_value):
            unknown_bits.append(bit_index)
            components.append(
                {
                    "name": f"UNKNOWN_DQ_BIT_{bit_index}",
                    "bit": bit_index,
                    "value": int(bit_value),
                    "policy": "UNKNOWN",
                }
            )
    return DecodedValue(
        raw=raw,
        flags=tuple(names),
        unknown_bits=tuple(unknown_bits),
        components=tuple(components),
    )


def summarize_region(
    dq: np.ndarray,
    mask: np.ndarray,
    dictionary: FlagDictionary,
) -> dict[str, object]:
    """Count named and unknown bits on the True pixels of ``mask``."""

    selected = np.asarray(dq)[mask]
    count = int(selected.size)
    if count == 0:
        return {
            "n_pixels": 0,
            "flag_counts": {},
            "flag_fractions": {},
            "unknown_bit_counts": {},
            "do_not_use_count": 0,
            "do_not_use_fraction": None,
            "any_flag_count": 0,
            "raw_min": None,
            "raw_max": None,
        }
    values = selected.astype(np.uint32, copy=False)
    flag_counts: dict[str, int] = {}
    flag_fractions: dict[str, float] = {}
    for flag in dictionary.flags:
        bit = np.uint32(flag.value)
        n_flag = int(np.count_nonzero(values & bit))
        if n_flag:
            flag_counts[flag.name] = n_flag
            flag_fractions[flag.name] = n_flag / count
    known = np.uint32(dictionary.known_mask())
    leftover = values & ~known
    unknown_bit_counts: dict[str, int] = {}
    for bit_index in range(32):
        bit_value = np.uint32(1 << bit_index)
        if int(bit_value) & int(known):
            continue
        n_flag = int(np.count_nonzero(leftover & bit_value))
        if n_flag:
            unknown_bit_counts[str(bit_index)] = n_flag
    do_not_use = flag_counts.get("DO_NOT_USE", 0)
    return {
        "n_pixels": count,
        "flag_counts": flag_counts,
        "flag_fractions": flag_fractions,
        "unknown_bit_counts": unknown_bit_counts,
        "do_not_use_count": do_not_use,
        "do_not_use_fraction": do_not_use / count,
        "any_flag_count": int(np.count_nonzero(values)),
        "raw_min": int(values.min()),
        "raw_max": int(values.max()),
    }
