import os
import streamlit as st
import requests
from dotenv import load_dotenv
from scripts.maak_presentatie import maak_presentatie_automatisch

# Laad .env-bestand
load_dotenv()

# Base44 API-configuratie
STREAMLIT_API_KEY = st.secrets.get("STREAMLIT_API_KEY", None) or os.getenv("STREAMLIT_API_KEY")
BASE44_API_URL = "https://base44.app/api/fotos/goedgekeurd"

# Controleer of de sleutel beschikbaar is
if not STREAMLIT_API_KEY:
    st.error("❌ Geen API-sleutel gevonden. Controleer de Streamlit secrets-configuratie.")
else:
    st.success("🔒 Verbinding met Base44 beveiligd actief.")


def haal_goedgekeurde_fotos_op(eerbetoon_id):
    """Vraagt goedgekeurde foto's op uit Base44 voor het opgegeven eerbetoon."""
    try:
        headers = {"Authorization": f"Bearer {STREAMLIT_API_KEY}"}
        response = requests.get(f"{BASE44_API_URL}?eerbetoon_id={eerbetoon_id}", headers=headers)

        if response.status_code == 200:
            data = response.json()
            return [foto["url"] for foto in data]
        else:
            st.error(f"❌ Fout bij ophalen foto's: {response.status_code}")
            return []
    except Exception as e:
        st.error(f"⚠️ Er ging iets mis: {e}")
        return []

st.set_page_config(page_title="Warme Uitvaartassistent", page_icon="🌿", layout="centered")

st.title("🌿 Warme Uitvaartassistent")
st.write("Ik help u graag bij het samenstellen van een rustige, liefdevolle presentatie.")

st.divider()

# --- 1. Gegevens ---
naam = st.text_input("Naam van de overledene")
geboorte = st.text_input("Geboortedatum")
overlijden = st.text_input("Overlijdensdatum")
zin = st.text_input("Korte zin of motto (optioneel)")

st.divider()

# --- 2. Sfeerkeuze ---
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

# --- 3. Foto-upload ---
uploaded_files = st.file_uploader(
    "Upload de foto's (los of als ZIP)",
    type=["jpg", "jpeg", "png", "zip"],
    accept_multiple_files=True
)

st.divider()

# --- 4. Knop om presentatie te maken ---
if st.button("💛 Maak de presentatie"):
    with st.spinner("Een moment alstublieft... ik stel de presentatie zorgvuldig samen 🌿"):
        # Hier komt straks automatisch het juiste eerbetoon_id
        eerbetoon_id = 123  

        fotos = haal_goedgekeurde_fotos_op(eerbetoon_id)

        if fotos:
            st.success(f"✅ {len(fotos)} goedgekeurde foto's opgehaald uit Base44!")
            for foto in fotos:
                st.image(foto, width=200)
        else:
            st.warning("Er zijn nog geen goedgekeurde foto's gevonden.")


            try:
                result_path = maak_presentatie_automatisch(
                    sjabloon_pad,
                    upload_bestanden=upload_paths,
                    titel_naam=naam,
                    titel_datums=f"{geboorte} – {overlijden}" if geboorte and overlijden else None,
                    titel_bijzin=zin,
                )

                st.success("De presentatie is klaar 💛")
                with open(result_path, "rb") as f:
                    st.download_button(
                        label="📥 Download presentatie",
                        data=f,
                        file_name="uitvaart_presentatie_resultaat.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                    )

            except Exception as e:
                st.error(f"Er ging iets mis: {e}")

st.header("📸 Goedgekeurde foto's van Base44")

# Vraag de eerbetoon-ID op uit de URL (bijv. ...?eerbetoon=123)
query_params = st.query_params
eerbetoon_id = query_params.get("eerbetoon", ["onbekend"])[0]

if eerbetoon_id == "onbekend":
    st.warning("⚠️ Geen eerbetoon-ID gevonden in de URL.")
else:
    fotos = haal_goedgekeurde_fotos_op(eerbetoon_id)

    if fotos:
        st.success(f"✅ {len(fotos)} foto’s gevonden voor eerbetoon-ID: {eerbetoon_id}")
        cols = st.columns(3)
        for i, foto_url in enumerate(fotos):
            with cols[i % 3]:
                st.image(foto_url, use_container_width=True)
    else:
        st.info("ℹ️ Er zijn nog geen goedgekeurde foto’s beschikbaar.")

