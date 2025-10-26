os.environ["PYTHONUNBUFFERED"] = "1"
from dotenv import load_dotenv
load_dotenv()

import os
import logging
import sys
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from google.cloud import storage
from scripts.maak_presentatie import maak_presentatie_automatisch

# ✅ Logging naar stdout zodat Cloud Run het logt!
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True  # ✅ OVERRULE UVICORN LOGGING
)

API_KEY = os.getenv("STREAMLIT_API_KEY")
BUCKET_NAME = os.getenv("BUCKET_TEMPLATES")

logging.debug(f"✅ gestart met BUCKET_TEMPLATES = {BUCKET_NAME}")
logging.debug(f"✅ API_KEY loaded? {'✅' if API_KEY else '❌'}")

app = FastAPI(title="Uitvaart Presentatie API ✅")


class GenRequest(BaseModel):
    naam: str
    sjabloon: str
    fotos: List[str] = []
    geboortedatum: Optional[str] = None
    overlijdensdatum: Optional[str] = None


@app.get("/")
def root():
    return {"status": "✅ API actief", "service": "Presentatie generator"}


def _sjabloon_pad_from_id(sjabloon_id: str) -> str:
    logging.debug(f"➡️ _sjabloon_pad_from_id({sjabloon_id})")

    mapping = {
        "Rustig": "SjabloonRustig.pptx",
        "Bloemrijk": "SjabloonBloemrijk.pptx",
        "Modern": "SjabloonModern.pptx",
    }

    if sjabloon_id not in mapping:
        logging.error("❌ Onbekend sjabloon")
        raise HTTPException(status_code=400, detail="Onbekend sjabloon")

    file_name = mapping[sjabloon_id]
    blob_path = f"sjablonen/{file_name}"
    local_path = f"/tmp/{file_name}"

    if not BUCKET_NAME:
        logging.error("❌ BUCKET_TEMPLATES ontbreekt!")
        raise HTTPException(status_code=500, detail="Bucket ontbreekt")

    logging.debug(f"🔎 Zoeken in bucket: {BUCKET_NAME}")
    logging.debug(f"📁 Blob path: {blob_path}")

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_path)

    exists = blob.exists()
    logging.debug(f"📌 Blob exists? {exists}")

    if not exists:
        logging.error("❌ Sjabloon niet gevonden in GCS!")
        raise HTTPException(status_code=404, detail=f"Sjabloon niet gevonden: {sjabloon_id}")

    logging.debug("📥 Downloaden sjabloon...")
    try:
        blob.download_to_filename(local_path)
    except Exception as e:
        logging.exception("❌ Download fout")
        raise HTTPException(status_code=500, detail=str(e))

    logging.debug(f"✅ Presentatie sjabloon lokaal opgeslagen: {local_path}")
    return local_path


@app.post("/generate")
def generate(req: GenRequest, x_streamlit_key: str = Header(default="")):
    logging.debug("🔐 API Key controleren...")

    if not API_KEY or x_streamlit_key != API_KEY:
        logging.error("❌ Unauthorized request")
        raise HTTPException(status_code=401, detail="Unauthorized")

    titel_datums = f"{req.geboortedatum} – {req.overlijdensdatum}" \
        if req.geboortedatum and req.overlijdensdatum else None

    sjabloon_pad = _sjabloon_pad_from_id(req.sjabloon)

    try:
        logging.debug("🎬 PPT genereren gestart...")
        pptx_path = maak_presentatie_automatisch(
            sjabloon_pad=sjabloon_pad,
            base44_foto_urls=req.fotos,
            titel_naam=req.naam,
            titel_datums=titel_datums,
            ratio_mode="cover",
            repeat_if_insufficient=True,
        )
        logging.debug("✅ PPT genereren voltooid!")
    except Exception as e:
        logging.exception("❌ Fout tijdens maken presentatie")
        raise HTTPException(status_code=500, detail=str(e))

    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename="warme_uitvaart_presentatie.pptx",
    )
