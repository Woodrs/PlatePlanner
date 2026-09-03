"""Streamlit page: Bravo uniform stamp planner."""

from __future__ import annotations

import streamlit as st

from plateplanner.exporters.bravo import export_bravo_csv, export_bravo_rows
from plateplanner.models import BravoPlan
from plateplanner.plates import all_wells
from plateplanner.ui.demo_data import demo_bravo_plan
from plateplanner.ui.plates_viz import dual_plate_figures
from plateplanner.concentration import concentration_status_message


def render() -> None:
    st.header("Bravo")
    st.caption("Uniform stamp from source plate → destination plate (same volume all wells)")
    st.info(concentration_status_message())

    if st.button("Load demo plan", key="bravo_demo"):
        st.session_state["bravo_plan"] = demo_bravo_plan()
        st.rerun()

    col1, col2, col3 = st.columns(3)
    with col1:
        src_fmt = st.selectbox("Source plate format", ["96", "384"], index=0, key="br_src_fmt")
        src_id = st.text_input("Source plate ID", value="BRAVO_SRC", key="br_src_id")
    with col2:
        dst_fmt = st.selectbox("Destination plate format", ["96", "384"], index=0, key="br_dst_fmt")
        dst_id = st.text_input("Destination plate ID", value="BRAVO_DST", key="br_dst_id")
    with col3:
        volume = st.number_input("Stamp volume (µL)", min_value=0.0, value=25.0, step=0.5, key="br_vol")
        expand = st.checkbox("Expand CSV to per-well rows", value=False, key="br_expand")

    plan = BravoPlan(
        source_plate_format=src_fmt,
        destination_plate_format=dst_fmt,
        volume_ul=float(volume),
        source_plate_id=src_id,
        destination_plate_id=dst_id,
    )
    st.session_state["bravo_plan"] = plan

    st.subheader("1. Plan")
    st.write(
        f"Stamp **{volume:g} µL** from every well on `{src_id}` ({src_fmt}) "
        f"to the matching well ID on `{dst_id}` ({dst_fmt})."
    )

    st.subheader("2. Review — source ↔ destination")
    shared = sorted(set(all_wells(src_fmt)) & set(all_wells(dst_fmt)))
    src_vals = {w: float(volume) for w in shared}
    dst_vals = {w: float(volume) for w in shared}
    src_fig, dst_fig = dual_plate_figures(
        src_fmt,
        dst_fmt,
        source_values=src_vals,
        dest_values=dst_vals,
        source_highlight=shared[:1],  # show outline cue on A01
        dest_highlight=shared[:1],
        source_title=f"Source {src_id}",
        dest_title=f"Destination {dst_id}",
    )
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(src_fig, use_container_width=True)
    with c2:
        st.plotly_chart(dst_fig, use_container_width=True)

    rows = export_bravo_rows(plan, expand_wells=expand)
    preview = rows if not expand else rows[:24]
    st.dataframe(preview, use_container_width=True)
    if expand and len(rows) > 24:
        st.caption(f"Showing first 24 of {len(rows)} well rows.")

    st.subheader("3. Download CSV")
    csv_text = export_bravo_csv(plan, expand_wells=expand)
    st.download_button(
        label="Download Bravo CSV",
        data=csv_text,
        file_name=f"bravo_{src_id}_to_{dst_id}.csv",
        mime="text/csv",
        key="br_dl",
    )
    with st.expander("CSV schema"):
        st.markdown("**Summary mode**")
        st.code(
            "source_plate_format,destination_plate_format,source_plate_id,"
            "destination_plate_id,volume_ul,transfer_type",
            language="text",
        )
        st.markdown("**Per-well mode** (add `source_well,destination_well`)")
