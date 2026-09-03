"""Interactive plate schematics using Plotly heatmaps / scatter grids."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set

import plotly.graph_objects as go

from plateplanner.plates import PlateFormat, get_plate_format, parse_well_id, well_id


def _empty_z(fmt: PlateFormat) -> List[List[Optional[float]]]:
    return [[None for _ in range(fmt.cols)] for _ in range(fmt.rows)]


def plate_figure(
    plate: PlateFormat | str,
    *,
    values: Optional[Dict[str, float]] = None,
    highlight: Optional[Iterable[str]] = None,
    title: str = "",
    colorscale: str = "Blues",
    show_colorbar: bool = True,
    highlight_color: str = "#FF6B35",
    mapped_pairs: Optional[Sequence[tuple]] = None,
    height: Optional[int] = None,
) -> go.Figure:
    """
    Build an interactive plate schematic.

    - values: well -> numeric value (shown as color intensity / hover)
    - highlight: wells to outline
    - mapped_pairs: optional list of (src_well, dst_well) for annotation only
      when rendering a single plate (destination highlights)
    """
    fmt = plate if isinstance(plate, PlateFormat) else get_plate_format(plate)
    z = _empty_z(fmt)
    custom = _empty_z(fmt)
    values = values or {}
    highlight_set: Set[str] = {w.upper() if len(w) > 2 else w for w in (highlight or [])}
    # normalize highlight
    norm_highlight: Set[str] = set()
    for w in highlight or []:
        try:
            r, c = parse_well_id(w)
            norm_highlight.add(well_id(r, c))
        except ValueError:
            pass

    for well, val in values.items():
        try:
            r, c = parse_well_id(well)
        except ValueError:
            continue
        if 0 <= r < fmt.rows and 0 <= c < fmt.cols:
            z[r][c] = float(val)
            custom[r][c] = f"{well_id(r, c)}: {val:g} µL"

    # Fill customdata for empty wells
    for r in range(fmt.rows):
        for c in range(fmt.cols):
            if custom[r][c] is None:
                custom[r][c] = well_id(r, c)

    row_labels = list(fmt.row_letters)
    col_labels = [f"{c + 1:02d}" for c in range(fmt.cols)]

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=col_labels,
            y=row_labels,
            colorscale=colorscale,
            showscale=show_colorbar,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=custom,
            xgap=2,
            ygap=2,
            colorbar=dict(title="µL") if show_colorbar else None,
        )
    )

    # Highlight outlines via scatter markers
    if norm_highlight:
        hx, hy = [], []
        for w in norm_highlight:
            r, c = parse_well_id(w)
            if 0 <= r < fmt.rows and 0 <= c < fmt.cols:
                hx.append(col_labels[c])
                hy.append(row_labels[r])
        fig.add_trace(
            go.Scatter(
                x=hx,
                y=hy,
                mode="markers",
                marker=dict(
                    symbol="square",
                    size=18 if fmt.cols <= 12 else 10,
                    color="rgba(0,0,0,0)",
                    line=dict(color=highlight_color, width=2),
                ),
                hoverinfo="skip",
                showlegend=False,
                name="selected",
            )
        )

    auto_height = height or (320 if fmt.rows <= 8 else 520)
    fig.update_layout(
        title=title or f"{fmt.name}-well plate",
        height=auto_height,
        margin=dict(l=40, r=20, t=50, b=40),
        yaxis=dict(
            autorange="reversed",
            scaleanchor="x",
            scaleratio=1,
            tickmode="array",
            tickvals=row_labels,
            title="",
        ),
        xaxis=dict(
            side="top",
            tickmode="array",
            tickvals=col_labels,
            title="",
            constrain="domain",
        ),
        plot_bgcolor="#f7f7f7",
        paper_bgcolor="white",
    )
    return fig


def dual_plate_figures(
    source_format: str,
    dest_format: str,
    *,
    source_values: Optional[Dict[str, float]] = None,
    dest_values: Optional[Dict[str, float]] = None,
    source_highlight: Optional[Iterable[str]] = None,
    dest_highlight: Optional[Iterable[str]] = None,
    source_title: str = "Source",
    dest_title: str = "Destination",
) -> tuple:
    """Return (source_fig, dest_fig) for side-by-side source↔destination views."""
    src = plate_figure(
        source_format,
        values=source_values,
        highlight=source_highlight,
        title=source_title,
        colorscale="Teal",
    )
    dst = plate_figure(
        dest_format,
        values=dest_values,
        highlight=dest_highlight,
        title=dest_title,
        colorscale="Oranges",
    )
    return src, dst


def mapping_sankey_lite(
    pairs: Sequence[tuple],
    volumes: Optional[Sequence[float]] = None,
    title: str = "Source → Destination mappings",
) -> go.Figure:
    """
    Compact interactive list-style mapping as a Plotly table-like scatter.

    For many pairs a full sankey is cluttered; this shows indexed links.
    """
    if not pairs:
        fig = go.Figure()
        fig.update_layout(title=title + " (none)", height=200)
        return fig

    labels = []
    for i, (s, d) in enumerate(pairs):
        vol = ""
        if volumes is not None and i < len(volumes):
            vol = f"  ({volumes[i]:g} µL)"
        labels.append(f"{s} → {d}{vol}")

    fig = go.Figure(
        data=[
            go.Scatter(
                x=[0] * len(labels),
                y=list(range(len(labels))),
                mode="text",
                text=labels,
                textposition="middle right",
                hovertext=labels,
                hoverinfo="text",
            )
        ]
    )
    fig.update_layout(
        title=title,
        height=min(80 + 22 * len(labels), 500),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, autorange="reversed"),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig
