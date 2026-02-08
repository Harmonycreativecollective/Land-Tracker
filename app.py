import streamlit as st
from pathlib import Path

LOGO_PATH = Path("assets/kblogo.png")

st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="centered",
)

st.title("KB’s Land Tracker")
st.caption("Use the menu (top-left on mobile) to switch between Dashboard and Properties.")

