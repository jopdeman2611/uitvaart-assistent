import os
import urllib.parse
import streamlit as st
import requests
from dotenv import load_dotenv
from scripts.maak_presentatie import maak_presentatie_automatisch

# ===================== Config =====================
st.set_page_config(page_title="Warme Uitvaartassistent", page_icon="🌿", layout="centered")
load_dotenv()

STREAMLIT_API_KEY = st.secrets.get("STREAMLIT_API_KEY") or os.getenv("STREAMLIT_API_KEY")
BASE44_API_URL = "https://eerbetuiging.base44.app/api/functions/getGoedgekeurdeFotos"
BASE44_EERBETOON_BY_ID_URL = "https://eerbetuiging.base44.app/api/functions/getEerbetoonById"

if not STREAMLIT_API_KEY:
    st.error("❌ Geen API-sleutel gevonden — neem aub contact op met beheerder.")
    st.stop()


# ===================== Helpers =====================
def api_haal_eerbetoon_data(naam_dierbare: str):
    try:
        headers = {"X-API-Key": STREAMLIT_API_KEY, "Content-Type": "application/json"}
        r = requests.post(BASE44_API_URL, json={"naam_dierbare": naam_dierbare}, headers=headers, timeout=15)
        if r.status_code != 200:
            return [], {}
        data = r.json() or {}
        return data.get("goedgekeurde_fotos", []) or [], data.get("eerbetoon", {}) or {}
    except:
        return [], {}


def api_haal_naam_via_id(eerbetoon_id: str):
    try:
        headers = {"X-API-Key": STREAMLIT_API_KEY, "Content-Type": "application/json"}
        r = requests.post(BASE44_EERBETOON_BY_ID_URL, json={"id": eerbetoon_id}, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json() or {}
        return data.get("naam_dierbare")
    except:
        return None


def format_date(date_str):
    if not date_str:
        return ""
    try:
        y, m, d = date_str.split("-")
        return f"{d}-{m}-{y}"
    except:
        return date_str


# ===================== UI =====================
st.title("🌿 Warme Uitvaartassistent")
st.divider()

# ✅ URL parameter uitlezen
query_params = st.query_params

# ✅ Combineer alle delen van eerbetoon weer tot één string
eerbetoon_parts = []
for key, value in query_params.items():
    if key.startswith("eerbetoon"):
        eerbetoon_parts.append(value[0])

eerbetoon_raw = " ".join(eerbetoon_parts).strip()

naam_dierbare = ""
fotos = []
eerbetoon = {}

if eerbetoon_raw:
    # ✅ Eerste poging: behandelen als naam
    naam_dierbare = " ".join(eerbetoon_raw.split())
    fotos, eerbetoon = api_haal_eerbetoon_data(naam_dierbare)

    # ✅ Tweede poging: behandelen als ID
    if not fotos and len(eerbetoon_raw) > 10:
        mogelijke_naam = api_haal_naam_via_id(eerbetoon_raw)
        if mogelijke_naam:
            naam_dierbare = mogelijke_naam
            fotos, eerbetoon = api_haal_eerbetoon_data(naam_dierbare)


# ===================== Formulier =====================
st.subheader("Gegevens van uw dierbare")
naam = st.text_input("Naam van de overledene", value=eerbetoon.get("naam_dierbare", naam_dierbare))
geboorte = st.text_input("Geboortedatum", value=format_date(eerbetoon.get("geboortedatum", "")))
overlijden = st.text_input("Overlijdensdatum", value=format_date(eerbetoon.get("overlijdensdatum", "")))
zin = st.text_input("Korte zin of motto (optioneel)")

st.divider()

st.subheader("Kies de sfeer van de presentatie")
sfeer = st.radio("Sfeer", ["Rustig", "Bloemrijk", "Modern"], horizontal=True)
sjabloon_pad = f"sjablonen/Sjabloon{sfeer}.pptx"

st.divider()

if fotos:
    st.subheader("📸 Goedgekeurde foto's")
    cols = st.columns(3)
    for i, foto in enumerate(fotos):
        with cols[i % 3]:
            st.image(foto, use_container_width=True)
else:
    st.info("ℹ️ Geen foto's gevonden. Controleer of de naam klopt in Base44.")

st.divider()

st.header("💛 Automatische presentatie")

if st.button("🕊️ Maak de presentatie"):
    with st.spinner("Een moment alstublieft... 🌿"):

        if not fotos:
            st.error("❌ Geen foto's beschikbaar. Controleer Base44.")
            st.stop()

        resultaat = maak_presentatie_automatisch(
            sjabloon_pad=sjabloon_pad,
            base44_foto_urls=fotos,
            titel_naam=naam,
            titel_datums=f"{geboorte} – {overlijden}" if geboorte and overlijden else None,
            titel_bijzin=zin,
            ratio_mode="cover",
            repeat_if_insufficient=True
        )

        st.success("✅ Presentatie gereed! Download hieronder:")
        with open(resultaat, "rb") as f:
            st.download_button(
                label="📥 Download presentatie (PPTX)",
                data=f,
                file_name="warme_uitvaart_presentatie.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
