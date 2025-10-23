import os
import urllib.parse
import streamlit as st
import requests
from dotenv import load_dotenv
from scripts.maak_presentatie import maak_presentatie_automatisch


# --- BASISINSTELLINGEN ---
st.set_page_config(page_title="Warme Uitvaartassistent", page_icon="🌿", layout="centered")

# Laad .env-bestand
load_dotenv()

# --- API-CONFIGURATIE ---
STREAMLIT_API_KEY = st.secrets.get("STREAMLIT_API_KEY", None) or os.getenv("STREAMLIT_API_KEY")
BASE44_API_URL = "https://eerbetuiging.base44.app/api/functions/getGoedgekeurdeFotos"

# --- CONTROLE OP SLEUTEL ---
if not STREAMLIT_API_KEY:
    st.error("❌ Geen API-sleutel gevonden. Controleer de Streamlit secrets-configuratie.")
# else:
#     st.success("🔒 Verbinding met Base44 beveiligd actief.")

# --- FUNCTIE: FOTO'S OPHALEN ---
def haal_goedgekeurde_fotos_op(naam_dierbare):
    """Vraagt goedgekeurde foto's op uit Base44 via POST-request."""
    try:
        headers = {"X-API-Key": STREAMLIT_API_KEY, "Content-Type": "application/json"}
        payload = {"naam_dierbare": naam_dierbare}
        response = requests.post(BASE44_API_URL, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "goedgekeurde_fotos" in data:
                return data["goedgekeurde_fotos"]
            else:
                return []
        else:
            st.error(f"❌ Fout bij ophalen foto's ({response.status_code})")
            return []
    except Exception as e:
        st.error(f"⚠️ Er ging iets mis: {e}")
        return []

# --- TITEL & INTRO ---
st.title("🌿 Warme Uitvaartassistent")
st.write("Ik help u graag bij het samenstellen van een warme en liefdevolle presentatie.")

st.divider()

# --- 1. FORMULIER VOOR GEGEVENS ---
naam = st.text_input("Naam van de overledene")
geboorte = st.text_input("Geboortedatum")
overlijden = st.text_input("Overlijdensdatum")
zin = st.text_input("Korte zin of motto (optioneel)")

st.divider()

# --- 2. SFEERKEUZE ---
st.subheader("Kies de sfeer die past bij het afscheid")
sfeer = st.radio("Sfeer", ["Rustig", "Bloemrijk", "Modern"], horizontal=True)

# Koppel sferen aan sjablonen
sjabloon_map = {
    "Rustig": "sjablonen/SjabloonRustig.pptx",
    "Bloemrijk": "sjablonen/SjabloonBloemrijk.pptx",
    "Modern": "sjablonen/SjabloonModern.pptx"
}
sjabloon_pad = sjabloon_map[sfeer]

st.divider()

# --- 3. FOTO'S UIT BASE44 VIA URL (geen handmatige upload meer) ---

query_params = st.query_params
eerbetoon_values = query_params.get("eerbetoon", ["onbekend"])
naam_dierbare = urllib.parse.unquote("".join(eerbetoon_values)) if isinstance(eerbetoon_values, list) else eerbetoon_values

st.subheader("📸 Goedgekeurde foto's van Base44")

fotos = []
if naam_dierbare != "onbekend":
    fotos = haal_goedgekeurde_fotos_op(naam_dierbare)

if fotos:
    st.success(f"✅ {len(fotos)} foto’s automatisch gevonden")
    cols = st.columns(3)
    for i, foto_url in enumerate(fotos):
        with cols[i % 3]:
            st.image(foto_url, use_container_width=True)
else:
    st.info("ℹ️ Er zijn nog geen goedgekeurde foto's beschikbaar.")

st.divider()

# --- 4. PRESENTATIE GENEREREN ---

st.header("💛 Automatische presentatie")

if st.button("🕊️ Maak de presentatie"):
    with st.spinner("Een moment alstublieft... ik stel de presentatie zorgvuldig samen 🌿"):
        try:
            if not fotos:
                st.error("❌ Geen foto’s gevonden. Controleer aub bij Base44.")
                st.stop()

            result_path = maak_presentatie_automatisch(
                sjabloon_pad=sjabloon_pad,
                base44_foto_urls=fotos,
                titel_naam=naam,
                titel_datums=f"{geboorte} – {overlijden}" if geboorte and overlijden else None,
                titel_bijzin=zin,
                ratio_mode="cover",
                repeat_if_insufficient=True
            )

            st.success("✅ De presentatie is klaar!")
            with open(result_path, "rb") as f:
                st.download_button(
                    label="📥 Download de presentatie (PPTX)",
                    data=f,
                    file_name="warme_uitvaart_presentatie.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )
        except Exception as e:
            st.error("❌ Er is iets misgegaan tijdens het maken van de presentatie.")