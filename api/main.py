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


# ✅ VOLLEDIGE DEBUG LOGGING
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ✅ EXTRA: Log alle env vars
logging.debug(f"STREAMLIT_API_KEY: {os.getenv('STREAMLIT_API_KEY')}")
logging.debug(f"BUCKET_TEMPLATES: {os.getenv('BUCKET_TEMPLATES')}")

API_KEY = os.getenv("STREAMLIT_API_KEY")
BUCKET_NAME = os.getenv("BUCKET_TEMPLATES")

app = FastAPI(title="Uitvaart Presentatie API")


class GenRequest(BaseModel):
    naam: str
    geboortedatum: Optional[str] = None
    overlijdensdatum: Optional[str] = None
    sjabloon: str
    fotos: List[str] = []
    slagboom: Optional[bool] = False


def _sjabloon_pad_from_id(sjabloon_id: str) -> str:
    logging.debug(f"START _sjabloon_pad_from_id({sjabloon_id})")

    mapping = {
        "Rustig": "SjabloonRustig.pptx",
        "Bloemrijk": "SjabloonBloemrijk.pptx",
        "Modern": "SjabloonModern.pptx",
    }

    if sjabloon_id not in mapping:
        logging.error("Onbekend sjabloon!")
        raise HTTPException(status_code=400, detail="Onbekend sjabloon")

    file_name = mapping[sjabloon_id]
    blob_path = f"sjablonen/{file_name}"
    local_path = f"/tmp/{file_name}"

    logging.debug(f"Blob path: {blob_path}")
    logging.debug(f"Local tmp path: {local_path}")

    if not BUCKET_NAME:
        logging.error("❌ Env var BUCKET_TEMPLATES ontbreekt!")
        raise HTTPException(status_code=500, detail="Bucket onbekend")

    logging.debug(f"Bucket: {BUCKET_NAME}")

    # ✅ client + bucket
    try:
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_path)
    except Exception as e:
        logging.exception("❌ Bucket access error")
        raise HTTPException(status_code=500, detail=str(e))

    logging.debug(f"Blob exists?: {blob.exists()}")

    if not blob.exists():
        logging.error(f"❌ Sjabloon bestaat niet op: {blob_path}")
        raise HTTPException(status_code=404, detail=f"Sjabloon niet gevonden: {sjabloon_id}")

    try:
        if not os.path.exists(local_path):
            logging.debug("📥 Download sjabloon...")
            blob.download_to_filename(local_path)
            logging.debug("✅ Download OK!")
    except Exception as e:
        logging.exception("❌ FOUT tijdens download")
        raise HTTPException(status_code=500, detail=str(e))

    return local_path


@app.post("/generate")
def generate(req: GenRequest, x_streamlit_key: str = Header(default="")):
    logging.debug("🔐 Validating key...")

    if not API_KEY or x_streamlit_key != API_KEY:
        logging.error("❌ Incorrect API key")
        raise HTTPException(status_code=401, detail="Unauthorized")

    logging.debug("✅ API Key OK!")

    titel_datums = f"{req.geboortedatum} – {req.overlijdensdatum}" if req.geboortedatum and req.overlijdensdatum else None
    sjabloon_pad = _sjabloon_pad_from_id(req.sjabloon)

    try:
        logging.debug("🎬 Start PPT genereren...")
        pptx_path = maak_presentatie_automatisch(
            sjabloon_pad=sjabloon_pad,
            base44_foto_urls=req.fotos,
            titel_naam=req.naam,
            titel_datums=titel_datums,
            ratio_mode="cover",
            repeat_if_insufficient=True,
        )
        logging.debug("✅ PPT klaar!")
    except Exception as e:
        logging.exception("❌ Fout bij maken presentatie")
        raise HTTPException(status_code=500, detail=str(e))

    filename = "warme_uitvaart_presentatie.pptx"
    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=filename,
    )
