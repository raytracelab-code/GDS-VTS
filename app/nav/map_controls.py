"""Small, UI-independent state used by the NAV map controls."""

from dataclasses import dataclass


LAYER_VISIBILITY = {
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
