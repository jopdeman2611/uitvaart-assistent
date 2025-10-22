import os
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
else:
    st.success("🔒 Verbinding met Base44 beveiligd actief.")


# --- FUNCTIE: FOTO'S OPHALEN ---
def haal_goedgekeurde_fotos_op(naam_dierbare):
    """Vraagt goedgekeurde foto's op uit Base44 via POST-request."""
    try:
        headers = {
            "X-API-Key": STREAMLIT_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {"naam_dierbare": naam_dierbare}

        response = requests.post(BASE44_API_URL, json=payload, headers=headers)

        if response.status_code == 200:
            data = response.json()
            return [foto["url"] for foto in data.get("fotos", [])]
        else:
            st.error(f"❌ Fout bij ophalen foto's: {response.status_code}")
            st.text(response.text)
            return []
    except Exception as e:
        st.error(f"⚠️ Er ging iets mis: {e}")
        return []


# --- TITEL EN INTRO ---
st.title("🌿 Warme Uitvaartassistent")
st.write("Ik help u graag bij het samenstellen van een rustige, liefdevolle presentatie.")

st.divider()

# --- 1. FORMULIER VOOR GEGEVENS ---
naam = st.text_input("Naam van de overledene")
geboorte = st.text_input("Geboortedatum")
overlijden = st.text_input("Overlijdensdatum")
zin = st.text_input("Korte zin of motto (optioneel)")

st.divider()

# --- 2. SFEERKEUZE ---
st.write("Kies de sfeer die het beste past bij de persoon of het afscheid.")
sfeer = st.radio(
    "Welke sfeer wilt u graag uitstralen?",
    ["Rustig", "Bloemrijk", "Modern"],
    horizontal=True
)

# Koppel sferen aan sjablonen
sjabloon_map = {
    "Rustig": "sjablonen/SjabloonRustig.pptx",
    "Bloemrijk": "sjablonen/SjabloonBloemrijk.pptx",
    "Modern": "sjablonen/SjabloonModern.pptx"
}
sjabloon_pad = sjabloon_map[sfeer]

st.divider()

# --- 3. FOTO-UPLOAD ---
uploaded_files = st.file_uploader(
    "Upload de foto's (los of als ZIP)",
    type=["jpg", "jpeg", "png", "zip"],
    accept_multiple_files=True
)

st.divider()

# --- 4. URL-PARAMETER (Base44) ---
import urllib.parse

query_params = st.query_params
eerbetoon_values = query_params.get("eerbetoon", ["onbekend"])

if isinstance(eerbetoon_values, list):
    naam_dierbare_raw = "".join(eerbetoon_values)  # combineer losse letters tot één string
else:
    naam_dierbare_raw = eerbetoon_values

naam_dierbare = urllib.parse.unquote(naam_dierbare_raw)

st.write("🔍 Debug – ontvangen eerbetoon parameter:", naam_dierbare)

st.header("📸 Goedgekeurde foto's van Base44")

if naam_dierbare == "onbekend":
    st.warning("⚠️ Geen naam van dierbare gevonden in de URL.")
else:
    fotos = haal_goedgekeurde_fotos_op(naam_dierbare)

    if fotos:
        st.success(f"✅ {len(fotos)} goedgekeurde foto’s gevonden voor {naam_dierbare}.")
        cols = st.columns(3)
        for i, foto_url in enumerate(fotos):
            with cols[i % 3]:
                st.image(foto_url, use_container_width=True)
    else:
        st.info("ℹ️ Er zijn nog geen goedgekeurde foto’s beschikbaar.")

st.divider()

# --- 5. KNOP OM PRESENTATIE TE MAKEN ---
if st.button("💛 Maak de presentatie"):
    with st.spinner("Een moment alstublieft... ik stel de presentatie zorgvuldig samen 🌿"):

        try:
            # Combineer lokale uploads met Base44-foto’s
            upload_paths = []
            if uploaded_files:
                for file in uploaded_files:
                    temp_path = f"temp_{file.name}"
                    with open(temp_path, "wb") as f:
                        f.write(file.getbuffer())
                    upload_paths.append(temp_path)

            # Voeg Base44-foto’s toe (indien aanwezig)
            fotos = haal_goedgekeurde_fotos_op(naam_dierbare)
            upload_paths.extend(fotos)

            # Maak de presentatie
            result_path = maak_presentatie_automatisch(
                sjabloon_pad,
                upload_bestanden=upload_paths,
                titel_naam=naam,
                titel_datums=f"{geboorte} – {overlijden}" if geboorte and overlijden else None,
                titel_bijzin=zin,
            )

            st.success("💛 De presentatie is klaar!")
            with open(result_path, "rb") as f:
                st.download_button(
                    label="📥 Download presentatie",
                    data=f,
                    file_name="uitvaart_presentatie_resultaat.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )

        except Exception as e:
            st.error(f"Er ging iets mis: {e}")
