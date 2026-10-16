"""Analysis settings. Defaults are policies, not hidden classifications."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AnalysisSettings:
    """Knobs that change numerical evidence. They are copied into the manifest."""

    aperture_radius_px: float = 8.0
    annulus_inner_px: float | None = None
    annulus_outer_px: float | None = None
    dq_policy: str = "exclude_do_not_use"
    background: str = "sigma_clip_median"
    background_sigma: float = 3.0
    min_background_pixels: int = 30
    psf_adapter: str = "none"
    psf_sigma_px: float | None = None
    morphology_nsigma: float = 5.0
    coordinate_tolerance_arcsec: float = 0.05
    strict: bool = False

    def annulus_inner(self) -> float:
        if self.annulus_inner_px is None:
            return float(self.aperture_radius_px)
        return float(self.annulus_inner_px)

    def annulus_outer(self) -> float:
        if self.annulus_outer_px is None:
            return float(self.aperture_radius_px) * 2.0
        return float(self.annulus_outer_px)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["annulus_inner_px_effective"] = self.annulus_inner()
        payload["annulus_outer_px_effective"] = self.annulus_outer()
        return payload

    def validate(self) -> None:
        from romanartifactlens.errors import InvalidDataError

        if self.aperture_radius_px <= 0:
            raise InvalidDataError("aperture radius must be positive")
        if self.annulus_inner() < 0 or self.annulus_outer() <= self.annulus_inner():
            raise InvalidDataError("annulus outer radius must exceed the inner radius")
        if self.dq_policy not in {"exclude_do_not_use", "exclude_nonzero", "include_all"}:
            raise InvalidDataError(
                "dq policy must be exclude_do_not_use, exclude_nonzero, or include_all"
            )
        if self.background not in {"sigma_clip_median", "median"}:
            raise InvalidDataError("background estimator must be sigma_clip_median or median")
        if self.min_background_pixels < 1:
            raise InvalidDataError("min background pixels must be at least 1")
        if self.psf_adapter not in {"none", "synthetic-gaussian", "stpsf"}:
            raise InvalidDataError("psf adapter must be none, synthetic-gaussian, or stpsf")
        if self.morphology_nsigma <= 0:
            raise InvalidDataError("morphology nsigma must be positive")
