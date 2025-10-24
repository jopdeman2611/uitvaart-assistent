import os
import urllib.parse
import streamlit as st
import requests
from dotenv import load_dotenv
from scripts.maak_presentatie import maak_presentatie_automatisch

# ===== BASISINSTELLINGEN =====
st.set_page_config(page_title="Warme Uitvaartassistent", page_icon="🌿", layout="centered")
load_dotenv()

STREAMLIT_API_KEY = st.secrets.get("STREAMLIT_API_KEY") or os.getenv("STREAMLIT_API_KEY")
BASE44_API_URL = "https://eerbetuiging.base44.app/api/functions/getGoedgekeurdeFotos"

if not STREAMLIT_API_KEY:
    st.error("❌ API-sleutel ontbreekt")
    st.stop()

# ===== HELPERS =====
def api_haal_eerbetoon_data(naam_dierbare: str):
    """Haalt foto's + gegevens uit Base44 op"""
    try:
        headers = {"X-API-Key": STREAMLIT_API_KEY, "Content-Type": "application/json"}
        payload = {"naam_dierbare": naam_dierbare}  # ✅ juiste payload

        st.write("📤 Verstuurde payload:")
        st.json(payload)

        r = requests.post(BASE44_API_URL, json=payload, headers=headers, timeout=15)

        st.write("📥 API Response:")
        try:
            st.json(r.json())
        except:
            st.write(r.text)

        if r.status_code != 200:
            st.warning(f"⚠️ Base44 gaf fout terug (status {r.status_code})")
            return [], {}

        data = r.json() or {}
        fotos = data.get("goedgekeurde_fotos") or data.get("fotos") or []
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


# ===== UI START =====
st.title("🌿 Warme Uitvaartassistent")

st.divider()

# ====== URL-Parameter uitlezen ======
query_params = st.query_params
eerbetoon_values = query_params.get("eerbetoon", [])

# Join alle delen van de URL terug naar één naam (belangrijk!)
eerbetoon_id = urllib.parse.unquote(" ".join(eerbetoon_values)).replace("+", " ").strip()

st.write("📌 Debug volledige eerbetoon_id:", eerbetoon_id)

fotos, eerbetoon = api_haal_eerbetoon_data(naam_dierbare) if naam_dierbare else ([], {})

# ===== FORMULIER =====
st.subheader("Gegevens van uw dierbare")

naam = st.text_input("Naam van de dierbare",  # ✅ veldnaam aangepast
                     value=eerbetoon.get("naam_dierbare", naam_dierbare))

geboorte = st.text_input("Geboortedatum",
                         value=format_date(eerbetoon.get("geboortedatum", "")))

overlijden = st.text_input("Overlijdensdatum",
                           value=format_date(eerbetoon.get("overlijdensdatum", "")))

zin = st.text_input("Korte zin of motto (optioneel)")

st.divider()

# ===== SFEER =====
st.subheader("Kies de sfeer")
sfeer = st.radio("Sfeer", ["Rustig", "Bloemrijk", "Modern"], horizontal=True)
sjabloon_pad = f"sjablonen/Sjabloon{sfeer}.pptx"

st.divider()

# ===== FOTO'S =====
if fotos:
    st.subheader("📸 Goedgekeurde foto's")
    cols = st.columns(3)
    for i, foto in enumerate(fotos):
        with cols[i % 3]:
            st.image(foto, use_container_width=True)
else:
    st.info("ℹ️ Geen goedgekeurde foto's gevonden.")

st.divider()

# ===== GENEREREN =====
st.header("💛 Automatische presentatie")

if st.button("🕊️ Maak de presentatie"):
    with st.spinner("De presentatie wordt zorgvuldig samengesteld 🌿"):

        if not fotos:
            st.error("❌ Geen foto’s beschikbaar uit Base44")
            st.stop()

        resultaat = maak_presentatie_automatisch(
            sjabloon_pad=sjabloon_pad,
            base44_foto_urls=fotos,
            titel_naam=naam,
            titel_datums=f"{geboorte} – {overlijden}" if geboorte and overlijden else None,
            titel_bijzin=zin
        )

        st.success("✅ De presentatie is klaar!")
        with open(resultaat, "rb") as f:
            st.download_button(
                label="📥 Download presentatie (PPTX)",
                data=f,
                file_name="warme_uitvaart_presentatie.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )