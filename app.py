import streamlit as st

st.set_page_config(
    page_title="KB’s Land Tracker",
    layout="centered",
)

# Immediately send user to Dashboard
st.switch_page("pages/1_dashboard.py")
