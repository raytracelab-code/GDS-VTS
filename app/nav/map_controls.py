"""Small, UI-independent state used by the NAV map controls."""

from dataclasses import dataclass


LAYER_VISIBILITY = {
    "Squall Alerts": ("squall-current", "squall-direction", "squall-trajectories", "squall-impact-zones-fill", "squall-impact-zones-outline", "squall-surveillance-zones-fill", "squall-surveillance-zones-outline", "squall-prediction-points", "squall-eta", "squall-selection-point", "squall-selection-line", "squall-selection-outline"),
    "Vessel": ("vessel",),
    "Track": ("track", "track-start"),
    "Heading / COG": ("heading-vector", "cog-vector"),
    "Site Boundary": ("site-boundary-fill", "site-boundary-line"),
    "Pipelines": ("pipelines-fill", "pipelines-line"),
    "Anchor Pattern": ("anchor-patterns-fill", "anchor-patterns-line", "anchor-patterns-point"),
    "Survey Areas": ("survey-areas-fill", "survey-areas-line"),
    "Operational Zones": ("operational-zones-fill", "operational-zones-line"),
}


@dataclass
class FollowController:
    """Follow is intentionally opt-in and does not alter vessel data."""

    enabled: bool = False

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def disable(self) -> None:
        self.enabled = False
