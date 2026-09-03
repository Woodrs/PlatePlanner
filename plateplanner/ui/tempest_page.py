"""Streamlit page: Tempest variable-volume planner."""

from __future__ import annotations

import streamlit as st

from plateplanner.exporters.tempest import export_tempest_csv, export_tempest_rows
from plateplanner.models import TempestPlan, WellVolume
from plateplanner.plates import all_wells, well_id
from plateplanner.ui.demo_data import demo_tempest_plan, tempest_volume_map
from plateplanner.ui.plates_viz import plate_figure
from plateplanner.concentration import concentration_status_message


def render() -> None:
    st.header("Tempest")
    st.caption(
        "Variable volumes into 96/384-well plates · up to 12 stock/channels · per-well volumes"
    )
    st.info(concentration_status_message())

    col_a, col_b = st.columns([1, 2])
    with col_a:
        plate_format = st.selectbox("Plate format", ["96", "384"], index=0, key="tmp_fmt")
        plate_id = st.text_input("Plate ID", value="DEST_001", key="tmp_pid")
        if st.button("Load demo plan", key="tmp_demo"):
            st.session_state["tempest_plan"] = demo_tempest_plan()
            st.session_state["tempest_plan"].plate_format = plate_format
            st.session_state["tempest_plan"].plate_id = plate_id
            st.rerun()

    if "tempest_plan" not in st.session_state:
        st.session_state["tempest_plan"] = demo_tempest_plan()

    plan: TempestPlan = st.session_state["tempest_plan"]
    plan.plate_format = plate_format
    plan.plate_id = plate_id

    st.subheader("1. Plan — assign stock channels")
    channel = st.selectbox("Stock / channel (1–12)", list(range(1, 13)), index=0, key="tmp_ch")

    wells = all_wells(plate_format)
    existing = {
        wv.well: wv.volume_ul for wv in plan.stock_volumes.get(channel, [])
    }

    mode = st.radio(
        "Edit mode",
        ["Uniform fill (selected wells)", "Row gradient", "Edit via CSV-like table"],
        key="tmp_mode",
    )

    if mode == "Uniform fill (selected wells)":
        selected = st.multiselect(
            "Wells",
            wells,
            default=sorted(existing.keys())[:8] if existing else wells[:8],
            key="tmp_wells",
        )
        vol = st.number_input("Volume (µL)", min_value=0.0, value=10.0, step=0.5, key="tmp_vol")
        if st.button("Apply to channel", key="tmp_apply_uniform"):
            merged = dict(existing)
            for w in selected:
                merged[w] = float(vol)
            plan.assign_stock(channel, merged)
            st.success(f"Assigned stock {channel} → {len(selected)} wells @ {vol:g} µL")

    elif mode == "Row gradient":
        row_letter = st.selectbox(
            "Row",
            list("ABCDEFGH" if plate_format == "96" else "ABCDEFGHIJKLMNOP"),
            key="tmp_row",
        )
        start_v = st.number_input("Start µL (col 01)", min_value=0.0, value=5.0, key="tmp_g0")
        end_v = st.number_input("End µL (last col)", min_value=0.0, value=30.0, key="tmp_g1")
        cols = 12 if plate_format == "96" else 24
        if st.button("Apply row gradient", key="tmp_apply_grad"):
            r = ord(row_letter) - ord("A")
            merged = dict(existing)
            for c in range(cols):
                frac = c / (cols - 1) if cols > 1 else 0
                merged[well_id(r, c)] = round(start_v + frac * (end_v - start_v), 4)
            plan.assign_stock(channel, merged)
            st.success(f"Gradient on row {row_letter} for stock {channel}")

    else:
        st.caption("Enter well,volume pairs (one per line), e.g. A01,10")
        default_lines = "\n".join(f"{w},{v:g}" for w, v in sorted(existing.items()))
        text = st.text_area("well,volume_ul", value=default_lines, height=160, key="tmp_table")
        if st.button("Parse & assign", key="tmp_apply_table"):
            merged = {}
            for line in text.strip().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.replace("\t", ",").split(",")]
                if len(parts) < 2:
                    continue
                merged[parts[0]] = float(parts[1])
            plan.assign_stock(channel, merged)
            st.success(f"Assigned {len(merged)} wells to stock {channel}")

    st.session_state["tempest_plan"] = plan

    # Channel summary
    with st.expander("Assigned stocks summary", expanded=True):
        if not plan.stock_volumes:
            st.write("No stocks assigned yet.")
        else:
            for ch in sorted(plan.stock_volumes):
                n = len(plan.stock_volumes[ch])
                total = sum(wv.volume_ul for wv in plan.stock_volumes[ch])
                st.write(f"**Channel {ch}**: {n} wells, Σ {total:g} µL")

    st.subheader("2. Review — plate schematic")
    vol_map = tempest_volume_map(plan)
    active_wells = [wv.well for wv in plan.stock_volumes.get(channel, [])]
    fig = plate_figure(
        plate_format,
        values=vol_map,
        highlight=active_wells,
        title=f"Tempest {plate_format}-well · total µL (highlight = channel {channel})",
    )
    st.plotly_chart(fig, use_container_width=True)

    rows = export_tempest_rows(plan)
    st.dataframe(rows, use_container_width=True)

    st.subheader("3. Download CSV")
    csv_text = export_tempest_csv(plan)
    st.download_button(
        label="Download Tempest CSV",
        data=csv_text,
        file_name=f"tempest_{plate_id}_{plate_format}.csv",
        mime="text/csv",
        key="tmp_dl",
    )
    with st.expander("CSV schema"):
        st.code(
            "plate_format,plate_id,stock_channel,well,volume_ul\n"
            "96,DEST_001,1,A01,5",
            language="csv",
        )
