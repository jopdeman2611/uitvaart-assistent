from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from google.cloud import storage

from scripts.maak_presentatie import maak_presentatie_automatisch

# API Key
API_KEY = os.getenv("STREAMLIT_API_KEY")

# GCS Bucket with templates
BUCKET = os.getenv("BUCKET_TEMPLATES")

app = FastAPI(title="Uitvaart Presentatie API")


class GenRequest(BaseModel):
    naam: str
    geboortedatum: Optional[str] = None
    overlijdensdatum: Optional[str] = None
    sjabloon: str
    fotos: List[str]


def _sjabloon_pad_from_id(sjabloon_id: str) -> str:
    mapping = {
        "Rustig": "SjabloonRustig.pptx",
        "Bloemrijk": "SjabloonBloemrijk.pptx",
        "Modern": "SjabloonModern.pptx",
    }

    if sjabloon_id not in mapping:
        raise HTTPException(status_code=400, detail="Onbekend sjabloon")

    file_name = mapping[sjabloon_id]
    local_path = f"/tmp/{file_name}"  # Cloud Run allows writing to /tmp

    if not BUCKET:
        raise HTTPException(status_code=500, detail="Geen BUCKET_TEMPLATES ingesteld")

    client = storage.Client()
    bucket = client.bucket(BUCKET)
    blob = bucket.blob(f"sjablonen/{file_name}")

    if not blob.exists():
        raise HTTPException(status_code=404, detail=f"Sjabloon niet gevonden: {sjabloon_id}")

    # Download only if not already cached
    if not os.path.exists(local_path):
        blob.download_to_filename(local_path)

    return local_path


@app.post("/generate")
def generate(req: GenRequest, x_streamlit_key: str = Header(default="")):
    # Auth check
    if not API_KEY or x_streamlit_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    titel_datums = None
    if req.geboortedatum and req.overlijdensdatum:
        titel_datums = f"{req.geboortedatum} – {req.overlijdensdatum}"

    sjabloon_path = _sjabloon_pad_from_id(req.sjabloon)

    try:
        pptx_path = maak_presentatie_automatisch(
            sjabloon_pad=sjabloon_path,
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
