import os
import urllib.parse
import streamlit as st
import requests
from dotenv import load_dotenv
from scripts.maak_presentatie import maak_presentatie_automatisch
from urllib.parse import unquote
import re

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
st.write("We helpen u graag bij het maken van een warme en liefdevolle presentatie 🌿")
st.divider()

# ✅ URL naam reconstructie met volledige correctie
query_params = st.query_params
naam_dierbare = ""

# Combineer alle mogelijke delen (Streamlit splitst soms per letter)
for key, val in query_params.items():
    if key.startswith("eerbetoon"):
        naam_dierbare += key.replace("eerbetoon", "")
        naam_dierbare += "".join(val)

# Decoderen en opschonen
naam_dierbare = urllib.parse.unquote(naam_dierbare).strip()

# ✅ Dubbele of onjuiste spaties verwijderen
while "  " in naam_dierbare:
    naam_dierbare = naam_dierbare.replace("  ", " ")

# ✅ Typografische varianten corrigeren
naam_dierbare = (
    naam_dierbare
    .replace("–", "-")
    .replace("—", "-")
    .replace(" - ", "-")
    .replace("- ", "-")
    .replace(" -", "-")
)

# ✅ Voor alle zekerheid: eerste letter hoofdletter
if naam_dierbare:
    naam_dierbare = naam_dierbare[0].upper() + naam_dierbare[1:]

# Debug (kan later weg)
# st.write("✅ Herkende naam voor API:", repr(naam_dierbare))

fotos = []
eerbetoon = {}

if naam_dierbare:
    # Eerste poging: naam direct gebruiken
    fotos, eerbetoon = api_haal_eerbetoon_data(naam_dierbare)

    # Tweede poging: als het een ID is
    if not fotos and len(naam_dierbare) > 10:
        mogelijke_naam = api_haal_naam_via_id(naam_dierbare)
        if mogelijke_naam:
            naam_dierbare = mogelijke_naam
            fotos, eerbetoon = api_haal_eerbetoon_data(naam_dierbare)
else:
    st.info("🌿 Vul hieronder de naam van uw dierbare in om te beginnen.")

# ===================== Formulier =====================
st.subheader("Gegevens van uw dierbare")

naam = eerbetoon.get("naam_dierbare", naam_dierbare)
geboorte = format_date(eerbetoon.get("geboortedatum", ""))
overlijden = format_date(eerbetoon.get("overlijdensdatum", ""))
zin = eerbetoon.get("zin", "")  # of leeg indien niet aanwezig

st.markdown(f"**Naam van dierbare**: {naam}")
st.markdown(f"**Geboortedatum**: {geboorte if geboorte else '—'}")
st.markdown(f"**Overlijdensdatum**: {overlijden if overlijden else '—'}")
st.markdown(f"**Korte zin / motto**: {zin if zin else '—'}")

st.divider()


# ===================== Sfeer =====================
st.subheader("Kies de sfeer van de presentatie")
sfeer = st.radio("Sfeer", ["Rustig", "Bloemrijk", "Modern"], horizontal=True)
sjabloon_pad = f"sjablonen/Sjabloon{sfeer}.pptx"

st.divider()


# ===================== Foto preview =====================
if fotos:
    st.subheader("📸 Goedgekeurde foto's")
    cols = st.columns(3)
    for i, foto in enumerate(fotos):
        with cols[i % 3]:
            st.image(foto, use_container_width=True)
else:
    st.info("ℹ️ We hebben nog geen foto's kunnen vinden. Controleer de naam in Base44.")

st.divider()


# ===================== Genereer Presentatie =====================
st.header("💛 Automatische presentatie")

if st.button("🕊️ Maak de presentatie"):
    with st.spinner("Een moment alstublieft... 🌿"):

        if not fotos:
            st.error("❌ Er zijn nog geen foto's beschikbaar! Controleer Base44.")
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
