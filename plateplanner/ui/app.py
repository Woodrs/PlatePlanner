"""PlatePlanner Streamlit entrypoint.

Run:
    streamlit run plateplanner/ui/app.py
"""

from __future__ import annotations

import streamlit as st

from plateplanner import __version__
from plateplanner.ui import bravo_page, floi8_page, tempest_page
from plateplanner.concentration import concentration_status_message


def main() -> None:
    st.set_page_config(
        page_title="PlatePlanner",
        page_icon="🧪",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("PlatePlanner")
    st.markdown(
        f"Laboratory liquid-transfer planner for **Tempest**, **Bravo**, and **Floi8** "
        f"(v{__version__}). Volume transfers only."
    )

    with st.sidebar:
        st.header("Instrument")
        instrument = st.radio(
            "Select instrument",
            ["Tempest", "Bravo", "Floi8"],
            key="instrument",
        )
        st.divider()
        st.caption(concentration_status_message())
        st.markdown(
            """
**Flow:** plan → review → download CSV

Demo data is loaded by default on each instrument page.
"""
        )

    if instrument == "Tempest":
        tempest_page.render()
    elif instrument == "Bravo":
        bravo_page.render()
    else:
        floi8_page.render()


if __name__ == "__main__":
    main()
