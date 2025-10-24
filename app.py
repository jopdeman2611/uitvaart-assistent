import os
import urllib.parse
import streamlit as st
import requests
from dotenv import load_dotenv
from scripts.maak_presentatie import maak_presentatie_automatisch

# ====== BASISINSTELLINGEN ======
st.set_page_config(page_title="Warme Uitvaartassistent", page_icon="🌿", layout="centered")
load_dotenv()

STREAMLIT_API_KEY = st.secrets.get("STREAMLIT_API_KEY") or os.getenv("STREAMLIT_API_KEY")
BASE44_API_URL = "https://eerbetuiging.base44.app/api/functions/getGoedgekeurdeFotos"

if not STREAMLIT_API_KEY:
    st.error("❌ Geen API-sleutel gevonden — neem contact op met beheerder.")
    st.stop()

# ====== HELPERS ======
def api_haal_eerbetoon_data(naam_dierbare: str):
    """Haalt foto's + metadata op uit Base44."""
    try:
        headers = {"X-API-Key": STREAMLIT_API_KEY, "Content-Type": "application/json"}
        payload = {"naam": naam_dierbare}  # ✅ BELANGRIJK → juiste key voor Base44

        r = requests.post(BASE44_API_URL, json=payload, headers=headers, timeout=15)

        # Debug logging zichtbaar in Streamlit interface
        st.write("📡 Verstuurde request payload:")
        st.json(payload)

        st.write("📥 Base44 API Response:")
        try:
            st.json(r.json())
        except:
            st.write(r.text)

        if r.status_code != 200:
            return [], {}

        data = r.json() or {}

        # ✅ Flexibel ophalen van geopende data
        fotos = data.get("fotos") or data.get("goedgekeurde_fotos", []) or []
        eerbetoon = data.get("eerbetoon") or {}

        return fotos, eerbetoon

    except Exception as e:
        st.error(f"⚠️ Base44 foutmelding: {e}")
        return [], {}

def format_date(date_str: str):
    """YYYY-MM-DD → DD-MM-YYYY"""
    if not date_str:
        return ""
    try:
        y, m, d = date_str.split("-")
        return f"{d}-{m}-{y}"
    except:
        return date_str


# ====== UI START ======
st.title("🌿 Warme Uitvaartassistent")
st.write("We helpen u graag bij het maken van een warme en liefdevolle presentatie 🌿")

st.divider()

# ====== NIEUW: URL-Parameter uitlezen ======
query_params = st.query_params
eerbetoon_param = query_params.get("eerbetoon", [""])[0]
naam_dierbare = urllib.parse.unquote(eerbetoon_param).strip()

fotos, eerbetoon = api_haal_eerbetoon_data(naam_dierbare) if naam_dierbare else ([], {})

# ====== FORMULIER ======
st.subheader("Gegevens van uw dierbare")

naam = st.text_input("Naam van de overledene",
                     value=eerbetoon.get("naam_dierbare") 
                     or eerbetoon.get("naam") 
                     or naam_dierbare)

geboorte = st.text_input("Geboortedatum",
                         value=format_date(
                             eerbetoon.get("geboortedatum", "")
                         ))

overlijden = st.text_input("Overlijdensdatum",
                           value=format_date(
                               eerbetoon.get("overlijdensdatum", "")
                           ))

zin = st.text_input("Korte zin of motto (optioneel)")

st.divider()

# ====== SFEERKEUZE ======
st.subheader("Kies de sfeer van de presentatie")
sfeer = st.radio("Sfeer", ["Rustig", "Bloemrijk", "Modern"], horizontal=True)
sjabloon_pad = f"sjablonen/Sjabloon{sfeer}.pptx"

st.divider()

# ====== FOTO PREVIEW ======
if fotos:
    st.subheader("📸 Goedgekeurde foto’s uit Base44")
    cols = st.columns(3)
    for i, url in enumerate(fotos):
        with cols[i % 3]:
            st.image(url, use_container_width=True)
else:
    st.info("ℹ️ Nog geen goedgekeurde foto's beschikbaar vanuit Base44.")

st.divider()

# ====== PRESENTATIE GENEREREN ======
st.header("💛 Automatische presentatie")

if st.button("🕊️ Maak de presentatie"):
    with st.spinner("Een moment alstublieft... de presentatie wordt zorgvuldig samengesteld 🌿"):
        if not fotos:
            st.error("❌ Geen foto’s beschikbaar. Controleer Base44.")
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

        st.success("✅ De presentatie is klaar! Klik hieronder om te downloaden:")
        with open(resultaat, "rb") as f:
            st.download_button(
                label="📥 Download presentatie (PPTX)",
                data=f,
                file_name="warme_uitvaart_presentatie.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )