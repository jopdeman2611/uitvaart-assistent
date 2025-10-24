import os
import streamlit as st
import requests
from dotenv import load_dotenv
from scripts.maak_presentatie import maak_presentatie_automatisch

# ============== Config ==============
st.set_page_config(page_title="Warme Uitvaartassistent", page_icon="🌿", layout="centered")
load_dotenv()

STREAMLIT_API_KEY = st.secrets.get("STREAMLIT_API_KEY") or os.getenv("STREAMLIT_API_KEY")
BASE44_API_URL = "https://eerbetuiging.base44.app/api/functions/getGoedgekeurdeFotos"

if not STREAMLIT_API_KEY:
    st.error("❌ Geen API-sleutel gevonden.")
    st.stop()

# ============== Helpers ==============
def api_haal_eerbetoon_data(naam_dierbare: str):
    """Haalt foto's + metadata op uit Base44. Geen zichtbare debug."""
    naam_dierbare = " ".join((naam_dierbare or "").split()).strip()
    if not naam_dierbare:
        return [], {}

    try:
        headers = {"X-API-Key": STREAMLIT_API_KEY, "Content-Type": "application/json"}
        payload = {"naam_dierbare": naam_dierbare}
        r = requests.post(BASE44_API_URL, json=payload, headers=headers, timeout=12)

        if not r.ok:
            return [], {}

        data = r.json() or {}
        # Respecteer 'success' als het aanwezig is, maar val niet om als het ontbreekt
        if data.get("success") is False:
            return [], {}

        fotos = data.get("goedgekeurde_fotos") or []
        eerbetoon = data.get("eerbetoon") or {}
        return fotos, eerbetoon
    except Exception:
        return [], {}

def format_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        y, m, d = date_str.split("-")
        return f"{d}-{m}-{y}"
    except Exception:
        return date_str

# ============== UI ==============
st.title("🌿 Warme Uitvaartassistent")
st.write("We helpen u graag bij het maken van een liefdevolle presentatie.")

st.divider()

# 1) Naam uit URL halen en normaliseren (verwijder rare per-letter spacing)
params = st.query_params
eerbetoon_raw = params.get("eerbetoon", [""])[0]
naam_dierbare = " ".join(eerbetoon_raw.split()).strip()

# 2) Slechts één API-call
fotos, eerbetoon = api_haal_eerbetoon_data(naam_dierbare) if naam_dierbare else ([], {})

# 3) Formulier automatisch ingevuld
st.subheader("Gegevens van uw dierbare")

naam = st.text_input(
    "Naam van de overledene",
    value=eerbetoon.get("naam_dierbare", naam_dierbare or "")
)

geboorte = st.text_input(
    "Geboortedatum",
    value=format_date(eerbetoon.get("geboortedatum", ""))
)

overlijden = st.text_input(
    "Overlijdensdatum",
    value=format_date(eerbetoon.get("overlijdensdatum", ""))
)

zin = st.text_input("Korte zin of motto (optioneel)")

st.divider()

# 4) Sfeerkeuze
st.subheader("Kies de sfeer van de presentatie")
sfeer = st.radio("Sfeer", ["Rustig", "Bloemrijk", "Modern"], horizontal=True)
sjabloon_pad = f"sjablonen/Sjabloon{sfeer}.pptx"

st.divider()

# 5) Foto preview
if fotos:
    st.subheader("📸 Goedgekeurde foto's")
    cols = st.columns(3)
    for i, url in enumerate(fotos):
        with cols[i % 3]:
            st.image(url, use_container_width=True)
else:
    st.info("ℹ️ Nog geen goedgekeurde foto's beschikbaar vanuit Base44.")

st.divider()

# 6) Presentatie genereren
st.header("💛 Automatische presentatie")

if st.button("🕊️ Maak de presentatie"):
    with st.spinner("Een moment alstublieft... 🌿"):
        if not fotos:
            st.error("❌ Geen foto's gevonden via Base44.")
            st.stop()

        resultaat = maak_presentatie_automatisch(
            sjabloon_pad=sjabloon_pad,
            base44_foto_urls=fotos,
            titel_naam=naam,
            titel_datums=f"{geboorte} – {overlijden}" if geboorte and overlijden else None,
            titel_bijzin=zin,
            ratio_mode="cover",
            repeat_if_insufficient=True,
        )

        st.success("✅ Presentatie gereed! Download hieronder:")
        with open(resultaat, "rb") as f:
            st.download_button(
                label="📥 Download presentatie (PPTX)",
                data=f,
                file_name="warme_uitvaart_presentatie.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
