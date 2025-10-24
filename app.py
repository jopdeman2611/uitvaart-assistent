import os
import urllib.parse
import streamlit as st
import requests
from dotenv import load_dotenv
from scripts.maak_presentatie import maak_presentatie_automatisch

# --- BASISINSTELLINGEN ---
st.set_page_config(page_title="Warme Uitvaartassistent", page_icon="🌿", layout="centered")
load_dotenv()

# --- API-CONFIGURATIE ---
STREAMLIT_API_KEY = st.secrets.get("STREAMLIT_API_KEY", None) or os.getenv("STREAMLIT_API_KEY")
BASE44_API_URL = "https://eerbetuiging.base44.app/api/functions/getGoedgekeurdeFotos"

if not STREAMLIT_API_KEY:
    st.error("❌ Geen API-sleutel gevonden. Voeg STREAMLIT_API_KEY toe in Streamlit secrets of .env.")
    st.stop()

# --- FUNCTIE: FOTO'S + METADATA OPHALEN ---
def haal_goedgekeurde_fotos_op(naam_dierbare: str):
    """Vraagt goedgekeurde foto's én de gegevens van de overledene op (eerbetoon)."""
    try:
        headers = {"X-API-Key": STREAMLIT_API_KEY, "Content-Type": "application/json"}
        payload = {"naam_dierbare": naam_dierbare}
        r = requests.post(BASE44_API_URL, json=payload, headers=headers, timeout=20)

        if r.status_code == 200:
            data = r.json() or {}
            fotos = data.get("goedgekeurde_fotos", []) or []
            eerbetoon = data.get("eerbetoon", {}) or {}
            return fotos, eerbetoon

        st.error(f"❌ Fout bij ophalen: status {r.status_code}")
        return [], {}

    except Exception as e:
        st.error(f"⚠️ Ophalen Base44-data mislukt: {e}")
        return [], {}

# ===========================
# UI
# ===========================

st.title("🌿 Warme Uitvaartassistent")
st.write("Ik help u graag bij het samenstellen van een warme en liefdevolle presentatie.")

st.divider()

# --- 1) EERBETOON-ID UIT URL + DATA OPHALEN ---
query_params = st.query_params
eerbetoon_values = query_params.get("eerbetoon", ["onbekend"])
naam_dierbare = (
    urllib.parse.unquote("".join(eerbetoon_values))
    if isinstance(eerbetoon_values, list)
    else eerbetoon_values
)

fotos, eerbetoon = ([], {})
if naam_dierbare and naam_dierbare != "onbekend":
    fotos, eerbetoon = haal_goedgekeurde_fotos_op(naam_dierbare)

# --- 2) FORMULIER (AUTOMATISCH VOORAF INGEVULD) ---
st.subheader("Gegevens van uw dierbare")
naam = st.text_input("Naam van de overledene", value=eerbetoon.get("naam", ""))
geboorte = st.text_input("Geboortedatum", value=eerbetoon.get("geboortedatum", ""))
overlijden = st.text_input("Overlijdensdatum", value=eerbetoon.get("overlijdensdatum", ""))
zin = st.text_input("Korte zin of motto (optioneel)")

st.divider()

# --- 3) SFEERKEUZE + SJABLOON ---
st.subheader("Kies de sfeer die past bij het afscheid")
sfeer = st.radio("Sfeer", ["Rustig", "Bloemrijk", "Modern"], horizontal=True)

sjabloon_map = {
    "Rustig": "sjablonen/SjabloonRustig.pptx",
    "Bloemrijk": "sjablonen/SjabloonBloemrijk.pptx",
    "Modern": "sjablonen/SjabloonModern.pptx",
}
sjabloon_pad = sjabloon_map[sfeer]

st.divider()

# --- 4) BASE44-FOTO PREVIEW (optioneel) ---
if fotos:
    st.subheader("Goedgekeurde foto's (preview)")
    cols = st.columns(3)
    for i, foto_url in enumerate(fotos):
        with cols[i % 3]:
            st.image(foto_url, use_container_width=True)
else:
    st.info("ℹ️ Er zijn nog geen goedgekeurde foto's beschikbaar voor dit eerbetoon.")

st.divider()

# --- 5) PRESENTATIE GENEREREN ---
st.header("💛 Automatische presentatie")

if st.button("🕊️ Maak de presentatie"):
    with st.spinner("Een moment alstublieft... ik stel de presentatie zorgvuldig samen 🌿"):
        try:
            if not fotos:
                st.error("❌ Geen foto’s gevonden. Controleer a.u.b. uw eerbetoon in Base44.")
                st.stop()

            result_path = maak_presentatie_automatisch(
                sjabloon_pad=sjabloon_pad,
                base44_foto_urls=fotos,
                titel_naam=naam,
                titel_datums=f"{geboorte} – {overlijden}" if geboorte and overlijden else None,
                titel_bijzin=zin,
                ratio_mode="cover",
                repeat_if_insufficient=True,
            )

            st.success("✅ De presentatie is klaar!")
            with open(result_path, "rb") as f:
                st.download_button(
                    label="📥 Download de presentatie (PPTX)",
                    data=f,
                    file_name="warme_uitvaart_presentatie.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
        except Exception:
            st.error("❌ Er is iets misgegaan tijdens het maken van de presentatie.")
