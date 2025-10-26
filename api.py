import json
import streamlit as st
from scripts.maak_presentatie import maak_presentatie_automatisch

st.set_page_config(page_title="Presentatie API", page_icon="🕊️")
st.write("")  # Geen UI tonen

query_params = st.experimental_get_query_params()

# ✅ API actief wanneer ?api=1
if query_params.get("api", ["0"])[0] == "1":
    try:
        data = json.loads(query_params.get("data", ["{}"])[0])

        resultaat_pad = maak_presentatie_automatisch(
            sjabloon_pad=data["sjabloon"],
            base44_foto_urls=data["fotos"],
            titel_naam=data["naam"],
            titel_datums=data.get("datums"),
            ratio_mode="cover",
            repeat_if_insufficient=True
        )

        st.json({
            "status": "success",
            "download_url": resultaat_pad
        })

    except Exception as e:
        st.json({
            "status": "error",
            "message": str(e)
        })

    st.stop()