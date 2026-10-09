"""Deterministic publication figures and an auditable figure registry.

SVG is always retained. With the research extra, Matplotlib writes matching
SVG and PNG views; PNG is the registry entry point for parent-template
rendering. Every empirical figure is descriptive: its caption records the
population, unit, aggregation, sample size, uncertainty policy, and limits of
interpretation. Renderer-generated SVG companions are post-processed to carry
the same ``role="img"``/``<title>``/``<desc>`` accessibility metadata as the
hand-drawn fallback SVGs, and the denominator-aware ``proportion-intervals``
figure ships a hash-bound point-data sidecar referenced by its registry entry.
"""

from __future__ import annotations

import html
import json
import math
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .research import (
    EvaluationReport,
    _report_content_hash,
    _report_payload_hash,
)
from .statistics import DEFAULT_POLICY
from .utils import (
    jsonable,
    provenance_path,
    sha256_bytes,
    sha256_text,
    write_json_atomic,
    write_text_atomic,
)

FIGURE_SCHEMA_VERSION = 4
READABLE_FIGURE_SCHEMA_VERSIONS = (1, 2, 3, FIGURE_SCHEMA_VERSION)
FIGURE_GENERATOR = "skillarum.figures:v4"
# Okabe-Ito-inspired colors remain legible in grayscale when paired with the
# direct value labels and strong dark outlines used below.
PALETTE = ("#0072b2", "#d55e00", "#009e73", "#cc79a7", "#e69f00", "#56b4e9")
INK = "#172033"
GRID = "#cbd5e1"


@dataclass(frozen=True)
class FigureRecord:
    """Registry record for one generated figure and its evidence surface."""

    figure_id: str
    title: str
    path: str
    raster_path: str | None
    source_data: str
    source_sha256: str
    artifact_sha256: str
    raster_sha256: str | None
    generator: str
    caption: str
    alt_text: str
    units: str
    aggregation: str
    evidence_origin: str
    sample_size: int
    sample_size_basis: str
    uncertainty: str
    limitations: tuple[str, ...]
    manuscript_refs: tuple[str, ...]
    report_id: str = ""
    denominator: str = ""
    data_path: str | None = None
    data_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


def _svg_start(
    title: str, description: str, width: int = 1100, height: int = 620
) -> list[str]:
    escaped_title = html.escape(title)
    escaped_description = html.escape(description)
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escaped_title}</title>',
        f'<desc id="desc">{escaped_description}</desc>',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        "<style>"
        f"text{{font-family:Arial,sans-serif;fill:{INK}}} "
        ".title{font-size:24px;font-weight:700} .subtitle{font-size:14px} "
        ".label{font-size:15px} .small{font-size:12px} .tick{font-size:11px} "
        f".axis{{stroke:{INK};stroke-width:1.5}} .grid{{stroke:{GRID};stroke-width:1}} "
        f".box{{stroke:{INK};stroke-width:2;rx:12}}",
        "</style>",
        f'<text x="55" y="42" class="title">{escaped_title}</text>',
    ]


def _svg_end(lines: list[str]) -> str:
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _box(
    lines: list[str], x: int, y: int, width: int, height: int, label: str, color: str
) -> None:
    lines.append(
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" class="box" fill="{color}"/>'
    )
    wrapped = textwrap.wrap(label, width=17)[:2] or [label]
    first_y = y + height / 2 - (len(wrapped) - 1) * 9
    for index, line in enumerate(wrapped):
        lines.append(
            f'<text x="{x + width / 2:.0f}" y="{first_y + index * 19:.0f}" '
            f'text-anchor="middle" class="label">{html.escape(line)}</text>'
        )


def _flow_figure(title: str, labels: list[str], subtitle: str, description: str) -> str:
    lines = _svg_start(title, description)
    y = 220
    width = 150 if len(labels) <= 5 else 135
    gap = 38 if len(labels) <= 5 else 22
    for index, label in enumerate(labels):
        x = 48 + index * (width + gap)
        _box(lines, x, y, width, 78, label, "#d9f2ec" if index % 2 == 0 else "#dceafe")
        if index < len(labels) - 1:
            next_x = x + width + 7
            lines.append(
                f'<path d="M {next_x} {y + 39} L {next_x + gap - 13} {y + 39}" '
                'stroke="#334155" stroke-width="3" marker-end="url(#arrow)"/>'
            )
    lines.insert(
        4,
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" '
        'orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#334155"/></marker></defs>',
    )
    lines.append(
        f'<text x="55" y="365" class="subtitle">{html.escape(subtitle)}</text>'
    )
    return _svg_end(lines)


def _format_value(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}".rstrip("0").rstrip(".") if value % 1 else f"{int(value)}"


def _all_integral(values: list[float | None]) -> bool:
    """True when every recorded value is a whole number (counts, not ratios)."""
    recorded = [value for value in values if value is not None]
    return bool(recorded) and all(float(value).is_integer() for value in recorded)


def _axis_ticks(maximum: float, *, integral: bool) -> list[float]:
    """Five-or-fewer ticks; whole-number steps whenever the data are counts.

    Fractional ticks on a count axis (0.25, 0.5, …) misstate the unit, and a
    percent axis must never suggest values above 100. When the step grid
    misses the maximum, the maximum itself becomes the final tick so the top
    gridline meets the tallest bar instead of floating below it.
    """
    if not integral:
        return [maximum * tick / 4 for tick in range(5)]
    top = max(int(math.ceil(maximum)), 1)
    step = max(1, math.ceil(top / 5))
    ticks = [float(value) for value in range(0, top + 1, step)]
    if ticks[-1] != top and len(ticks) < 6:
        ticks.append(float(top))
    return ticks


def _percent_ticks() -> list[float]:
    return [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]


def _bar_figure(
    title: str,
    labels: list[str],
    values: list[float],
    y_label: str,
    subtitle: str,
    description: str,
    *,
    maximum: float | None = None,
) -> str:
    lines = _svg_start(title, description)
    left, top, chart_width, chart_height = 100, 125, 900, 345
    maximum = max(
        maximum
        if maximum is not None
        else max([value for value in values if value is not None] or [0.0]),
        1.0,
    )
    integral = _all_integral(values)
    for tick_value in _axis_ticks(maximum, integral=integral):
        fraction = tick_value / maximum if maximum else 0.0
        y = top + chart_height - chart_height * fraction
        lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_width}" y2="{y:.1f}" class="grid"/>'
        )
        lines.append(
            f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="tick">{_format_value(tick_value)}</text>'
        )
    lines.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_height}" class="axis"/>'
    )
    lines.append(
        f'<line x1="{left}" y1="{top + chart_height}" x2="{left + chart_width}" y2="{top + chart_height}" class="axis"/>'
    )
    lines.append(
        f'<text x="27" y="{top + chart_height / 2}" transform="rotate(-90 27 {top + chart_height / 2})" '
        f'class="small">{html.escape(y_label)}</text>'
    )
    slot = chart_width / max(len(labels), 1)
    bar_width = min(132, max(26, slot * 0.58))
    for index, (label, value) in enumerate(zip(labels, values)):
        height = chart_height * max(value or 0, 0) / maximum
        x = left + index * slot + (slot - bar_width) / 2
        y = top + chart_height - height
        # One hue for a single series: color must not imply a second variable.
        color = PALETTE[0]
        # A minimum-width outline makes a measured zero visible rather than an
        # apparently missing category.
        if value is None:
            pass  # unavailable values have an N/A label and no quantitative mark
        elif value == 0:
            lines.append(
                f'<circle cx="{x + bar_width / 2:.1f}" cy="{top + chart_height:.1f}" r="4" fill="{color}"/>'
            )
        else:
            lines.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{height:.1f}" '
                f'fill="{color}" stroke="{INK}" stroke-width="0.7" rx="4"/>'
            )
        label_y = max(y - 9, top - 7)
        lines.append(
            f'<text x="{x + bar_width / 2:.1f}" y="{label_y:.1f}" text-anchor="middle" class="small">{_format_value(value)}</text>'
        )
        wrapped = textwrap.wrap(label, width=18)[:3] or [label]
        for line_index, line in enumerate(wrapped):
            lines.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{top + chart_height + 25 + line_index * 15}" '
                f'text-anchor="middle" class="small">{html.escape(line)}</text>'
            )
    lines.append(
        f'<text x="55" y="565" class="subtitle">{html.escape(subtitle)}</text>'
    )
    return _svg_end(lines)


def _grouped_bar_figure(
    title: str,
    categories: list[str],
    series: dict[str, list[float]],
    y_label: str,
    subtitle: str,
    description: str,
    *,
    maximum: float | None = None,
    percent: bool = False,
) -> str:
    """Render a directly labelled grouped comparison without hiding zeros."""
    lines = _svg_start(title, description)
    left, top, chart_width, chart_height = 110, 150, 880, 315
    all_values = [
        value for values in series.values() for value in values if value is not None
    ]
    scale = max(maximum if maximum is not None else max(all_values or [0.0]), 1.0)
    tick_values = (
        _percent_ticks()
        if percent
        else _axis_ticks(scale, integral=_all_integral(all_values))
    )
    for tick_value in tick_values:
        fraction = tick_value / scale if scale else 0.0
        y = top + chart_height - chart_height * fraction
        lines.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_width}" y2="{y:.1f}" class="grid"/>'
        )
        label = f"{tick_value:.0f}%" if percent else _format_value(tick_value)
        lines.append(
            f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="tick">{label}</text>'
        )
    lines.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + chart_height}" class="axis"/>'
    )
    lines.append(
        f'<line x1="{left}" y1="{top + chart_height}" x2="{left + chart_width}" y2="{top + chart_height}" class="axis"/>'
    )
    lines.append(
        f'<text x="27" y="{top + chart_height / 2}" transform="rotate(-90 27 {top + chart_height / 2})" '
        f'class="small">{html.escape(y_label)}</text>'
    )
    legend_x = left
    for index, label in enumerate(series):
        color = PALETTE[index % len(PALETTE)]
        lines.append(
            f'<rect x="{legend_x}" y="90" width="14" height="14" fill="{color}" stroke="{INK}" stroke-width="0.6"/>'
        )
        lines.append(
            f'<text x="{legend_x + 20}" y="102" class="small">{html.escape(label)}</text>'
        )
        legend_x += max(130, len(label) * 7 + 38)
    group_width = chart_width / max(len(categories), 1)
    series_count = max(len(series), 1)
    bar_width = min(34, max(12, group_width / (series_count + 1) * 0.7))
    for category_index, category in enumerate(categories):
        group_left = left + category_index * group_width
        for series_index, (series_name, values) in enumerate(series.items()):
            value = values[category_index] if category_index < len(values) else None
            height = chart_height * max(value or 0, 0) / scale
            x = (
                group_left
                + group_width / 2
                + (series_index - (series_count - 1) / 2) * (bar_width + 4)
                - bar_width / 2
            )
            y = top + chart_height - height
            color = PALETTE[series_index % len(PALETTE)]
            if value is None:
                pass  # N/A is distinct from a measured zero
            elif value == 0:
                lines.append(
                    f'<circle cx="{x + bar_width / 2:.1f}" cy="{top + chart_height:.1f}" r="3.5" fill="{color}"/>'
                )
            else:
                lines.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{height:.1f}" fill="{color}" stroke="{INK}" stroke-width="0.6" rx="3"/>'
                )
            label = (
                f"{value:.0f}%"
                if percent and value is not None
                else _format_value(value)
            )
            lines.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{max(y - 7, top - 5):.1f}" text-anchor="middle" class="tick">{label}</text>'
            )
        wrapped = textwrap.wrap(category, width=16)[:3] or [category]
        for line_index, line in enumerate(wrapped):
            lines.append(
                f'<text x="{group_left + group_width / 2:.1f}" y="{top + chart_height + 25 + line_index * 15}" text-anchor="middle" class="small">{html.escape(line)}</text>'
            )
    lines.append(
        f'<text x="55" y="565" class="subtitle">{html.escape(subtitle)}</text>'
    )
    return _svg_end(lines)


def _accessible_svg(path: Path, title: str, description: str) -> None:
    """Insert role/title/desc metadata into a renderer-generated SVG file.

    The hand-drawn fallback SVGs already carry this metadata; renderer output
    does not, so the accessibility story must not depend on which optional
    dependency produced the file.
    """
    text = path.read_text(encoding="utf-8")
    if "<svg" not in text or 'role="img"' in text:
        return
    start = text.index("<svg")
    end = text.index(">", start)
    injected = (
        ' role="img" aria-labelledby="fig-title fig-desc">'
        f'<title id="fig-title">{html.escape(title)}</title>'
        f'<desc id="fig-desc">{html.escape(description)}</desc>'
    )
    write_text_atomic(path, text[:end] + injected + text[end + 1 :])


def _maybe_png(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float],
    y_label: str,
    subtitle: str,
    description: str = "",
) -> Path | None:
    """Emit a high-resolution PNG when the optional plotting extra is installed."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    horizontal = (
        len(labels) > 4 or max((len(label) for label in labels), default=0) > 18
    )
    height = max(4.0, len(labels) * 0.62 + 2.2) if horizontal else 4.6
    figure, axis = plt.subplots(figsize=(11, height), constrained_layout=False)
    figure.subplots_adjust(
        left=0.27 if horizontal else 0.12,
        right=0.98,
        top=0.88,
        bottom=0.28 if horizontal else 0.30,
    )
    figure.patch.set_facecolor("white")
    axis.set_facecolor("white")
    figure.suptitle(title, x=0.04, y=0.98, ha="left", fontweight="bold", fontsize=15)
    maximum = max(max([value for value in values if value is not None] or [0.0]), 1.0)
    # One hue for a single series: color must not imply a second variable.
    color = PALETTE[0]
    integral = _all_integral(values)
    axis_ticks = _axis_ticks(maximum, integral=integral)
    all_zero = bool(values) and all(
        value is not None and value == 0 for value in values
    )
    # An all-zero record gets a minimal unit span: a 20% headroom axis would
    # suggest a magnitude the data do not show.
    axis_span = (
        1.0
        if all_zero
        else (max(math.ceil(maximum), 1) * 1.2 if integral else maximum * 1.2)
    )
    zero_positions = [
        index for index, value in enumerate(values) if value is not None and value == 0
    ]
    # Measured zeros are labelled above their baseline marker instead of on
    # top of it; bar_label would print the label straight onto the marker.
    value_labels = [
        "" if (value is not None and value == 0) else _format_value(value)
        for value in values
    ]
    zero_label_offset = axis_span * 0.05
    if horizontal:
        positions = list(range(len(labels)))
        bars = axis.barh(
            positions, [value or 0 for value in values], color=color, edgecolor=INK
        )
        axis.set_yticks(
            positions, ["\n".join(textwrap.wrap(label, 32)) for label in labels]
        )
        axis.invert_yaxis()
        axis.set_xlabel(y_label)
        axis.set_ylabel("")
        axis.grid(axis="x", alpha=0.35, color=GRID)
        axis.set_xlim(0, axis_span)
        if integral:
            axis.set_xticks(axis_ticks)
        axis.bar_label(
            bars,
            labels=value_labels,
            padding=3,
            fontsize=9,
        )
        if zero_positions:
            axis.plot(
                [0] * len(zero_positions),
                zero_positions,
                linestyle="none",
                marker="o",
                markersize=5.5,
                markerfacecolor="none",
                markeredgecolor=color,
                markeredgewidth=1.2,
                zorder=3,
            )
            for position in zero_positions:
                axis.text(
                    zero_label_offset,
                    position,
                    "0",
                    ha="left",
                    va="center",
                    fontsize=9,
                    color=INK,
                )
    else:
        bars = axis.bar(
            labels, [value or 0 for value in values], color=color, edgecolor=INK
        )
        axis.bar_label(
            bars,
            labels=value_labels,
            padding=3,
            fontsize=9,
        )
        if zero_positions:
            axis.plot(
                zero_positions,
                [0] * len(zero_positions),
                linestyle="none",
                marker="o",
                markersize=5.5,
                markerfacecolor="none",
                markeredgecolor=color,
                markeredgewidth=1.2,
                zorder=3,
            )
            for position in zero_positions:
                axis.text(
                    position,
                    zero_label_offset,
                    "0",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                    color=INK,
                )
        axis.set_ylabel(y_label)
        axis.tick_params(axis="x", labelrotation=20)
        axis.grid(axis="y", alpha=0.35, color=GRID)
        axis.set_ylim(0, axis_span)
        if integral:
            axis.set_yticks(axis_ticks)
    if values and all(value == 0 for value in values):
        axis.text(
            0.5,
            0.6,
            "All recorded values are zero",
            transform=axis.transAxes,
            ha="center",
            color=INK,
            fontsize=11,
        )
    axis.set_axisbelow(True)
    figure.text(
        0.04,
        0.015,
        "\n".join(textwrap.wrap(subtitle, 108)),
        fontsize=11,
        va="bottom",
        color=INK,
    )
    figure.savefig(
        path,
        dpi=300,
        metadata={"Creator": "Skillarum", "Title": title},
        facecolor="white",
        edgecolor="white",
        transparent=False,
    )
    svg_path = path.with_suffix(".svg")
    with matplotlib.rc_context({"svg.hashsalt": "skillarum", "svg.fonttype": "none"}):
        figure.savefig(svg_path, metadata={"Date": None, "Creator": "Skillarum"})
    _accessible_svg(svg_path, title, description or subtitle)
    plt.close(figure)
    if not path.is_file():
        raise RuntimeError(f"figure raster was not generated: {path}")
    return path


def _maybe_grouped_png(
    path: Path,
    title: str,
    categories: list[str],
    series: dict[str, list[float]],
    y_label: str,
    subtitle: str,
    description: str = "",
    *,
    maximum: float | None = None,
    percent: bool = False,
) -> Path | None:
    """Render a grouped raster companion when the optional research extra exists."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None
    figure, axis = plt.subplots(figsize=(11, 4.6), constrained_layout=False)
    figure.subplots_adjust(left=0.12, right=0.98, top=0.75, bottom=0.27)
    positions = np.arange(len(categories), dtype=float)
    width = 0.78 / max(len(series), 1)
    scale = max(
        maximum
        if maximum is not None
        else max(
            (
                max([value for value in values if value is not None] or [0.0])
                for values in series.values()
            ),
            default=0.0,
        ),
        1.0,
    )
    zero_x: list[float] = []
    for index, (label, values) in enumerate(series.items()):
        bar_x = positions + (index - (len(series) - 1) / 2) * width
        bars = axis.bar(
            bar_x,
            [value or 0 for value in values],
            width=width,
            label=label,
            color=PALETTE[index % len(PALETTE)],
            edgecolor=INK,
        )
        labels = [
            ""
            if value is not None and value == 0
            else (
                f"{value:.0f}%"
                if percent and value is not None
                else _format_value(value)
            )
            for value in values
        ]
        axis.bar_label(bars, labels=labels, padding=2, fontsize=7)
        for x_position, value in zip(bar_x, values):
            if value is not None and value == 0:
                zero_x.append(float(x_position))
    figure.suptitle(title, x=0.04, y=0.98, ha="left", fontweight="bold", fontsize=15)
    axis.set_xticks(
        positions, ["\n".join(textwrap.wrap(label, 24)) for label in categories]
    )
    axis.set_ylabel(y_label)
    if percent:
        axis.set_ylim(0, 108)
        axis.set_yticks(_percent_ticks())
        axis.set_yticklabels([f"{tick:.0f}%" for tick in _percent_ticks()])
    else:
        recorded = [
            value
            for series_values in series.values()
            for value in series_values
            if value is not None
        ]
        integral = _all_integral(recorded)
        all_zero = bool(recorded) and all(value == 0 for value in recorded)
        axis.set_ylim(
            0,
            1.0
            if all_zero
            else max(math.ceil(scale), 1) * 1.2
            if integral
            else scale * 1.2,
        )
        if integral:
            axis.set_yticks(_axis_ticks(scale, integral=True))
    axis.grid(axis="y", alpha=0.35, color=GRID)
    if zero_x:
        axis.plot(
            zero_x,
            [0] * len(zero_x),
            linestyle="none",
            marker="o",
            markersize=5.5,
            markerfacecolor="none",
            markeredgecolor=INK,
            markeredgewidth=1.1,
            zorder=3,
        )
        for x_position in zero_x:
            axis.text(
                x_position,
                0.03 * axis.get_ylim()[1] if axis.get_ylim()[1] else 0.03,
                "0",
                ha="center",
                va="bottom",
                fontsize=7,
                color=INK,
            )
    axis.legend(
        frameon=False,
        ncol=min(len(series), 3),
        loc="lower left",
        bbox_to_anchor=(0, 1.02),
    )
    if series and all(
        values and all(value == 0 for value in values) for values in series.values()
    ):
        axis.text(
            0.5,
            0.6,
            "All recorded counts are zero",
            transform=axis.transAxes,
            ha="center",
            color=INK,
            fontsize=11,
        )
    axis.set_axisbelow(True)
    figure.text(
        0.04,
        0.015,
        "\n".join(textwrap.wrap(subtitle, 108)),
        fontsize=11,
        va="bottom",
        color=INK,
    )
    figure.savefig(
        path,
        dpi=300,
        metadata={"Creator": "Skillarum", "Title": title},
        facecolor="white",
        edgecolor="white",
        transparent=False,
    )
    svg_path = path.with_suffix(".svg")
    with matplotlib.rc_context({"svg.hashsalt": "skillarum", "svg.fonttype": "none"}):
        figure.savefig(svg_path, metadata={"Date": None, "Creator": "Skillarum"})
    _accessible_svg(svg_path, title, description or subtitle)
    plt.close(figure)
    if not path.is_file():
        raise RuntimeError(f"figure raster was not generated: {path}")
    return path


def _maybe_structural_png(
    path: Path,
    title: str,
    labels: list[str],
    subtitle: str,
    description: str = "",
) -> Path | None:
    """Render the same readable structural scene to PNG and SVG."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch
    except ImportError:
        return None
    figure, axis = plt.subplots(figsize=(11, 4.2))
    figure.subplots_adjust(left=0.02, right=0.98, top=0.82, bottom=0.17)
    axis.set(xlim=(0, 11), ylim=(0, 3))
    axis.axis("off")
    figure.suptitle(title, x=0.04, y=0.97, ha="left", fontsize=16, fontweight="bold")
    width, gap = 1.40, (10.5 - 1.40 * len(labels)) / max(len(labels) - 1, 1)
    centers = []
    for index, label in enumerate(labels):
        x = 0.25 + index * (width + gap)
        centers.append(x + width / 2)
        axis.add_patch(
            FancyBboxPatch(
                (x, 1.65),
                width,
                0.60,
                boxstyle="round,pad=0.025",
                facecolor="#e7eff5",
                edgecolor=INK,
            )
        )
        axis.text(
            x + width / 2, 1.95, label, ha="center", va="center", fontsize=10, color=INK
        )
        if index:
            axis.annotate(
                "",
                (x - 0.03, 1.95),
                (x - gap + 0.03, 1.95),
                arrowprops={"arrowstyle": "->", "color": INK},
            )
    if path.stem == "pipeline-trust-boundaries":
        for left, right, label in (
            (1, 2, "Provider boundary"),
            (2, 3, "Draft validation"),
        ):
            boundary = (centers[left] + centers[right]) / 2
            axis.plot(
                [boundary, boundary],
                [1.1, 2.55],
                color=INK,
                linestyle="--",
                linewidth=1,
            )
            axis.text(boundary, 0.85, label, ha="center", fontsize=9, color=INK)
        axis.text(
            (centers[0] + centers[1]) / 2,
            0.3,
            "Untrusted source data",
            ha="center",
            fontsize=9,
        )
        axis.text(
            (centers[3] + centers[4]) / 2,
            0.3,
            "Validated structure; source claims remain untrusted",
            ha="center",
            fontsize=8,
        )
    if path.stem == "run-state-machine":
        axis.plot(
            [centers[0], centers[-1]],
            [1.12, 1.12],
            color=INK,
            linestyle="--",
            linewidth=1,
        )
        for x in centers:
            axis.plot([x, x], [1.65, 1.12], color=INK, linestyle="--", linewidth=1)
        axis.annotate(
            "", (5.5, 0.72), (5.5, 1.12), arrowprops={"arrowstyle": "->", "color": INK}
        )
        axis.add_patch(
            FancyBboxPatch(
                (4.8, 0.13),
                1.4,
                0.58,
                boxstyle="round,pad=0.025",
                facecolor="#fff3df",
                edgecolor=INK,
            )
        )
        axis.text(5.5, 0.42, "failed", ha="center", va="center", fontsize=10)
        axis.text(
            0.25,
            0.45,
            "Caught exception; diagnostic write requires writable storage",
            fontsize=8,
        )
        axis.annotate(
            "next target",
            (centers[0], 2.3),
            (centers[-1], 2.55),
            fontsize=8,
            arrowprops={
                "arrowstyle": "->",
                "connectionstyle": "arc3,rad=0.12",
                "color": INK,
            },
        )
    figure.text(
        0.04,
        0.02,
        "\n".join(textwrap.wrap(subtitle, 95)),
        fontsize=11,
        color=INK,
    )
    figure.savefig(path, dpi=300, metadata={"Creator": "Skillarum"})
    svg_path = path.with_suffix(".svg")
    with matplotlib.rc_context({"svg.hashsalt": "skillarum", "svg.fonttype": "none"}):
        figure.savefig(svg_path, metadata={"Date": None, "Creator": "Skillarum"})
    _accessible_svg(svg_path, title, description or subtitle)
    plt.close(figure)
    if not path.is_file():
        raise RuntimeError(f"figure raster was not generated: {path}")
    return path


def _area_name(observation: Any) -> str:
    declared_area = str(getattr(observation, "area", "")).strip()
    if declared_area:
        return {
            "Active-Inference-Institute": "Active Inference Institute",
            "Math4Wisdom": "Math4Wisdom",
        }.get(declared_area, declared_area.replace("-", " "))
    known = {
        "math4wisdom": "Math4Wisdom",
        "active-inference-institute": "Active Inference Institute",
    }
    profile_id = str(getattr(observation, "profile_id", "unknown"))
    return known.get(profile_id, profile_id.replace("-", " ").title())


def _area_rows(report: EvaluationReport) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for observation in report.observations:
        area = _area_name(observation)
        row = grouped.setdefault(
            area,
            {
                "area": area,
                "targets": set(),
                "observations": 0,
                "accepted_pages": 0,
                "truncated_pages": 0,
                "coverage": 0,
                "source_total": 0,
            },
        )
        row["targets"].add(observation.target_id)
        row["observations"] += 1
        row["accepted_pages"] += observation.accepted_pages
        row["truncated_pages"] += observation.truncated_pages
        row["coverage"] += observation.source_coverage_pages
        row["source_total"] += observation.source_page_total
    rows = []
    for row in sorted(grouped.values(), key=lambda item: item["area"].casefold()):
        total = int(row["source_total"])
        row["targets"] = len(row["targets"])
        row["mapping"] = (
            f"{row['coverage']}/{total} ({row['coverage'] / total:.0%})"
            if total
            else "not available"
        )

        rows.append(row)
    return rows


PER_TARGET_FIGURE_LIMIT = 40


def _per_target_observations(report: EvaluationReport) -> tuple[Any, int]:
    """Observations for one-row-per-target figures, and how many were left out.

    Up to ``PER_TARGET_FIGURE_LIMIT`` observations are all drawn. Beyond that a
    per-target chart is unreadable, so only observations of declared evaluation
    cases are drawn; the rest still count in every area-level figure. If no
    observation is a declared case, all are drawn rather than none.
    """
    observations = tuple(report.observations)
    if len(observations) <= PER_TARGET_FIGURE_LIMIT:
        return observations, 0
    declared = tuple(
        item for item in observations if item.metadata.get("declared_case")
    )
    if not declared:
        return observations, 0
    return declared, len(observations) - len(declared)


def _omission_note(omitted: int) -> str:
    if not omitted:
        return ""
    return (
        f" Only declared evaluation cases are drawn; {omitted} further completed "
        "observations of undeclared (index-derived) targets are counted in the "
        "area-level figures and the report."
    )


def _latency_series(report: EvaluationReport) -> tuple[list[str], list[float | None]]:
    """Per-observation latency labels and values, grouped by area then target.

    Report order interleaves areas; the figure reads better when bars for the
    same source area sit together. Sorting is deterministic and every value
    stays bound to its own observation label.
    """
    selected, _ = _per_target_observations(report)
    ordered = sorted(selected, key=lambda item: (_area_name(item), item.target_id))
    labels = [
        f"{_area_name(item)} / {item.target_id.replace('-', ' ').title()}"
        for item in ordered
    ]
    values: list[float | None] = [
        None
        if "generation_duration_ms" in item.metadata.get("missing_metrics", [])
        else float(item.generation_duration_ms)
        for item in ordered
    ]
    return labels or ["no observations"], values or [None]


def _area_telemetry(report: EvaluationReport) -> list[dict[str, Any]]:
    """Aggregate page/request telemetry while retaining every denominator."""
    grouped: dict[str, dict[str, Any]] = {}
    for observation in report.observations:
        area = _area_name(observation)
        row = grouped.setdefault(
            area,
            {
                "area": area,
                "accepted": 0,
                "rejected": 0,
                "redirects": 0,
                "canonicalized": 0,
                "duplicates": 0,
                "truncated": 0,
                "requests": 0,
                "response_bytes": 0,
                "coverage": 0,
                "source_total": 0,
                "observations": 0,
            },
        )
        row["accepted"] += observation.accepted_pages
        row["rejected"] += observation.rejected_requests
        row["redirects"] += observation.redirect_count
        row["canonicalized"] += observation.canonical_count
        row["duplicates"] += observation.duplicate_count
        row["truncated"] += observation.truncated_pages
        row["requests"] += observation.request_count
        row["requests_missing"] = row.get(
            "requests_missing", False
        ) or "request_count" in observation.metadata.get("missing_metrics", [])
        row["response_bytes"] += observation.response_bytes
        row["coverage"] += observation.source_coverage_pages
        row["source_total"] += observation.source_page_total
        row["observations"] += 1
    return [grouped[key] for key in sorted(grouped, key=str.casefold)]


def _report_context(report: EvaluationReport) -> str:
    source_types = (
        report.summary.get("source_types", {})
        if isinstance(report.summary, dict)
        else {}
    )
    origins = (
        ", ".join(
            f"{label}={int(source_types.get(label, 0))}"
            for label in ("fixture", "live", "unknown")
            if int(source_types.get(label, 0))
        )
        or "none"
    )
    return f"n={len(report.observations)} completed observations; evidence origins: {origins}"


def _area_matrix_figure(report: EvaluationReport) -> str:
    rows = _area_rows(report)
    title = "Skill catalog by source area"
    description = "A table groups completed target observations by declared source area and reports accepted pages, truncation, and page-level provenance mapping."
    lines = _svg_start(title, description, height=480)
    lines.append(
        f'<text x="55" y="78" class="subtitle">n={len(report.observations)} completed observations; rows are descriptive groupings, not site-coverage estimates.</text>'
    )
    columns = (
        (55, "source area"),
        (470, "targets"),
        (590, "observations"),
        (745, "accepted pages"),
        (900, "truncated"),
        (1000, "mapping"),
    )
    for x, label in columns:
        lines.append(
            f'<text x="{x}" y="135" class="small" font-weight="700">{html.escape(label)}</text>'
        )
    lines.append('<line x1="45" y1="148" x2="1060" y2="148" class="axis"/>')
    for index, row in enumerate(rows):
        y = 180 + index * 72
        fill = "#eef8f5" if index % 2 == 0 else "#eff5fd"
        lines.append(
            f'<rect x="45" y="{y - 28}" width="1015" height="58" fill="{fill}" rx="8"/>'
        )
        values = (
            row["area"],
            row["targets"],
            row["observations"],
            row["accepted_pages"],
            row["truncated_pages"],
            row["mapping"],
        )
        for (x, _), value in zip(columns, values):
            lines.append(
                f'<text x="{x}" y="{y + 5}" class="label">{html.escape(str(value))}</text>'
            )
    if not rows:
        lines.append(
            '<text x="55" y="195" class="label">No completed observations</text>'
        )
    lines.append(
        '<text x="55" y="425" class="subtitle">Mapping is source pages with complete URL and content/text hashes divided by observed source pages.</text>'
    )
    return _svg_end(lines)


def _maybe_area_png(
    path: Path, report: EvaluationReport, description: str = ""
) -> Path | None:
    """Export a legible catalog table from the same scene to PNG and SVG."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    rows = _area_rows(report)
    figure, axis = plt.subplots(figsize=(11, max(3.5, 2.2 + len(rows) * 0.45)))
    axis.axis("off")
    figure.subplots_adjust(left=0.03, right=0.97, top=0.75, bottom=0.25)
    figure.suptitle(
        "Skill catalog by source area",
        x=0.04,
        y=0.97,
        ha="left",
        fontsize=16,
        fontweight="bold",
    )
    figure.text(0.04, 0.84, _report_context(report), fontsize=11, color=INK)
    values = [
        [
            row["area"],
            row["targets"],
            row["observations"],
            row["accepted_pages"],
            row["truncated_pages"],
            row["mapping"],
        ]
        for row in rows
    ]
    if values:
        table = axis.table(
            cellText=values,
            colLabels=[
                "Source area",
                "Targets",
                "Observations",
                "Accepted pages",
                "Truncated",
                "Mapping",
            ],
            colWidths=[0.35, 0.09, 0.13, 0.14, 0.11, 0.18],
            cellLoc="center",
            bbox=[0, 0, 1, 1],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        for (row, column), cell in table.get_celld().items():
            cell.set_edgecolor(GRID)
            cell.set_linewidth(0.5)
            cell.set_facecolor(
                "#e7eff5" if row == 0 else ("#eef8f5" if row % 2 else "#eff5fd")
            )
            if row == 0:
                cell.set_text_props(weight="bold")
            if column == 0:
                cell.set_text_props(ha="left")
    else:
        axis.text(0.02, 0.5, "No completed observations", fontsize=12)
    figure.text(
        0.04,
        0.08,
        "Mapping = source pages with complete URL/content/text hashes divided by observed source pages.",
        fontsize=11,
        color=INK,
    )
    figure.savefig(path, dpi=300, metadata={"Creator": "Skillarum"})
    svg_path = path.with_suffix(".svg")
    with matplotlib.rc_context({"svg.hashsalt": "skillarum", "svg.fonttype": "none"}):
        figure.savefig(svg_path, metadata={"Date": None, "Creator": "Skillarum"})
    _accessible_svg(
        svg_path,
        "Skill catalog by source area",
        description
        or "A table of targets, observations, accepted pages, truncation, and mapping by source area.",
    )
    plt.close(figure)
    if not path.is_file():
        raise RuntimeError(f"figure raster was not generated: {path}")
    return path


def _confidence_label(report: EvaluationReport) -> str:
    """Human label for the report's interval confidence level.

    The level is policy, not typography: it comes from the report's recorded
    statistics policy when present and from the package default otherwise, so
    captions cannot drift from the intervals they describe.
    """
    summary = report.summary if isinstance(report.summary, dict) else {}
    policy = summary.get("policy") or summary.get("statistics_policy")
    confidence = None
    if isinstance(policy, dict) and isinstance(policy.get("confidence"), (int, float)):
        confidence = float(policy["confidence"])
    if confidence is None:
        confidence = DEFAULT_POLICY.confidence
    return f"{confidence * 100:.12g}%"


_PROPORTION_LABELS: tuple[tuple[str, str, str], ...] = (
    ("package_valid", "Package valid", "completed observations"),
    ("provenance_complete", "Provenance complete", "completed observations"),
    (
        "required_sections_valid",
        "Required portable sections valid",
        "completed observations",
    ),
    (
        "unsafe_source_preserved",
        "Untrusted source marker preserved",
        "completed observations",
    ),
    ("fallback_used", "Fallback used", "observations with fallback telemetry"),
    ("source_coverage", "Source pages completely mapped", "observed source pages"),
)


def _proportion_rows(report: EvaluationReport) -> list[dict[str, Any]]:
    """Project the report's exact-binomial proportion records for plotting.

    Rows reuse the report's own successes, totals, rates, and Clopper–Pearson
    intervals verbatim; figures.py never recomputes or relabels them. Each row
    carries its eligible denominator basis because the denominators differ.
    """
    proportions = (
        report.summary.get("proportions", {})
        if isinstance(report.summary, dict)
        else {}
    )
    rows: list[dict[str, Any]] = []
    for key, label, basis in _PROPORTION_LABELS:
        record = proportions.get(key) if isinstance(proportions, dict) else None
        if not isinstance(record, dict):
            continue
        rate = record.get("rate")
        interval = record.get("exact_95_interval")
        rows.append(
            {
                "key": key,
                "label": label,
                "denominator_basis": basis,
                "successes": int(record.get("successes", 0)),
                "total": int(record.get("total", 0)),
                "rate": float(rate) if rate is not None else None,
                "percent": 100.0 * float(rate) if rate is not None else None,
                "exact_95_interval": (
                    [float(interval[0]), float(interval[1])] if interval else None
                ),
            }
        )
    return rows


def _point_data(
    root: Path,
    figure_id: str,
    rows: list[dict[str, Any]],
    *,
    report: EvaluationReport,
    source_path: Path,
    units: str,
    denominator: str,
    notes: tuple[str, ...] = (),
) -> tuple[str, str] | tuple[None, None]:
    """Write the plotted point data as a hash-bound machine-readable sidecar.

    The returned registry-relative path and SHA-256 bind the plotted numbers
    to the source report without requiring anyone to parse SVG geometry.
    """
    if not rows:
        return None, None
    relative = f"figure_data/{figure_id}.json"
    path = root / "figure_data" / f"{figure_id}.json"
    write_json_atomic(
        path,
        {
            "schema_version": 1,
            "figure_id": figure_id,
            "generator": FIGURE_GENERATOR,
            "report_id": report.report_id,
            "source_data": provenance_path(source_path, root.parent),
            "source_sha256": sha256_bytes(source_path.read_bytes()),
            "units": units,
            "denominator": denominator,
            "notes": list(notes),
            "rows": rows,
        },
    )
    return relative, sha256_bytes(path.read_bytes())


def _interval_figure(
    title: str,
    rows: list[dict[str, Any]],
    subtitle: str,
    description: str,
) -> str:
    """Draw one dot-and-line per proportion with its exact binomial interval."""
    left, right, top, row_height = 300, 940, 168, 56
    if rows:
        bottom = top + row_height * len(rows)
    else:
        bottom = top + row_height
    height = max(430, bottom + 96)
    lines = _svg_start(title, description, height=height)

    def px(percent: float) -> float:
        return left + (right - left) * percent / 100.0

    lines.append(
        f'<text x="{(left + right) / 2:.0f}" y="{top - 34}" text-anchor="middle" '
        'class="small">percent of each row\'s eligible denominator</text>'
    )
    for tick in range(0, 101, 25):
        x = px(tick)
        lines.append(
            f'<line x1="{x:.1f}" y1="{top - 14}" x2="{x:.1f}" y2="{bottom + 6}" class="grid"/>'
        )
        lines.append(
            f'<text x="{x:.1f}" y="{bottom + 26}" text-anchor="middle" class="tick">{tick}%</text>'
        )
    lines.append(
        f'<line x1="{left}" y1="{top - 14}" x2="{left}" y2="{bottom + 6}" class="axis"/>'
    )
    if not rows:
        lines.append(
            f'<text x="{left + 6}" y="{top + row_height / 2:.0f}" class="small">'
            "No proportion records in this report</text>"
        )
    for index, row in enumerate(rows):
        y = top + index * row_height + row_height / 2
        wrapped = textwrap.wrap(str(row["label"]), width=28)[:2] or [str(row["label"])]
        label_y = y - (len(wrapped) - 1) * 9
        for line_index, line in enumerate(wrapped):
            lines.append(
                f'<text x="{left - 14}" y="{label_y + line_index * 18:.0f}" '
                f'text-anchor="end" class="small">{html.escape(line)}</text>'
            )
        basis = str(row.get("denominator_basis", "")).strip()
        if basis and basis != "none":
            lines.append(
                f'<text x="{left - 14}" y="{label_y + len(wrapped) * 18:.0f}" '
                f'text-anchor="end" class="tick" fill="#5b6472">'
                f"denominator: {html.escape(basis)}</text>"
            )
        if row["total"] == 0 or row["percent"] is None:
            lines.append(
                f'<text x="{left + 6}" y="{y + 5:.1f}" class="small">'
                "no eligible denominator (n=0)</text>"
            )
            continue
        interval = row["exact_95_interval"] or (row["rate"], row["rate"])
        lo_x, hi_x, point_x = (
            px(100 * interval[0]),
            px(100 * interval[1]),
            px(row["percent"]),
        )
        lines.append(
            f'<line x1="{lo_x:.1f}" y1="{y:.1f}" x2="{hi_x:.1f}" y2="{y:.1f}" '
            f'stroke="{INK}" stroke-width="2.5"/>'
        )
        for cap_x in (lo_x, hi_x):
            lines.append(
                f'<line x1="{cap_x:.1f}" y1="{y - 7:.1f}" x2="{cap_x:.1f}" y2="{y + 7:.1f}" '
                f'stroke="{INK}" stroke-width="2"/>'
            )
        lines.append(
            f'<circle cx="{point_x:.1f}" cy="{y:.1f}" r="5.5" fill="{PALETTE[0]}" '
            f'stroke="{INK}" stroke-width="1"/>'
        )
        note = f"{_format_value(row['percent'])}% ({row['successes']}/{row['total']})"
        if hi_x <= right - 150:
            lines.append(
                f'<text x="{hi_x + 10:.1f}" y="{y + 5:.1f}" text-anchor="start" '
                f'class="small">{html.escape(note)}</text>'
            )
        else:
            lines.append(
                f'<text x="{point_x:.1f}" y="{y - 13:.1f}" text-anchor="middle" '
                f'class="small">{html.escape(note)}</text>'
            )
    lines.append(
        f'<text x="55" y="{height - 24}" class="subtitle">{html.escape(subtitle)}</text>'
    )
    return _svg_end(lines)


def _maybe_interval_png(
    path: Path,
    title: str,
    rows: list[dict[str, Any]],
    subtitle: str,
    description: str = "",
) -> Path | None:
    """Render the proportion-interval scene to PNG and a matched SVG."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    figure, axis = plt.subplots(
        figsize=(11, max(3.6, 0.62 * max(len(rows), 1) + 2.2)),
        constrained_layout=False,
    )
    figure.subplots_adjust(left=0.34, right=0.97, top=0.84, bottom=0.24)
    figure.suptitle(title, x=0.04, y=0.98, ha="left", fontweight="bold", fontsize=15)
    positions: list[int] = []
    labels: list[str] = []
    for index, row in enumerate(rows):
        y = index
        positions.append(y)
        labels.append("\n".join(textwrap.wrap(str(row["label"]), 30)))
        if row["total"] == 0 or row["percent"] is None:
            axis.text(
                1.5,
                y,
                "no eligible denominator (n=0)",
                fontsize=8.5,
                va="center",
                color=INK,
            )
            continue
        interval = row["exact_95_interval"] or (row["rate"], row["rate"])
        lo_pct, hi_pct = 100.0 * interval[0], 100.0 * interval[1]
        axis.errorbar(
            [row["percent"]],
            [y],
            xerr=[
                [max(row["percent"] - lo_pct, 0.0)],
                [max(hi_pct - row["percent"], 0.0)],
            ],
            fmt="o",
            color=PALETTE[0],
            ecolor=INK,
            elinewidth=1.6,
            capsize=4,
            capthick=1.6,
            markersize=6,
        )
        note = f"{_format_value(row['percent'])}% ({row['successes']}/{row['total']})"
        if hi_pct <= 86:
            axis.text(hi_pct + 2, y, note, fontsize=8, va="center", ha="left")
        else:
            axis.text(lo_pct - 2, y, note, fontsize=8, va="center", ha="right")
    axis.set_yticks(positions, labels)
    for index, row in enumerate(rows):
        basis = str(row.get("denominator_basis", "")).strip()
        if basis and basis != "none":
            label_lines = len(textwrap.wrap(str(row["label"]), 30))
            offset = 0.18 + 0.22 * label_lines
            axis.text(
                -0.01,
                index + offset,
                f"denominator: {basis}",
                transform=axis.get_yaxis_transform(),
                ha="right",
                va="top",
                fontsize=7,
                color="#5b6472",
            )
    # Keep endpoint markers fully visible while labeling the probability scale.
    axis.set_xlim(-2, 102)
    axis.set_xticks(range(0, 101, 20))
    axis.set_ylim(-0.75, max(len(rows) - 0.25, 0.75))
    axis.invert_yaxis()
    axis.grid(axis="x", alpha=0.35, color=GRID)
    axis.set_axisbelow(True)
    axis.set_xlabel("percent of each row's eligible denominator")
    if not rows:
        axis.text(
            0.5,
            0.5,
            "No proportion records in this report",
            transform=axis.transAxes,
            ha="center",
            color=INK,
            fontsize=11,
        )
    figure.text(
        0.04,
        0.015,
        "\n".join(textwrap.wrap(subtitle, 108)),
        fontsize=11,
        va="bottom",
        color=INK,
    )
    figure.savefig(
        path,
        dpi=300,
        metadata={"Creator": "Skillarum", "Title": title},
        facecolor="white",
        edgecolor="white",
        transparent=False,
    )
    svg_path = path.with_suffix(".svg")
    with matplotlib.rc_context({"svg.hashsalt": "skillarum", "svg.fonttype": "none"}):
        figure.savefig(svg_path, metadata={"Date": None, "Creator": "Skillarum"})
    _accessible_svg(svg_path, title, description or subtitle)
    plt.close(figure)
    if not path.is_file():
        raise RuntimeError(f"figure raster was not generated: {path}")
    return path


def _overlap_rows(report: EvaluationReport) -> list[dict[str, Any]] | None:
    """Per-target source-URL rows for the shared-pages matrix.

    The only inputs are the persisted ``metadata.source_urls`` lists. A target
    whose list is not recorded is carried as an unavailable row and column
    (N/A), never dropped. Returns None — the same gating pattern as the review
    rubric figure — when fewer than two observations carry a list at all.
    """
    selected, _ = _per_target_observations(report)
    ordered = sorted(selected, key=lambda item: (_area_name(item), item.target_id))
    rows: list[dict[str, Any]] = []
    for item in ordered:
        urls = item.metadata.get("source_urls")
        rows.append(
            {
                "target": item.target_id.replace("-", " ").title(),
                "area": _area_name(item),
                "urls": (
                    sorted({str(url) for url in urls})
                    if isinstance(urls, list)
                    else None
                ),
            }
        )
    if sum(row["urls"] is not None for row in rows) < 2:
        return None
    return rows


def _overlap_cell(rows: list[dict[str, Any]], first: int, second: int) -> int | None:
    """Exact |A ∩ B| for two targets; None when either list is unavailable."""
    first_urls = rows[first]["urls"]
    second_urls = rows[second]["urls"]
    if first_urls is None or second_urls is None:
        return None
    return len(set(first_urls) & set(second_urls))


def _overlap_matrix_svg(
    title: str,
    rows: list[dict[str, Any]],
    subtitle: str,
    description: str,
) -> str:
    """Draw the shared-URL matrix with printed counts and explicit N/A cells."""
    size = len(rows)
    cell, gutter_left, gutter_top = 58, 300, 132
    width = gutter_left + size * cell + 60
    height = gutter_top + size * cell + 120
    lines = _svg_start(title, description, width=width, height=height)
    lines.append(
        f'<text x="{gutter_left - 12}" y="{gutter_top - 96}" text-anchor="end" '
        'class="small">column target \u2192</text>'
    )
    for index, row in enumerate(rows):
        center = gutter_left + index * cell + cell / 2
        top_y = gutter_top - 18
        lines.append(
            f'<text x="{center:.0f}" y="{top_y}" text-anchor="end" class="tick" '
            f'transform="rotate(-40 {center:.0f} {top_y})">{html.escape(str(row["target"]))}</text>'
        )
        label_y = gutter_top + index * cell + cell / 2
        lines.append(
            f'<text x="{gutter_left - 12}" y="{label_y - 3:.0f}" text-anchor="end" '
            f'class="small">{html.escape(str(row["target"]))}</text>'
        )
        lines.append(
            f'<text x="{gutter_left - 12}" y="{label_y + 14:.0f}" text-anchor="end" '
            f'class="tick" fill="#5b6472">{html.escape(str(row["area"]))}</text>'
        )
    for row_index in range(size):
        for column_index in range(size):
            value = _overlap_cell(rows, row_index, column_index)
            x = gutter_left + column_index * cell
            y = gutter_top + row_index * cell
            diagonal = row_index == column_index
            fill = "#cfe3f7" if diagonal else "#eef5fc"
            lines.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="{fill}" stroke="{GRID}" stroke-width="1"/>'
            )
            text_color = "#5b6472" if value is None else INK
            content = "N/A" if value is None else str(value)
            lines.append(
                f'<text x="{x + cell / 2:.0f}" y="{y + cell / 2 + 5:.0f}" '
                f'text-anchor="middle" class="small" fill="{text_color}">{content}</text>'
            )
    lines.append(
        f'<text x="55" y="{height - 36}" class="subtitle">{html.escape(subtitle)}</text>'
    )
    return _svg_end(lines)


def _maybe_overlap_png(
    path: Path,
    title: str,
    rows: list[dict[str, Any]],
    subtitle: str,
    description: str = "",
) -> Path | None:
    """Render the shared-URL matrix to PNG with a matched accessible SVG."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None
    size = len(rows)
    matrix = np.full((size, size), np.nan)
    for row_index in range(size):
        for column_index in range(size):
            value = _overlap_cell(rows, row_index, column_index)
            if value is not None:
                matrix[row_index, column_index] = value
    figure, axis = plt.subplots(
        figsize=(11, max(4.6, 0.62 * size + 2.6)), constrained_layout=False
    )
    figure.subplots_adjust(left=0.24, right=0.95, top=0.82, bottom=0.3)
    masked = np.ma.masked_invalid(matrix)
    maximum = float(np.max(matrix)) if size else 0.0
    axis.imshow(
        masked,
        cmap="Blues",
        vmin=0,
        vmax=max(maximum, 1.0),
        aspect="auto",
    )
    for row_index in range(size):
        for column_index in range(size):
            value = _overlap_cell(rows, row_index, column_index)
            if value is None:
                text, color = "N/A", "#5b6472"
            else:
                text, color = str(value), ("#ffffff" if value > maximum * 0.6 else INK)
            axis.text(
                column_index,
                row_index,
                text,
                ha="center",
                va="center",
                fontsize=9,
                color=color,
            )
    figure.suptitle(title, x=0.04, y=0.98, ha="left", fontweight="bold", fontsize=15)
    axis.set_xticks(range(size), [str(row["target"]) for row in rows])
    axis.tick_params(axis="x", labelrotation=40)
    for label in axis.get_xticklabels():
        label.set_ha("right")
    axis.set_yticks(
        range(size),
        [f"{row['target']}\n{row['area']}" for row in rows],
        fontsize=8,
    )
    axis.set_xticks(np.arange(-0.5, size), minor=True)
    axis.set_yticks(np.arange(-0.5, size), minor=True)
    axis.grid(which="minor", color="white", linewidth=1.2)
    axis.tick_params(which="minor", length=0)
    figure.text(
        0.04,
        0.01,
        "\n".join(textwrap.wrap(subtitle, 95)),
        fontsize=11,
        va="bottom",
        color=INK,
    )
    figure.savefig(
        path,
        dpi=300,
        metadata={"Creator": "Skillarum", "Title": title},
        facecolor="white",
        edgecolor="white",
        transparent=False,
    )
    svg_path = path.with_suffix(".svg")
    with matplotlib.rc_context({"svg.hashsalt": "skillarum", "svg.fonttype": "none"}):
        figure.savefig(svg_path, metadata={"Date": None, "Creator": "Skillarum"})
    _accessible_svg(svg_path, title, description or subtitle)
    plt.close(figure)
    if not path.is_file():
        raise RuntimeError(f"figure raster was not generated: {path}")
    return path


def _registry_record(
    figure_id: str,
    title: str,
    path: Path,
    source_data: Path,
    report: EvaluationReport,
    caption: str,
    alt_text: str,
    *,
    units: str,
    aggregation: str,
    sample_size_basis: str,
    evidence_origin: str | None = None,
    sample_size: int | None = None,
    raster_path: Path | None = None,
    uncertainty: str = "Not applicable for a structural diagram.",
    limitations: tuple[str, ...] = (
        "Structural diagram; no empirical performance claim.",
    ),
    manuscript_refs: tuple[str, ...] = ("03_methodology",),
    denominator: str = "not applicable (contract-derived structural diagram)",
    data_path: str | None = None,
    data_sha256: str | None = None,
) -> FigureRecord:
    if not source_data.exists():
        raise FileNotFoundError(f"figure source data does not exist: {source_data}")
    if not caption.strip() or not alt_text.strip():
        raise ValueError(f"figure {figure_id} requires caption and alt text")
    if len(alt_text.strip()) < 20:
        raise ValueError(f"figure {figure_id} alt text is too short to be useful")
    source_types = (
        report.summary.get("source_types", {})
        if isinstance(report.summary, dict)
        else {}
    )
    origin = (
        evidence_origin
        or ", ".join(
            f"{label}={int(source_types.get(label, 0))}"
            for label in ("fixture", "live", "unknown")
            if int(source_types.get(label, 0))
        )
        or "no completed observations"
    )
    source_hash = sha256_bytes(source_data.read_bytes())
    artifact_hash = sha256_text(path.read_text(encoding="utf-8"))
    raster_hash = sha256_bytes(raster_path.read_bytes()) if raster_path else None
    return FigureRecord(
        figure_id=figure_id,
        title=title,
        path=path.name,
        raster_path=raster_path.name if raster_path else None,
        source_data=provenance_path(source_data, path.parent.parent),
        source_sha256=source_hash,
        artifact_sha256=artifact_hash,
        raster_sha256=raster_hash,
        generator=FIGURE_GENERATOR,
        caption=caption,
        alt_text=alt_text,
        units=units,
        aggregation=aggregation,
        evidence_origin=origin,
        sample_size=len(report.observations) if sample_size is None else sample_size,
        sample_size_basis=sample_size_basis,
        uncertainty=uncertainty,
        limitations=limitations,
        manuscript_refs=manuscript_refs,
        report_id=report.report_id,
        denominator=denominator,
        data_path=data_path,
        data_sha256=data_sha256,
    )


def _verify_source_report(source_data: Path, report: EvaluationReport) -> None:
    """Reject a source file that is not the persisted form of ``report``.

    Hashing arbitrary bytes is not enough: the file must be internally
    consistent (its own ``artifact_sha256`` must match its payload body) and
    that body must equal the persisted form of the in-memory report being
    plotted. Generation fails closed otherwise.
    """
    try:
        payload = json.loads(source_data.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"source data is not readable JSON: {source_data}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"source data is not a report object: {source_data}")
    if payload.get("report_id") != report.report_id:
        raise ValueError(
            f"source data report_id {payload.get('report_id')!r} does not match the "
            f"in-memory report {report.report_id!r}"
        )
    if payload.get("artifact_sha256") != _report_payload_hash(payload):
        raise ValueError(
            f"source data artifact_sha256 does not match the file contents "
            f"for {source_data}"
        )
    if payload.get("artifact_sha256") != _report_content_hash(report):
        raise ValueError(
            f"source data artifact_sha256 does not match the in-memory report "
            f"content for {report.report_id!r}"
        )


def generate_figures(
    report: EvaluationReport,
    output_dir: str | Path,
    *,
    source_data: str | Path = "output/reports/evaluation-summary.json",
) -> Path:
    """Generate reproducible structural and telemetry figures plus a registry.

    The source file must be the persisted form of the passed report (matching
    report_id and content hash); figures are never plotted from a file that
    merely happens to exist at ``source_data``.
    """
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    source_path = Path(source_data)
    _verify_source_report(source_path, report)
    records: list[FigureRecord] = []
    context = _report_context(report)
    structural = [
        (
            "pipeline-trust-boundaries",
            "Pipeline and trust boundaries",
            ["acquire", "prepare", "process", "parse", "render"],
            "The source corpus is untrusted data; the provider boundary and the draft-validation gate remain explicit.",
            "The five Skillarum stages form a one-way dataflow with an explicit trust boundary around source content.",
            "Pipeline and trust boundaries. The diagram shows the five contract-defined Skillarum stages and the source-data trust boundary; it is generated from implementation contracts, not from the report's measurements. Report context (metadata only): "
            + context
            + ". The diagram is not a performance measurement or a claim about site coverage.",
            ("03_methodology",),
        ),
        (
            "run-state-machine",
            "Run states and recovery",
            [
                "planned",
                "acquiring",
                "preparing",
                "generating",
                "validating",
                "rendered",
            ],
            "Caught exceptions attempt diagnostic writes; subsequent runs revalidate cache state.",
            "The run state machine progresses from planning through rendering and records failure as a diagnosable terminal state.",
            "Run states and recovery. The diagram shows the persisted lifecycle from planning to rendering and the recoverable failure boundary; it is generated from implementation contracts, not from the report's measurements. Report context (metadata only): "
            + context
            + ". It does not establish reliability, recovery probability, or successful resumption under every failure mode.",
            ("03_methodology",),
        ),
        (
            "cache-integrity-flow",
            "Cache identity and artifact integrity",
            [
                "profile+target",
                "bundle hash",
                "corpus hash",
                "draft hash",
                "package hash",
                "index",
            ],
            "Each downstream identity commits to the upstream content and configuration it depends on.",
            "Cache and publication identities form a chain from profile and target configuration to the discovery index.",
            "Cache identity and artifact integrity. The diagram shows the contract-defined hash dependencies from configuration through the published index; it is generated from implementation contracts, not from the report's measurements. Report context (metadata only): "
            + context
            + ". It is not an empirical collision or speed result.",
            ("04_security",),
        ),
    ]
    for (
        figure_id,
        title,
        labels,
        subtitle,
        alt_text,
        caption,
        structural_refs,
    ) in structural:
        path = root / f"{figure_id}.svg"
        write_text_atomic(path, _flow_figure(title, labels, subtitle, alt_text))
        raster_path = _maybe_structural_png(
            path.with_suffix(".png"), title, labels, subtitle, description=alt_text
        )
        records.append(
            _registry_record(
                figure_id,
                title,
                path,
                source_path,
                report,
                caption,
                alt_text,
                units="diagram stages",
                aggregation="contract-defined flow; no numeric aggregation",
                sample_size_basis="completed observations retained as context only",
                raster_path=raster_path,
                manuscript_refs=structural_refs,
            )
        )

    telemetry_rows = _area_telemetry(report)
    area_labels = [str(row["area"]) for row in telemetry_rows] or ["no observations"]
    acquisition_categories = [
        "accepted",
        "rejected",
        "redirected",
        "canonicalized",
        "duplicates",
        "truncated",
    ]
    acquisition_series = {
        str(row["area"]): [
            float(row["accepted"]),
            float(row["rejected"]),
            float(row["redirects"]),
            float(row["canonicalized"]),
            float(row["duplicates"]),
            float(row["truncated"]),
        ]
        for row in telemetry_rows
    } or {"no observations": [0.0] * len(acquisition_categories)}
    acquisition_title = "Acquisition outcomes by source area"
    acquisition_subtitle = f"{context}; each bar is a within-area sum from persisted request/page telemetry."
    acquisition_alt = "Grouped bars compare accepted, rejected, redirected, canonicalized, duplicate, and truncated page outcomes for each declared source area."
    path = root / "acquisition-funnel.svg"
    write_text_atomic(
        path,
        _grouped_bar_figure(
            acquisition_title,
            acquisition_categories,
            acquisition_series,
            "event/page count",
            acquisition_subtitle,
            acquisition_alt,
        ),
    )
    records.append(
        _registry_record(
            "acquisition-funnel",
            acquisition_title,
            path,
            source_path,
            report,
            "Acquisition outcomes by source area. For each declared area, grouped bars show six separately defined counts: accepted pages, rejected requests, redirects, pages carrying canonical links, duplicate pages, and truncated accepted pages. Each value is a within-area sum across completed observations ("
            + context
            + "). The categories are not additive because one request can redirect or carry a canonical link while still producing an accepted page. This case-study matrix does not establish the number of pages available on either website, a site-wide coverage rate, or a causal effect of any crawler policy.",
            acquisition_alt,
            units="event/page counters",
            aggregation="separate sums of request/page outcome counters grouped by source area",
            sample_size_basis="completed evaluation observations",
            denominator="separate within-area sums; outcome categories are not additive",
            raster_path=_maybe_grouped_png(
                root / "acquisition-funnel.png",
                acquisition_title,
                acquisition_categories,
                acquisition_series,
                "event/page count",
                acquisition_subtitle,
                acquisition_alt,
            ),
            uncertainty="No inferential interval is plotted because the categories are event counts; exact intervals for selected proportions belong to the machine-readable report.",
            limitations=(
                "The two public domains are case-study sources, not a population sample.",
                "Outcome counts depend on target selection, robots policy, crawl limits, retries, and duplicate/canonical rules.",
            ),
            manuscript_refs=("05_evaluation",),
        )
    )

    backend_labels = sorted(
        {str(item.selected_backend or item.generator) for item in report.observations}
    )
    backend_labels = backend_labels or ["no observations"]
    provider_series = {
        "fallback observations": [
            float(
                sum(
                    item.fallback_used
                    for item in report.observations
                    if str(item.selected_backend or item.generator) == label
                )
            )
            for label in backend_labels
        ],
        "provider failures": [
            float(
                sum(
                    item.provider_failures
                    for item in report.observations
                    if str(item.selected_backend or item.generator) == label
                )
            )
            for label in backend_labels
        ],
        "retry attempts": [
            float(
                sum(
                    item.retry_count
                    for item in report.observations
                    if str(item.selected_backend or item.generator) == label
                )
            )
            for label in backend_labels
        ],
    }
    for series_name, field in (
        ("fallback observations", "fallback_used"),
        ("provider failures", "provider_failures"),
        ("retry attempts", "retry_count"),
    ):
        for index, backend in enumerate(backend_labels):
            selected = [
                item
                for item in report.observations
                if str(item.selected_backend or item.generator) == backend
            ]
            if not selected or any(
                field in item.metadata.get("missing_metrics", []) for item in selected
            ):
                provider_series[series_name][index] = None
    fallback_note = (
        "No fallback events were observed in this report."
        if report.observations
        and all(value == 0 for value in provider_series["fallback observations"])
        else "Fallback counts use persisted traces; N/A means unavailable telemetry."
    )
    fallback_title = "Provider fallback outcomes"
    fallback_subtitle = f"{context}; {fallback_note}"
    fallback_alt = "Grouped bars compare fallback observations, provider failures, and retry attempts for each selected generation backend."
    path = root / "provider-fallback-outcomes.svg"
    write_text_atomic(
        path,
        _grouped_bar_figure(
            fallback_title,
            backend_labels,
            provider_series,
            "count",
            fallback_subtitle,
            fallback_alt,
        ),
    )
    records.append(
        _registry_record(
            "provider-fallback-outcomes",
            fallback_title,
            path,
            source_path,
            report,
            "Provider fallback outcomes. For each selected backend, grouped bars separately count observations with fallback, recorded provider-failure attempts, and retry attempts. Fallback is a Boolean observation-level indicator; failures and retries are attempt-level counters. The aggregation is grouped sums over "
            + context
            + ". A zero is an observed absence in this report, not a guarantee that providers cannot fail; the plot does not measure output quality or provider reliability in the population.",
            fallback_alt,
            units="fallback observations; provider-failure attempts; retry attempts",
            denominator=(
                "fallback: observations with fallback telemetry; failures and "
                "retries: recorded attempts within those observations"
            ),
            aggregation="separate grouped sums over generation traces",
            sample_size_basis="completed evaluation observations with a generation trace",
            raster_path=_maybe_grouped_png(
                root / "provider-fallback-outcomes.png",
                fallback_title,
                backend_labels,
                provider_series,
                "count",
                fallback_subtitle,
                fallback_alt,
            ),
            uncertainty="No inferential interval is plotted; the report provides an exact small-sample interval for the overall fallback proportion.",
            limitations=(
                "Provider availability, model configuration, and the deterministic default affect these observed counts.",
                "The three series have different units and are not additive.",
            ),
            manuscript_refs=("05_evaluation",),
        )
    )

    latency_labels, latency_values = _latency_series(report)
    per_target_note = _omission_note(_per_target_observations(report)[1])
    latency_title = "Generation latency by target observation"
    latency_subtitle = (
        f"{context}; persisted generation durations, including retries. Cached drafts, when present, retain original timings; N/A means unavailable. Zero can reflect sub-millisecond rounding."
        + per_target_note
    )
    latency_alt = "A bar chart of recorded generation duration in milliseconds for each area and target observation."
    path = root / "generation-latency.svg"
    write_text_atomic(
        path,
        _bar_figure(
            latency_title,
            latency_labels,
            latency_values,
            "milliseconds",
            latency_subtitle,
            latency_alt,
        ),
    )
    records.append(
        _registry_record(
            "generation-latency",
            latency_title,
            path,
            source_path,
            report,
            "Generation latency. Each bar identifies one area/target observation and shows the sum of persisted provider-attempt durations, including retry attempts. The unit is milliseconds and the aggregation is a run-level sum over attempts; "
            + context
            + ". Cached drafts, when present, retain original attempt timings; reported durations are not end-to-end pipeline wall time. N/A denotes absent telemetry. The report also retains the median, range, and missingness for this metric. This operational telemetry is not a model-quality measure, does not isolate network/provider/cache components, and should not be generalized beyond these runs."
            + per_target_note,
            latency_alt,
            units="milliseconds",
            denominator=(
                "one persisted generation-duration value per completed "
                "observation; N/A when telemetry is missing"
            ),
            aggregation="sum of provider-attempt duration_ms per observation",
            sample_size_basis="completed target observations with generation traces",
            raster_path=_maybe_png(
                root / "generation-latency.png",
                latency_title,
                latency_labels,
                latency_values,
                "milliseconds",
                latency_subtitle,
                latency_alt,
            ),
            uncertainty="No inferential interval is shown; the figure reports observed run-level values.",
            limitations=(
                "Small samples, caching, hardware, provider configuration, and retries can dominate latency.",
                "Labels identify run observations rather than independent replicated experiments.",
            ),
            manuscript_refs=("05_evaluation",),
        )
    )

    completeness_title = "Artifact integrity checks"
    completeness_labels = ["provenance", "required sections", "untrusted source"]
    completeness_values = [
        float(sum(item.provenance_complete for item in report.observations)),
        float(sum(item.required_sections_valid for item in report.observations)),
        float(sum(item.unsafe_source_preserved for item in report.observations)),
    ]
    completeness_subtitle = f"{context}; each value counts observations passing the named structural or trust-boundary check."
    completeness_alt = "A bar chart comparing observation counts that pass provenance, required-section, and untrusted-source preservation checks."
    path = root / "provenance-completeness.svg"
    write_text_atomic(
        path,
        _bar_figure(
            completeness_title,
            completeness_labels,
            completeness_values,
            "valid observations",
            completeness_subtitle,
            completeness_alt,
        ),
    )
    records.append(
        _registry_record(
            "provenance-completeness",
            completeness_title,
            path,
            source_path,
            report,
            "Artifact integrity checks. Bars count completed observations that pass three separately evaluated Boolean checks: page-level provenance completeness, required portable sections, and presence of an untrusted-source marker. The unit is observations and the aggregation is a sum of Boolean checks over "
            + context
            + ". Numerators and denominators remain available in the report’s exact-binomial proportion records; the companion proportion-intervals figure draws those exact intervals with each row’s eligible denominator. These checks establish package structure and provenance handling; they do not establish the factual truth, semantic coverage, or usefulness of source claims.",
            completeness_alt,
            units="observations passing check",
            denominator="observations passing each check out of all completed observations",
            aggregation="sum of Boolean validation results across observations",
            sample_size_basis="completed evaluation observations",
            raster_path=_maybe_png(
                root / "provenance-completeness.png",
                completeness_title,
                completeness_labels,
                completeness_values,
                "valid observations",
                completeness_subtitle,
                completeness_alt,
            ),
            uncertainty="Exact small-sample intervals are reported in the evaluation JSON rather than plotted here.",
            limitations=(
                "Structural validation does not establish semantic correctness or source truth.",
            ),
            manuscript_refs=("05_evaluation",),
        )
    )

    proportion_rows = _proportion_rows(report)
    if not proportion_rows:
        proportion_rows = [
            {
                "key": "none",
                "label": "No proportion records",
                "denominator_basis": "none",
                "successes": 0,
                "total": 0,
                "rate": None,
                "percent": None,
                "exact_95_interval": None,
            }
        ]
    confidence = _confidence_label(report)
    proportion_title = "Exact binomial intervals for reported proportions"
    proportion_subtitle = (
        f"{context}; dots mark observed rates, lines span exact Clopper–Pearson "
        f"{confidence} intervals, and each row uses its own eligible denominator."
    )
    proportion_alt = (
        "For each reported proportion, a row places a dot at the observed "
        f"percentage, a horizontal capped line spans the exact {confidence} "
        "interval, and the annotation gives successes over the row's "
        "denominator. Rows without an eligible denominator are marked as such."
    )
    proportion_denominator = (
        "per-row successes over the row's eligible denominator: completed "
        "observations for the package checks, observations with fallback telemetry "
        "for the fallback row, and observed source pages for complete mapping"
    )
    proportion_caption = (
        "Exact binomial intervals for reported proportions. Each row shows the "
        "observed rate as a dot with a capped line spanning its exact "
        f"Clopper–Pearson {confidence} interval, annotated successes/denominator. "
        "Rows use their own eligible denominator: completed observations for the "
        "package checks, observations with fallback telemetry for the fallback "
        "row, and observed source pages for complete mapping ("
        + context
        + "). Intervals are model-reference quantities under independent Bernoulli "
        "assumptions: targets share sites, robots policy, and crawl limits, repeated "
        "invocations overwrite stable run identities, and pages within a target are "
        "not independent, so interval coverage is not calibrated for these "
        "selected dependent records. The figure does not establish "
        "web-population rates, provider effects, semantic quality, or a "
        "significance test between rows; rows have different denominators and "
        "are not compared inferentially."
    )
    path = root / "proportion-intervals.svg"
    write_text_atomic(
        path,
        _interval_figure(
            proportion_title,
            proportion_rows,
            proportion_subtitle,
            proportion_alt,
        ),
    )
    data_path, data_sha256 = _point_data(
        root,
        "proportion-intervals",
        proportion_rows,
        report=report,
        source_path=source_path,
        units=f"percent with exact Clopper–Pearson {confidence} interval",
        denominator=proportion_denominator,
        notes=(
            "Rates and intervals are reused verbatim from the report's proportion records.",
            "Rows without an eligible denominator carry total=0 and no interval.",
        ),
    )
    records.append(
        _registry_record(
            "proportion-intervals",
            proportion_title,
            path,
            source_path,
            report,
            proportion_caption,
            proportion_alt,
            units=f"percent with exact Clopper–Pearson {confidence} interval",
            aggregation="report-level proportion records reused verbatim; no recomputation",
            sample_size_basis="each row's eligible denominator is stated beside its estimate",
            raster_path=_maybe_interval_png(
                root / "proportion-intervals.png",
                proportion_title,
                proportion_rows,
                proportion_subtitle,
                proportion_alt,
            ),
            uncertainty=(
                f"Exact Clopper–Pearson {confidence} intervals under independent "
                "Bernoulli assumptions; interval coverage is not calibrated under "
                "the dependence described in the caption."
            ),
            denominator=proportion_denominator,
            data_path=data_path,
            data_sha256=data_sha256,
            limitations=(
                "Rows share sites, robots policy, and crawl limits; observations are not independent trials.",
                "Interval width is driven by small denominators and must not be read as a population estimate.",
                "No between-row significance test is implied; rows have different denominators.",
            ),
            manuscript_refs=("05_evaluation",),
        )
    )

    coverage_categories = area_labels
    coverage_series = {
        "mapped source pages": [
            (100.0 * row["coverage"] / row["source_total"])
            if row["source_total"]
            else None
            for row in telemetry_rows
        ]
        or [None],
        "truncated accepted pages": [
            (100.0 * row["truncated"] / row["accepted"]) if row["accepted"] else None
            for row in telemetry_rows
        ]
        or [None],
    }
    coverage_title = "Source mapping and truncation rates"
    coverage_subtitle = f"{context}; percentages are descriptive and use the denominator named in the caption."
    coverage_alt = "Grouped percentage bars compare complete source-page mapping with truncation among accepted pages for each source area."
    path = root / "coverage-truncation.svg"
    write_text_atomic(
        path,
        _grouped_bar_figure(
            coverage_title,
            coverage_categories,
            coverage_series,
            "percent",
            coverage_subtitle,
            coverage_alt,
            maximum=100.0,
            percent=True,
        ),
    )
    records.append(
        _registry_record(
            "coverage-truncation",
            coverage_title,
            path,
            source_path,
            report,
            "Source mapping and truncation rates. For each declared area, the first series is complete source-page mappings divided by observed source pages; the second is truncated accepted pages divided by accepted pages. Thus the two percentages have different denominators and are shown together for diagnostic comparison, not as complementary parts of one rate. The population is the completed observation set ("
            + context
            + "). These case-study rates do not establish site-wide completeness, content quality, or the probability that an unseen page would be truncated.",
            coverage_alt,
            sample_size_basis="completed evaluation observations and their persisted page counters",
            units="percent; mapping denominator = observed source pages, truncation denominator = accepted pages",
            denominator="mapping: observed source pages; truncation: accepted pages",
            aggregation="area-level ratios from summed page counters",
            uncertainty="No interval is plotted; exact intervals for selected proportions are available in the report, while the displayed area ratios are descriptive aggregates.",
            limitations=(
                "Mapping and truncation denominators differ.",
                "Area-level aggregation can conceal target-level variation.",
            ),
            manuscript_refs=("05_evaluation",),
            raster_path=_maybe_grouped_png(
                root / "coverage-truncation.png",
                coverage_title,
                coverage_categories,
                coverage_series,
                "percent",
                coverage_subtitle,
                coverage_alt,
                maximum=100.0,
                percent=True,
            ),
        )
    )

    request_categories = area_labels
    request_values = [
        (row["requests"] / row["accepted"])
        if row["accepted"] and not row.get("requests_missing")
        else None
        for row in telemetry_rows
    ] or [None]
    request_title = "Request pressure per accepted page"
    request_subtitle = f"{context}; requests include page, redirect, robots, and retry attempts recorded by the acquisition layer."
    request_alt = "A bar chart showing the number of recorded acquisition requests per accepted page for each source area."
    path = root / "request-pressure.svg"
    write_text_atomic(
        path,
        _bar_figure(
            request_title,
            request_categories,
            request_values,
            "requests per accepted page",
            request_subtitle,
            request_alt,
        ),
    )
    records.append(
        _registry_record(
            "request-pressure",
            request_title,
            path,
            source_path,
            report,
            "Request pressure per accepted page. Each area value is the total persisted request-attempt count divided by the total accepted-page count for that area; request attempts include robots checks, redirects, retries, and normal page requests when recorded. The unit is requests per accepted page and the aggregation is a ratio of area-level sums over the completed observation set ("
            + context
            + "). This diagnostic does not establish network cost, crawler efficiency, or the total number of pages on a source site.",
            request_alt,
            sample_size_basis="completed evaluation observations with persisted request events",
            units="requests per accepted page",
            denominator="total request attempts divided by accepted pages",
            aggregation="area-level request-count sum divided by accepted-page sum",
            uncertainty="No inferential interval is plotted; the report retains request-count distributions and missingness.",
            limitations=(
                "A ratio of sums can conceal target-level variation.",
                "Request-event completeness depends on the acquisition manifest schema.",
            ),
            manuscript_refs=("05_evaluation",),
            raster_path=_maybe_png(
                root / "request-pressure.png",
                request_title,
                request_categories,
                request_values,
                "requests per accepted page",
                request_subtitle,
                request_alt,
            ),
        )
    )

    review = (
        report.summary.get("review", {}) if isinstance(report.summary, dict) else {}
    )
    if (
        review.get("status") == "complete"
        and int(review.get("paired_case_count", 0)) > 0
    ):
        criteria = list(review.get("criteria", {}))
        criteria_values = [
            float(review["criteria"][criterion].get("mean", 0.0))
            for criterion in criteria
        ]
        review_title = "Human review rubric scores"
        review_subtitle = f"{review.get('rater_count', 0)} raters; {review.get('paired_case_count', 0)} paired cases; ordinal scores range from 0 to 4."
        review_alt = "A bar chart showing mean ordinal human-review scores for semantic coverage, procedure, verification, provenance, safety, and readability."
        path = root / "human-review-rubric.svg"
        write_text_atomic(
            path,
            _bar_figure(
                review_title,
                criteria,
                criteria_values,
                "mean score (0–4)",
                review_subtitle,
                review_alt,
                maximum=4.0,
            ),
        )
        records.append(
            _registry_record(
                "human-review-rubric",
                review_title,
                path,
                source_path,
                report,
                "Human review rubric scores. Bars show the arithmetic mean of 0–4 ordinal ratings for each review criterion across the persisted rating rows; the report records the rater count, paired-case count, individual ratings, and weighted agreement values. The displayed population is the completed two-rater review subset, not the full web or user population ("
                + context
                + "). Means summarize observed ratings and do not establish semantic validity, causal provider effects, or general human preference.",
                review_alt,
                units="mean ordinal score on a 0–4 rubric",
                sample_size_basis="rating rows from at least two raters with overlapping cases",
                denominator="rating rows per criterion",
                aggregation="criterion-wise arithmetic mean over rating rows",
                evidence_origin=f"two-rater review; rating_count={review.get('rating_count', 0)}; paired_cases={review.get('paired_case_count', 0)}",
                sample_size=int(review.get("rating_count", 0)),
                raster_path=_maybe_png(
                    root / "human-review-rubric.png",
                    review_title,
                    criteria,
                    criteria_values,
                    "mean score (0–4)",
                    review_subtitle,
                    review_alt,
                ),
                uncertainty="No confidence interval is plotted for ordinal means; agreement statistics and the complete rating rows remain in the report.",
                limitations=(
                    "Ratings are ordinal and reviewer/sample selection may limit interpretation.",
                    "A paired two-rater subset is not a population-level quality estimate.",
                    "Agreement does not establish validity of the rubric itself.",
                ),
                manuscript_refs=("05_evaluation",),
            )
        )

    area_title = "Skill catalog by source area"
    area_alt = "A table comparing distinct targets, observations, accepted pages, truncated pages, and complete page-level provenance mapping for Math4Wisdom and Active Inference Institute areas."
    area_caption = (
        "Skill catalog by source area. Each row is a declarative namespace rather than an inferred topic cluster. Columns report distinct target count, observation count, accepted pages, truncated accepted pages, and complete source-page mapping. Counts are within-area sums; mapping is complete pages divided by observed source pages. The population is the completed observation set ("
        + context
        + "); it does not establish website completeness, semantic quality, comparative superiority, or equal acquisition effort between areas."
    )
    path = root / "area-catalog.svg"
    write_text_atomic(path, _area_matrix_figure(report))
    records.append(
        _registry_record(
            "area-catalog",
            area_title,
            path,
            source_path,
            report,
            area_caption,
            area_alt,
            units="targets; observations; accepted pages; truncated pages; mapping proportion",
            denominator="mapping: complete pages divided by observed source pages",
            aggregation="grouped descriptive sums by declared source area",
            sample_size_basis="completed evaluation observations",
            raster_path=_maybe_area_png(root / "area-catalog.png", report, area_alt),
            uncertainty="No inferential comparison between source areas is attempted; mapping proportions are descriptive ratios.",
            limitations=("Area membership is declarative profile metadata.",),
            manuscript_refs=("05_evaluation",),
        )
    )

    overlap_rows = _overlap_rows(report)
    if overlap_rows is not None:
        overlap_title = "Shared source pages between targets"
        overlap_subtitle = (
            f"{context}; each cell counts accepted-page URLs recorded by both "
            "targets; the diagonal is a target's own page count; N/A marks a "
            "target without a recorded URL list." + per_target_note
        )
        overlap_alt = (
            "A square matrix with one row and column per target: each cell "
            "prints the number of accepted-page URLs shared by the two targets, "
            "the diagonal shows each target's own page count, and targets "
            "without a recorded URL list are marked N/A."
        )
        overlap_caption = (
            "Shared source pages between targets. Each cell is the exact number "
            "of accepted-page URLs present in both targets' persisted "
            "source-URL lists, and the diagonal repeats each target's own page "
            "count. Values derive from the recorded URL lists only (" + context + "). "
            "Overlap between targets is the concrete dependence that limits "
            "interval coverage in the proportion figure. It does not establish "
            "that shared URLs produced identical extracted content, that any "
            "website is completely covered, or anything about pages outside "
            "these recorded lists." + per_target_note
        )
        path = root / "source-overlap.svg"
        write_text_atomic(
            path,
            _overlap_matrix_svg(
                overlap_title, overlap_rows, overlap_subtitle, overlap_alt
            ),
        )
        pair_rows = []
        for first in range(len(overlap_rows)):
            for second in range(first, len(overlap_rows)):
                source_urls = overlap_rows[first]["urls"]
                target_urls = overlap_rows[second]["urls"]
                pair_rows.append(
                    {
                        "source_target": overlap_rows[first]["target"],
                        "target": overlap_rows[second]["target"],
                        "source_area": overlap_rows[first]["area"],
                        "target_area": overlap_rows[second]["area"],
                        "shared": _overlap_cell(overlap_rows, first, second),
                        "pages_source": (
                            len(source_urls) if source_urls is not None else None
                        ),
                        "pages_target": (
                            len(target_urls) if target_urls is not None else None
                        ),
                    }
                )
        data_path, data_sha256 = _point_data(
            root,
            "source-overlap",
            pair_rows,
            report=report,
            source_path=source_path,
            units="shared accepted-page URLs",
            denominator="shared URLs out of each target's accepted-page URL list",
            notes=(
                "Cells are exact set intersections of the persisted URL lists.",
                "shared=null marks a target whose URL list was not recorded; it is not a zero.",
            ),
        )
        records.append(
            _registry_record(
                "source-overlap",
                overlap_title,
                path,
                source_path,
                report,
                overlap_caption,
                overlap_alt,
                units="shared accepted-page URLs",
                aggregation="exact set intersection of persisted per-target source URL lists",
                sample_size_basis="completed observations with a persisted source-URL list",
                raster_path=_maybe_overlap_png(
                    root / "source-overlap.png",
                    overlap_title,
                    overlap_rows,
                    overlap_subtitle,
                    overlap_alt,
                ),
                uncertainty="No interval applies; cell values are exact set intersections of recorded lists.",
                denominator="shared URLs out of each target's accepted-page URL list",
                data_path=data_path,
                data_sha256=data_sha256,
                limitations=(
                    "URL identity is the recorded canonical form; it is not a claim that shared URLs produced identical extracted content.",
                    "Pages outside the recorded URL lists are invisible to this figure.",
                    "Overlap contextualizes dependence between observations; it is not a similarity metric between generated skills.",
                    "Manuscript linkage is prose-only this wave: 05_evaluation describes this figure conditionally; no caption token or figure embed exists yet.",
                ),
                manuscript_refs=("05_evaluation",),
            )
        )

    registry = {
        "schema_version": FIGURE_SCHEMA_VERSION,
        "report_id": report.report_id,
        # The parent-template PDF/HTML renderers key figure alt-text records by
        # a pandoc-crossref label; every manuscript caption uses {#fig:<id>}.
        "figures": [
            {"label": f"fig:{record.figure_id}", **_registry_entry(record)}
            for record in records
        ],
    }
    registry_path = root / "figure_registry.json"
    write_json_atomic(registry_path, registry)
    registry_hash = sha256_bytes(registry_path.read_bytes())
    write_json_atomic(
        root / "figure_registry.manifest.json",
        {
            "schema_version": FIGURE_SCHEMA_VERSION,
            "registry_file": provenance_path(registry_path, root.parent),
            "registry_sha256": registry_hash,
            "figure_count": len(records),
            "figure_artifacts": {
                record.figure_id: {
                    "title": record.title,
                    "path": record.raster_path or record.path,
                    "artifact_sha256": record.raster_sha256 or record.artifact_sha256,
                    "vector_path": record.path,
                    "vector_sha256": record.artifact_sha256,
                }
                for record in records
            },
        },
    )
    return registry_path


def _registry_entry(record: FigureRecord) -> dict[str, Any]:
    """Emit one registry entry, promoting a raster twin to the canonical path.

    The parent-template PDF/HTML figure-alt registry matches rendered figure
    filenames against the record's canonical path only (it does not read
    ``raster_path``), and sibling projects register their PNG artifacts as the
    canonical path. When a raster twin exists, the PNG becomes ``path`` and the
    vector original is retained as ``vector_path`` for provenance.
    """
    entry = record.to_dict()
    raster = record.raster_path
    if raster:
        entry["path"] = raster
        entry["artifact_sha256"] = record.raster_sha256
        entry["vector_path"] = record.path
        entry["vector_sha256"] = record.artifact_sha256
        del entry["raster_path"]
        del entry["raster_sha256"]
    return entry


def validate_figure_registry(path: str | Path) -> dict[str, Any]:
    """Validate figure files, hashes, captions, accessibility, and metadata."""
    registry_path = Path(path)
    value = json.loads(registry_path.read_text(encoding="utf-8"))
    schema_version = value.get("schema_version")
    if schema_version not in READABLE_FIGURE_SCHEMA_VERSIONS:
        raise ValueError(f"unsupported figure registry schema: {schema_version!r}")
    figures = value.get("figures")
    if not isinstance(figures, list):
        raise ValueError("figure registry figures must be a list")
    errors: list[str] = []
    base_fields = (
        "figure_id",
        "path",
        "caption",
        "alt_text",
        "source_data",
        "source_sha256",
        "artifact_sha256",
        "sample_size",
    )
    v3_fields = (
        "title",
        "units",
        "aggregation",
        "sample_size_basis",
        "generator",
        "uncertainty",
        "limitations",
        "manuscript_refs",
    )
    v4_fields = ("evidence_origin",)
    seen_ids: set[str] = set()
    for figure in figures:
        if not isinstance(figure, dict):
            errors.append("figure entry is not an object")
            continue
        figure_id = str(figure.get("figure_id", "<unknown>"))
        if figure_id in seen_ids:
            errors.append(f"{figure_id}: duplicate figure_id")
        seen_ids.add(figure_id)
        fields = (
            base_fields
            + (v3_fields if schema_version >= 3 else ())
            + (v4_fields if schema_version >= 4 else ())
        )
        for field in fields:
            if field == "sample_size":
                if not isinstance(figure.get(field), int) or figure[field] < 0:
                    errors.append(
                        f"{figure_id}: sample_size must be a non-negative integer"
                    )
            elif not figure.get(field) and figure.get(field) != 0:
                errors.append(f"{figure_id}: missing {field}")
        if schema_version >= 3:
            if not isinstance(figure.get("limitations"), list) or not figure.get(
                "limitations"
            ):
                errors.append(f"{figure_id}: limitations must be a non-empty list")
            if not isinstance(figure.get("manuscript_refs"), list) or not figure.get(
                "manuscript_refs"
            ):
                errors.append(f"{figure_id}: manuscript_refs must be a non-empty list")
        if schema_version >= 4:
            if (
                not isinstance(figure.get("evidence_origin"), str)
                or not figure.get("evidence_origin", "").strip()
            ):
                errors.append(
                    f"{figure_id}: evidence_origin must be a non-empty string"
                )
            caption = str(figure.get("caption", ""))
            if "n=" not in caption:
                errors.append(f"{figure_id}: caption must state a sample size with n=")
            if not any(
                phrase in caption.casefold()
                for phrase in (
                    "does not establish",
                    "not establish",
                    "not a ",
                    "not an ",
                )
            ):
                errors.append(
                    f"{figure_id}: caption must state an interpretation boundary"
                )
            if len(str(figure.get("alt_text", ""))) < 20:
                errors.append(f"{figure_id}: alt_text must describe the visual content")
            alt_start = str(figure.get("alt_text", "")).strip()[:1]
            if alt_start and alt_start.islower():
                errors.append(
                    f"{figure_id}: alt_text must begin a descriptive sentence, "
                    "not a mid-sentence fragment"
                )
        alt_normalized = str(figure.get("alt_text", "")).strip().casefold()
        caption_normalized = str(figure.get("caption", "")).strip().casefold()
        if (
            alt_normalized
            and caption_normalized
            and alt_normalized == caption_normalized
        ):
            errors.append(f"{figure_id}: alt_text must not duplicate the caption")
        report_id = figure.get("report_id")
        if report_id is not None and (
            not isinstance(report_id, str) or not report_id.strip()
        ):
            errors.append(f"{figure_id}: report_id must be a non-empty string")
        denominator = figure.get("denominator")
        if denominator is not None and (
            not isinstance(denominator, str) or not denominator.strip()
        ):
            errors.append(f"{figure_id}: denominator must be a non-empty string")
        data_path = figure.get("data_path")
        data_sha256 = figure.get("data_sha256")
        if (data_path is None) != (data_sha256 is None):
            errors.append(
                f"{figure_id}: data_path and data_sha256 must be provided together"
            )
        elif data_path is not None:
            data_file = Path(str(data_path))
            if data_file.is_absolute() or ".." in data_file.parts:
                errors.append(
                    f"{figure_id}: data path must remain relative to the registry"
                )
                data_file = registry_path.parent / "__invalid_data_path__"
            else:
                data_file = registry_path.parent / data_file
            if data_file.is_symlink():
                errors.append(f"{figure_id}: data file must not be a symlink")
            elif not data_file.is_file():
                errors.append(f"{figure_id}: missing data file {data_file}")
            elif sha256_bytes(data_file.read_bytes()) != data_sha256:
                errors.append(f"{figure_id}: data file hash mismatch")
            else:
                try:
                    data_payload = json.loads(data_file.read_text(encoding="utf-8"))
                    if not isinstance(data_payload, dict):
                        raise ValueError("data table must be an object")
                    if data_payload.get("schema_version") != 1:
                        errors.append(f"{figure_id}: unsupported data table schema")
                    if data_payload.get("report_id") != value.get("report_id"):
                        errors.append(f"{figure_id}: data table report_id mismatch")
                    if data_payload.get("source_sha256") != figure.get("source_sha256"):
                        errors.append(f"{figure_id}: data table source hash mismatch")
                    if data_payload.get("figure_id") != figure_id:
                        errors.append(f"{figure_id}: data table figure_id mismatch")
                    if not isinstance(data_payload.get("rows"), list) or not (
                        data_payload.get("rows")
                    ):
                        errors.append(
                            f"{figure_id}: data table rows must be a non-empty list"
                        )
                except (OSError, ValueError) as exc:
                    errors.append(f"{figure_id}: invalid data table: {exc}")
        figure_path = Path(str(figure.get("path", "")))
        if figure_path.is_absolute() or ".." in figure_path.parts:
            errors.append(
                f"{figure_id}: figure path must remain relative to the registry"
            )
            figure_path = registry_path.parent / "__invalid_figure_path__"
        else:
            figure_path = registry_path.parent / figure_path
        if figure_path.is_symlink():
            errors.append(f"{figure_id}: figure artifact must not be a symlink")
        elif not figure_path.is_file():
            errors.append(f"{figure_id}: missing file {figure_path}")
        elif sha256_bytes(figure_path.read_bytes()) != figure.get("artifact_sha256"):
            errors.append(f"{figure_id}: artifact hash mismatch")
        source_data = Path(str(figure.get("source_data", "")))
        if source_data.is_absolute() or ".." in source_data.parts:
            errors.append(
                f"{figure_id}: source_data must remain relative (portable provenance)"
            )
            source_data = registry_path.parent / "__invalid_source_data__"
        else:
            candidates = (
                registry_path.parent / source_data,
                registry_path.parent.parent / source_data,
                Path.cwd() / source_data,
            )
            source_data = next(
                (candidate for candidate in candidates if candidate.exists()),
                candidates[0],
            )
        if source_data.is_symlink():
            errors.append(f"{figure_id}: source data must not be a symlink")
        elif not source_data.is_file():
            errors.append(f"{figure_id}: missing source data {source_data}")
        elif figure.get("source_sha256") and sha256_bytes(
            source_data.read_bytes()
        ) != figure.get("source_sha256"):
            errors.append(f"{figure_id}: source data hash mismatch")
        vector = figure.get("vector_path")
        if vector:
            vector_path = Path(str(vector))
            if vector_path.is_absolute() or ".." in vector_path.parts:
                errors.append(
                    f"{figure_id}: vector path must remain relative to the registry"
                )
                vector_path = registry_path.parent / "__invalid_vector_path__"
            else:
                vector_path = registry_path.parent / vector_path
            if vector_path.is_symlink():
                errors.append(f"{figure_id}: vector artifact must not be a symlink")
            elif not vector_path.is_file():
                errors.append(f"{figure_id}: missing vector file {vector_path}")
            elif sha256_bytes(vector_path.read_bytes()) != figure.get("vector_sha256"):
                errors.append(f"{figure_id}: vector hash mismatch")
    manifest_path = registry_path.with_name("figure_registry.manifest.json")
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("registry_sha256") != sha256_bytes(
                registry_path.read_bytes()
            ):
                errors.append("figure registry manifest hash mismatch")
            if manifest.get("figure_count") != len(figures):
                errors.append("figure registry manifest count mismatch")
            registry_file = manifest.get("registry_file")
            if registry_file is not None and Path(str(registry_file)).is_absolute():
                errors.append(
                    "figure registry manifest registry_file must remain relative"
                )
        except (OSError, json.JSONDecodeError):
            errors.append("figure registry manifest is unreadable")
    return {
        "schema_version": schema_version,
        "ok": not errors,
        "figure_count": len(figures),
        "errors": errors,
    }


__all__ = [
    "FIGURE_SCHEMA_VERSION",
    "FigureRecord",
    "generate_figures",
    "validate_figure_registry",
]
