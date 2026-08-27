"""Palette and typographic tokens for the report.

Values come from the validated reference palette: the eight categorical slots
pass the lightness, chroma, CVD-separation and normal-vision checks in both
light and dark mode (`validate_palette.js`). Three light-mode slots sit below
3:1 against the surface, so every multi-series chart in this report carries
direct labels and a table twin -- the documented relief for that warning.
"""
from __future__ import annotations

# Categorical slots, in fixed order. Assigned to assets once, never cycled.
CATEGORICAL_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                     "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
CATEGORICAL_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500",
                    "#d55181", "#008300", "#9085e9", "#e66767"]

# Sequential blue ramp (magnitude) and the diverging arms (polarity).
SEQUENTIAL = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
              "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281"]
DIVERGING_COOL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]
DIVERGING_WARM = ["#f7d5d5", "#efb0b0", "#e58585", "#d95c5c", "#c03a3a", "#9b2727"]
MIDPOINT_LIGHT = "#f0efec"
MIDPOINT_DARK = "#383835"

SURFACE_LIGHT = "#fcfcfb"
SURFACE_DARK = "#1a1a19"


def asset_color_index(keys: list[str]) -> dict[str, int]:
    """Freeze the slot each asset uses, so a filtered chart never repaints."""
    return {key: i % len(CATEGORICAL_LIGHT) for i, key in enumerate(keys)}
