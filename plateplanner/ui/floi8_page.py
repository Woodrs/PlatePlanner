"""Streamlit page: Floi8 8-channel independent transfer planner."""

from __future__ import annotations

import streamlit as st

from plateplanner.exporters.floi8 import (
    export_floi8_transfer_csv,
    export_floi8_rows,
    parse_floi8_source_csv,
)
from plateplanner.models import (
    Floi8Transfer,
    apply_linear_gradient,
    apply_uniform_volume,
    assign_floi8_channels,
    select_features_by_contents,
    select_features_by_strain_barcodes,
    unique_strain_barcodes,
)
from plateplanner.plates import all_wells, well_id
from plateplanner.ui.demo_data import (
    demo_floi8_source_features,
    demo_floi8_transfers,
    floi8_source_csv_text,
)
from plateplanner.ui.plates_viz import dual_plate_figures, mapping_sankey_lite
from plateplanner.concentration import concentration_status_message


def render() -> None:
    st.header("Floi8")
    st.caption(
        "8 independent channels · source→destination well mapping · "
        "filter by contents or unique strain barcodes · volumes / gradients"
    )
    st.info(concentration_status_message())

    src_fmt = st.selectbox("Source plate format", ["96", "384"], index=0, key="fl_src_fmt")
    dst_fmt = st.selectbox("Destination plate format", ["96", "384"], index=0, key="fl_dst_fmt")

    st.subheader("1. Plan — source features")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Load demo source CSV", key="fl_demo_src"):
            st.session_state["floi8_features"] = demo_floi8_source_features()
            st.session_state["floi8_src_csv"] = floi8_source_csv_text()
            st.rerun()
        if st.button("Load demo transfers", key="fl_demo_xfer"):
            st.session_state["floi8_features"] = demo_floi8_source_features()
            st.session_state["floi8_transfers"] = demo_floi8_transfers()
            st.rerun()
    with c2:
        uploaded = st.file_uploader("Import source features CSV", type=["csv"], key="fl_up")
        if uploaded is not None:
            text = uploaded.read().decode("utf-8")
            try:
                st.session_state["floi8_features"] = parse_floi8_source_csv(text)
                st.session_state["floi8_src_csv"] = text
                st.success(f"Imported {len(st.session_state['floi8_features'])} features")
            except Exception as exc:
                st.error(str(exc))

    if "floi8_features" not in st.session_state:
        st.session_state["floi8_features"] = demo_floi8_source_features()
    if "floi8_transfers" not in st.session_state:
        st.session_state["floi8_transfers"] = demo_floi8_transfers()

    features = st.session_state["floi8_features"]
    st.dataframe(
        [
            {
                "well": f.well,
                "contents": f.contents,
                "strain_barcode": f.strain_barcode,
                "volume_ul": f.volume_ul,
            }
            for f in features
        ],
        use_container_width=True,
    )

    st.markdown("#### Filter / select transfers")
    filter_mode = st.radio(
        "Selection mode",
        ["By contents", "By unique strain barcodes", "Manual well pairs"],
        key="fl_filter_mode",
    )

    selected_features = []
    if filter_mode == "By contents":
        options = sorted({f.contents for f in features if f.contents})
        chosen = st.multiselect("Contents", options, default=options[:1], key="fl_contents")
        for c in chosen:
            selected_features.extend(select_features_by_contents(features, c))
        # de-dupe by well
        seen = set()
        deduped = []
        for f in selected_features:
            if f.well not in seen:
                seen.add(f.well)
                deduped.append(f)
        selected_features = deduped
    elif filter_mode == "By unique strain barcodes":
        uniques = unique_strain_barcodes(features)
        st.caption(f"Unique barcodes on plate: {', '.join(uniques) or '(none)'}")
        chosen_bc = st.multiselect(
            "Strain barcodes (unique only)",
            uniques,
            default=uniques[:4],
            key="fl_barcodes",
        )
        selected_features = select_features_by_strain_barcodes(
            features, chosen_bc, unique_only=True
        )
    else:
        st.caption("Enter source,dest pairs (one per line), e.g. A01,A01")
        default = "\n".join(
            f"{t.source_well},{t.destination_well}"
            for t in st.session_state["floi8_transfers"][:8]
        )
        pair_text = st.text_area("source,dest", value=default, height=120, key="fl_pairs")

    dest_start_row = st.selectbox(
        "Auto-map destination starting row",
        list("ABCDEFGH" if dst_fmt == "96" else "ABCDEFGHIJKLMNOP"),
        key="fl_dst_row",
    )
    vol_mode = st.radio("Volume mode", ["Uniform", "Linear gradient"], key="fl_vol_mode")
    if vol_mode == "Uniform":
        vol_u = st.number_input("Volume (µL)", min_value=0.0, value=12.5, step=0.5, key="fl_vol")
        start_g, end_g = vol_u, vol_u
    else:
        start_g = st.number_input("Gradient start (µL)", min_value=0.0, value=5.0, key="fl_g0")
        end_g = st.number_input("Gradient end (µL)", min_value=0.0, value=40.0, key="fl_g1")

    if st.button("Build transfers from selection", key="fl_build"):
        transfers = []
        if filter_mode == "Manual well pairs":
            feat_by_well = {f.well: f for f in features}
            for line in pair_text.strip().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.replace("\t", ",").split(",")]
                if len(parts) < 2:
                    continue
                sw, dw = parts[0], parts[1]
                f = feat_by_well.get(sw)
                transfers.append(
                    Floi8Transfer(
                        source_well=sw,
                        destination_well=dw,
                        volume_ul=0.0,
                        contents=f.contents if f else "",
                        strain_barcode=f.strain_barcode if f else "",
                    )
                )
        else:
            r0 = ord(dest_start_row) - ord("A")
            max_cols = 12 if dst_fmt == "96" else 24
            for i, f in enumerate(selected_features):
                c = i % max_cols
                r = r0 + i // max_cols
                transfers.append(
                    Floi8Transfer(
                        source_well=f.well,
                        destination_well=well_id(r, c),
                        volume_ul=0.0,
                        contents=f.contents,
                        strain_barcode=f.strain_barcode,
                    )
                )

        if vol_mode == "Uniform":
            transfers = apply_uniform_volume(transfers, float(vol_u))
        else:
            transfers = apply_linear_gradient(transfers, float(start_g), float(end_g))
        transfers = assign_floi8_channels(transfers)
        st.session_state["floi8_transfers"] = transfers
        st.success(f"Built {len(transfers)} transfers")

    transfers = st.session_state["floi8_transfers"]

    st.subheader("2. Review — mapping & plates")
    src_highlight = [t.source_well for t in transfers]
    dst_highlight = [t.destination_well for t in transfers]
    src_vals = {t.source_well: t.volume_ul for t in transfers}
    dst_vals = {}
    for t in transfers:
        dst_vals[t.destination_well] = dst_vals.get(t.destination_well, 0.0) + t.volume_ul

    src_fig, dst_fig = dual_plate_figures(
        src_fmt,
        dst_fmt,
        source_values=src_vals,
        dest_values=dst_vals,
        source_highlight=src_highlight,
        dest_highlight=dst_highlight,
        source_title="Source (selected)",
        dest_title="Destination (mapped)",
    )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(src_fig, use_container_width=True)
    with right:
        st.plotly_chart(dst_fig, use_container_width=True)

    pairs = [(t.source_well, t.destination_well) for t in transfers]
    vols = [t.volume_ul for t in transfers]
    st.plotly_chart(mapping_sankey_lite(pairs, vols), use_container_width=True)

    st.dataframe(export_floi8_rows(transfers), use_container_width=True)

    st.subheader("3. Download CSV")
    csv_text = export_floi8_transfer_csv(transfers)
    st.download_button(
        label="Download Floi8 transfer CSV",
        data=csv_text,
        file_name="floi8_transfers.csv",
        mime="text/csv",
        key="fl_dl",
    )
    with st.expander("CSV schemas"):
        st.markdown("**Source import**")
        st.code("well,contents,strain_barcode,volume_ul", language="text")
        st.markdown("**Transfer export**")
        st.code(
            "channel,source_well,destination_well,volume_ul,contents,strain_barcode",
            language="text",
        )
    st.download_button(
        label="Download demo source features CSV",
        data=floi8_source_csv_text(),
        file_name="floi8_source_features.csv",
        mime="text/csv",
        key="fl_dl_src",
    )
