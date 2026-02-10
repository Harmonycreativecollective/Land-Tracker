import streamlit as st
from supabase import create_client

def main():
    st.title("Supabase Read Test")

    sb = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SERVICE_ROLE_KEY"],
    )

    res = sb.table("favorites").select("listing_id").limit(1).execute()

    st.write("Supabase read OK:")
    st.write(res.data)

if __name__ == "__main__":
    main()
