"""Streamlit page: Tempest variable-volume and concentration planner."""

from __future__ import annotations

from typing import Dict, List

import streamlit as st

from plateplanner.concentration import (
    StockDefinition,
    WellVolumeInputs,
    concentration_status_message,
    free_dispense_volume,
    is_concentration_mode_available,
    max_achievable_concentration,
    plan_plate_concentrations,
)
from plateplanner.exporters.tempest import export_tempest_csv, export_tempest_rows
from plateplanner.models import TempestPlan
from plateplanner.plates import all_wells, well_id
from plateplanner.ui.demo_data import (
    demo_concentration_plan,
    demo_tempest_plan,
    tempest_volume_map,
)
from plateplanner.ui.plates_viz import plate_figure


def _ensure_volume_plan(plate_format: str, plate_id: str) -> TempestPlan:
    if "tempest_plan" not in st.session_state:
        st.session_state["tempest_plan"] = demo_tempest_plan()
    plan: TempestPlan = st.session_state["tempest_plan"]
    plan.plate_format = plate_format
    plan.plate_id = plate_id
    return plan


def _render_volume_mode(plate_format: str, plate_id: str) -> None:
    plan = _ensure_volume_plan(plate_format, plate_id)

    st.subheader("1. Plan — assign stock channels (volume mode)")
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


def _render_concentration_mode(plate_format: str, plate_id: str) -> None:
    st.subheader("1. Volume budget (final-volume basis)")
    st.markdown(
        "Concentrations are defined **w.r.t. final target volume**.  \n"
        "`V_free = V_target − V_base − V_inoc` · "
        "`V_reagent = C_target × V_target / C_stock` · "
        "`C_max = C_stock × V_free / V_target` · "
        "`V_normalize = V_free − Σ V_reagent`"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        target_ul = st.number_input(
            "Target final volume (µL)",
            min_value=0.0,
            value=200.0,
            step=1.0,
            key="tmp_c_target",
        )
    with c2:
        base_ul = st.number_input(
            "Base media already in well (µL)",
            min_value=0.0,
            value=100.0,
            step=1.0,
            key="tmp_c_base",
        )
    with c3:
        inoc_ul = st.number_input(
            "Inoculation reserve (µL)",
            min_value=0.0,
            value=10.0,
            step=1.0,
            key="tmp_c_inoc",
        )

    v_free = free_dispense_volume(target_ul, base_ul, inoc_ul)
    if v_free < 0:
        st.error(f"Free dispense volume is negative ({v_free:g} µL). Adjust volumes.")
    else:
        st.success(f"**Free / residual dispense volume:** {v_free:g} µL")

    st.subheader("2. Stocks (up to 12 Tempest channels)")
    n_stocks = st.number_input(
        "Number of reagent stocks",
        min_value=1,
        max_value=11,
        value=2,
        key="tmp_c_nstocks",
    )
    normalize_channel = st.number_input(
        "Normalize / diluent channel",
        min_value=1,
        max_value=12,
        value=12,
        key="tmp_c_norm_ch",
        help="Remaining free volume is dispensed on this channel (default: base media / water).",
    )
    normalize_label = st.text_input(
        "Normalize channel label",
        value="base media",
        key="tmp_c_norm_label",
    )

    stocks: List[StockDefinition] = []
    plate_targets: Dict[int, float] = {}
    stock_cols = st.columns(min(int(n_stocks), 4))
    for i in range(int(n_stocks)):
        col = stock_cols[i % len(stock_cols)]
        with col:
            st.markdown(f"**Stock {i + 1}**")
            ch = st.number_input(
                "Channel",
                min_value=1,
                max_value=12,
                value=i + 1,
                key=f"tmp_c_ch_{i}",
            )
            name = st.text_input("Name", value=f"Stock{i + 1}", key=f"tmp_c_name_{i}")
            c_stock = st.number_input(
                "C_stock",
                min_value=0.0,
                value=1000.0 if i == 0 else 500.0,
                step=10.0,
                key=f"tmp_c_stock_{i}",
            )
            units = st.text_input("Units", value="uM", key=f"tmp_c_units_{i}")
            c_max = (
                max_achievable_concentration(c_stock, max(v_free, 0.0), target_ul)
                if target_ul > 0 and v_free >= 0
                else 0.0
            )
            st.caption(f"C_max = {c_max:g} {units}")
            c_target = st.number_input(
                "C_target (plate-wide)",
                min_value=0.0,
                value=min(50.0 if i == 0 else 25.0, c_max) if c_max > 0 else 0.0,
                step=1.0,
                key=f"tmp_c_tgt_{i}",
            )
            try:
                stocks.append(
                    StockDefinition(
                        channel=int(ch),
                        stock_concentration=float(c_stock),
                        name=name,
                        units=units,
                    )
                )
                plate_targets[int(ch)] = float(c_target)
            except Exception as exc:  # noqa: BLE001 — surface to UI
                st.warning(str(exc))

    wells = all_wells(plate_format)
    selected = st.multiselect(
        "Wells to plan",
        wells,
        default=wells[:8],
        key="tmp_c_wells",
    )

    include_normalize = st.checkbox(
        "Include normalize volume in Tempest CSV (recommended)",
        value=True,
        key="tmp_c_incl_norm",
    )
    cap = st.checkbox(
        "Cap / scale reagents if sum exceeds free volume",
        value=False,
        key="tmp_c_cap",
    )

    col_demo, col_plan = st.columns(2)
    with col_demo:
        if st.button("Load concentration demo", key="tmp_c_demo"):
            demo = demo_concentration_plan(plate_format=plate_format, plate_id=plate_id)
            st.session_state["tempest_conc_result"] = demo
            st.session_state["tempest_plan"] = demo.to_tempest_plan(include_normalize=True)
            st.rerun()
    with col_plan:
        plan_clicked = st.button("Plan from concentrations", type="primary", key="tmp_c_plan")

    if plan_clicked:
        if not selected:
            st.error("Select at least one well.")
        elif v_free < 0:
            st.error("Cannot plan with negative free volume.")
        elif int(normalize_channel) in plate_targets and plate_targets[int(normalize_channel)] > 0:
            st.error(
                f"Normalize channel {int(normalize_channel)} is also used as a reagent "
                "with C_target > 0. Pick a free channel for diluent."
            )
        else:
            try:
                result = plan_plate_concentrations(
                    plate_format=plate_format,
                    plate_id=plate_id,
                    wells=selected,
                    defaults=WellVolumeInputs(target_ul, base_ul, inoc_ul),
                    stocks=stocks,
                    plate_targets=plate_targets,
                    normalize_channel=int(normalize_channel),
                    normalize_label=normalize_label,
                    cap_to_free_volume=cap,
                )
                st.session_state["tempest_conc_result"] = result
                st.session_state["tempest_plan"] = result.to_tempest_plan(
                    include_normalize=include_normalize
                )
                st.success(f"Planned {len(result.wells)} wells.")
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

    result = st.session_state.get("tempest_conc_result")
    plan: TempestPlan = st.session_state.get("tempest_plan") or TempestPlan(
        plate_format=plate_format, plate_id=plate_id
    )
    plan.plate_format = plate_format
    plan.plate_id = plate_id

    if result is not None:
        st.subheader("2b. Planned volumes / concentrations")
        preview_rows = []
        for well, wr in sorted(result.wells.items()):
            row = {
                "well": well,
                "V_target": wr.target_volume_ul,
                "V_base": wr.base_media_volume_ul,
                "V_inoc": wr.inoculation_volume_ul,
                "V_free": wr.free_volume_ul,
                "V_normalize": wr.normalize_volume_ul,
                "normalize_ch": wr.normalize_channel,
            }
            for ch, vol in sorted(wr.reagent_volumes_ul.items()):
                row[f"V_ch{ch}"] = vol
            for ch, c in sorted(wr.target_concentrations.items()):
                row[f"C_ch{ch}"] = c
            for ch, c in sorted(wr.max_concentrations.items()):
                row[f"Cmax_ch{ch}"] = c
            preview_rows.append(row)
        st.dataframe(preview_rows, use_container_width=True)
        st.caption(
            f"Normalize channel **{result.normalize_channel}** "
            f"({result.normalize_label}) pads remaining free volume so all wells "
            f"reach the same final target volume after inoculation."
        )

    st.subheader("3. Review — plate schematic")
    vol_map = tempest_volume_map(plan)
    # Optional: show planned concentration for first stock on hover via values = reagent vol
    fig = plate_figure(
        plate_format,
        values=vol_map,
        highlight=list(vol_map.keys()),
        title=f"Tempest {plate_format}-well · planned Tempest µL (reagents + normalize)",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Per-channel concentration map when available
    if result is not None and result.stocks:
        ch_show = st.selectbox(
            "Color plate by planned concentration (channel)",
            [s.channel for s in result.stocks],
            key="tmp_c_viz_ch",
        )
        conc_map = {
            well: wr.target_concentrations.get(ch_show, 0.0)
            for well, wr in result.wells.items()
            if ch_show in wr.target_concentrations
        }
        fig_c = plate_figure(
            plate_format,
            values=conc_map,
            highlight=list(conc_map.keys()),
            title=f"Target concentration · channel {ch_show}",
            colorscale="Purples",
        )
        # Relabel colorbar conceptually — values are concentration not µL
        fig_c.update_traces(colorbar=dict(title="C"))
        st.plotly_chart(fig_c, use_container_width=True)

    rows = export_tempest_rows(plan)
    st.dataframe(rows, use_container_width=True)

    st.subheader("4. Download CSV")
    csv_text = export_tempest_csv(plan)
    st.download_button(
        label="Download Tempest CSV",
        data=csv_text,
        file_name=f"tempest_conc_{plate_id}_{plate_format}.csv",
        mime="text/csv",
        key="tmp_c_dl",
    )
    with st.expander("CSV schema (concentration mode)"):
        st.markdown(
            "Same Tempest volume schema. Normalize / diluent pad is an ordinary "
            f"**stock_channel** row (default channel **{int(normalize_channel)}**, "
            f"label `{normalize_label}`)."
        )
        st.code(
            "plate_format,plate_id,stock_channel,well,volume_ul\n"
            "96,CONC_001,1,A01,10\n"
            "96,CONC_001,12,A01,80",
            language="csv",
        )


def render() -> None:
    st.header("Tempest")
    st.caption(
        "Variable volumes into 96/384-well plates · up to 12 stock/channels · "
        "volume or concentration planning"
    )

    if is_concentration_mode_available():
        st.info(concentration_status_message())
    else:
        st.warning(concentration_status_message())

    col_a, col_b = st.columns([1, 2])
    with col_a:
        plate_format = st.selectbox("Plate format", ["96", "384"], index=0, key="tmp_fmt")
        plate_id = st.text_input("Plate ID", value="DEST_001", key="tmp_pid")
        planning_mode = st.radio(
            "Planning mode",
            ["Volume", "Concentration"],
            horizontal=True,
            key="tmp_planning_mode",
        )
        if planning_mode == "Volume" and st.button("Load volume demo plan", key="tmp_demo"):
            st.session_state["tempest_plan"] = demo_tempest_plan()
            st.session_state["tempest_plan"].plate_format = plate_format
            st.session_state["tempest_plan"].plate_id = plate_id
            st.rerun()

    if planning_mode == "Concentration":
        _render_concentration_mode(plate_format, plate_id)
    else:
        _render_volume_mode(plate_format, plate_id)
