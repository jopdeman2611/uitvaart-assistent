from dotenv import load_dotenv
load_dotenv()

import os
import logging
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from google.cloud import storage

from scripts.maak_presentatie import maak_presentatie_automatisch

# --- Logging (komt in run.googleapis.com/stderr) ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# API Key
API_KEY = os.getenv("STREAMLIT_API_KEY")

# GCS Bucket met sjablonen
BUCKET_NAME = os.getenv("BUCKET_TEMPLATES")

app = FastAPI(title="Uitvaart Presentatie API")


class GenRequest(BaseModel):
    naam: str
    geboortedatum: Optional[str] = None
    overlijdensdatum: Optional[str] = None
    sjabloon: str                        # "Rustig" | "Bloemrijk" | "Modern"
    fotos: List[str] = []
    slagboom: Optional[bool] = False


def _sjabloon_pad_from_id(sjabloon_id: str) -> str:
    logging.info(f"START ophalen sjabloon: {sjabloon_id}")

    mapping = {
        "Rustig": "SjabloonRustig.pptx",
        "Bloemrijk": "SjabloonBloemrijk.pptx",
        "Modern": "SjabloonModern.pptx",
    }

    if sjabloon_id not in mapping:
        logging.error(f"Onbekend sjabloon gevraagd: {sjabloon_id}")
        raise HTTPException(status_code=400, detail="Onbekend sjabloon")

    file_name = mapping[sjabloon_id]
    local_path = f"/tmp/{file_name}"  # Cloud Run: /tmp is schrijfbaar

    if not BUCKET_NAME:
        logging.error("Env BUCKET_TEMPLATES ontbreekt")
        raise HTTPException(status_code=500, detail="Bucket niet ingesteld")

    logging.info(f"BUCKET_TEMPLATES = {BUCKET_NAME}")
    logging.info("Sjablonen staan in submap: 'sjablonen/'")

    # GCS client + bucket
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    # >>> JOUW STRUCTUUR: bestanden in submap 'sjablonen/'
    blob_path = f"sjablonen/{file_name}"
    blob = bucket.blob(blob_path)
    logging.info(f"Blob pad: {blob_path}")

    if not blob.exists():
        logging.error(f"Sjabloon BESTAAT NIET in bucket op pad: {blob_path}")
        raise HTTPException(status_code=404, detail=f"Sjabloon niet gevonden: {sjabloon_id}")

    if not os.path.exists(local_path):
        logging.info(f"Download sjabloon → {local_path}")
        blob.download_to_filename(local_path)

    logging.info("Sjabloon succesvol opgehaald ✅")
    return local_path


@app.post("/generate")
def generate(req: GenRequest, x_streamlit_key: str = Header(default="")):
    # Auth check
    if not API_KEY or x_streamlit_key != API_KEY:
        logging.warning("401 Unauthorized: header key mismatch/ontbreekt")
        raise HTTPException(status_code=401, detail="Unauthorized")

    titel_datums = None
    if req.geboortedatum and req.overlijdensdatum:
        titel_datums = f"{req.geboortedatum} – {req.overlijdensdatum}"

    try:
        sjabloon_pad = _sjabloon_pad_from_id(req.sjabloon)

        pptx_path = maak_presentatie_automatisch(
            sjabloon_pad=sjabloon_pad,
            base44_foto_urls=req.fotos,
            titel_naam=req.naam,
            titel_datums=titel_datums,
            ratio_mode="cover",
            repeat_if_insufficient=True,
        )
    except HTTPException:
        # Al correcte status/boodschap; laat door FastAPI afhandelen
        raise
    except Exception as e:
        logging.exception("Onverwachte fout tijdens genereren")
        raise HTTPException(status_code=500, detail=str(e))

    filename = "warme_uitvaart_presentatie.pptx"
    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=filename,
    )
