from dotenv import load_dotenv
load_dotenv()

from google.cloud import storage
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import FileResponse
import os
import tempfile

from scripts.maak_presentatie import maak_presentatie_automatisch

API_KEY = os.getenv("STREAMLIT_API_KEY")  # hergebruik je bestaande secret
BUCKET_NAME = os.environ.get("BUCKET_TEMPLATES")

app = FastAPI(title="Uitvaart Presentatie API")

class GenRequest(BaseModel):
    naam: str
    geboortedatum: Optional[str] = None
    overlijdensdatum: Optional[str] = None
    sjabloon: str                        # "Rustig" | "Bloemrijk" | "Modern"
    fotos: List[str]

def _sjabloon_pad_from_id(sjabloon_id: str) -> str:
    mapping = {
        "Rustig": "SjabloonRustig",
        "Bloemrijk": "SjabloonBloemrijk",
        "Modern": "SjabloonModern",
    }

    if sjabloon_id not in mapping:
        raise HTTPException(status_code=400, detail="Onbekend sjabloon")

    if not BUCKET_NAME:
        raise HTTPException(status_code=500, detail="Bucket naam ontbreekt (env BUCKET_TEMPLATES)")

    template_name = mapping[sjabloon_id]
    blob_path = f"sjablonen/{template_name}.pptx"

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_path)

    if not blob.exists():
        raise HTTPException(status_code=500, detail=f"Sjabloon niet gevonden: {sjabloon_id}")

    local_path = f"/tmp/{template_name}.pptx"
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
            repeat_if_insufficient=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    filename = "warme_uitvaart_presentatie.pptx"
    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=filename,
    )
