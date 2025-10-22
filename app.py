import streamlit as st
import os
from scripts.maak_presentatie import maak_presentatie_automatisch

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
    if not uploaded_files or not naam:
        st.error("Voeg ten minste één foto toe en vul de naam in.")
    else:
        with st.spinner("Een moment alstublieft... ik stel de presentatie zorgvuldig samen 🌿"):
            upload_paths = []
            os.makedirs("uploads", exist_ok=True)
            for file in uploaded_files:
                path = os.path.join("uploads", file.name)
                with open(path, "wb") as f:
                    f.write(file.getbuffer())
                upload_paths.append(path)

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
