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

# ✅ Logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

API_KEY = os.getenv("STREAMLIT_API_KEY")
BUCKET_NAME = os.getenv("BUCKET_TEMPLATES")

logging.debug(f"API_KEY: {API_KEY}")
logging.debug(f"BUCKET_NAME: {BUCKET_NAME}")

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

    logging.debug(f"📌 Bucket: {BUCKET_NAME}")
    logging.debug(f"📌 Blob path: {blob_path}")

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_path)

    # 👇 Debug blob attributes
    logging.debug(f"Blob exists? {blob.exists()}")
    try:
        blob.reload()
        logging.debug(f"Size: {blob.size}")
        logging.debug(f"Updated: {blob.updated}")
    except Exception as e:
        logging.warning(f"Blob reload failed: {str(e)}")

    if not blob.exists():
        raise HTTPException(status_code=404, detail=f"Sjabloon niet gevonden: {sjabloon_id}")

    if not os.path.exists(local_path):
        blob.download_to_filename(local_path)
        logging.debug("✅ Download OK!")

    logging.debug(f"RETURN {local_path}")
    return local_path
   blob = bucket.blob(blob_path)

    if not blob.exists():
        raise HTTPException(status_code=404,
                            detail=f"Sjabloon niet gevonden in bucket: {sjabloon_id}")

    if not os.path.exists(local_path):
        blob.download_to_filename(local_path)

    return local_path


@app.post("/generate")
def generate(req: GenRequest, x_streamlit_key: str = Header(default="")):
    if not API_KEY or x_streamlit_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    titel_datums = None
    if req.geboortedatum and req.overlijdensdatum:
        titel_datums = f"{req.geboortedatum} – {req.overlijdensdatum}"

    sjabloon_pad = _sjabloon_pad_from_id(req.sjabloon)

    try:
        pptx_path = maak_presentatie_automatisch(
            sjabloon_pad=sjabloon_pad,
            base44_foto_urls=req.fotos,
            titel_naam=req.naam,
            titel_datums=titel_datums,
            ratio_mode="cover",
            repeat_if_insufficient=True
        )
    except Exception as e:
        logging.exception("❌ Fout tijdens maken presentatie")
        raise HTTPException(status_code=500, detail=str(e))

    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename="warme_uitvaart_presentatie.pptx",
    )
