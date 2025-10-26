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

app = FastAPI(title="Uitvaart Presentatie API")


class GenRequest(BaseModel):
    naam: str
    geboortedatum: Optional[str] = None
    overlijdensdatum: Optional[str] = None
    sjabloon: str
    fotos: List[str] = []
    slagboom: Optional[bool] = False


def _sjabloon_pad_from_id(sjabloon_id: str) -> str:
    mapping = {
        "Rustig": "SjabloonRustig.pptx",
        "Bloemrijk": "SjabloonBloemrijk.pptx",
        "Modern": "SjabloonModern.pptx",
    }

    if sjabloon_id not in mapping:
        raise HTTPException(status_code=400,
                            detail=f"Onbekend sjabloon '{sjabloon_id}'. Kies: {list(mapping.keys())}")

    file_name = mapping[sjabloon_id]
    local_path = f"/tmp/{file_name}"

    BUCKET_NAME = os.getenv("BUCKET_TEMPLATES")
    if not BUCKET_NAME:
        raise HTTPException(status_code=500, detail="BUCKET_TEMPLATES ontbreekt")

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    # ✅ Geen subfolder meer — staat in root!
    blob = bucket.blob(file_name)

    if not blob.exists():
        raise HTTPException(status_code=404,
                            detail=f"Sjabloonbestand ontbreekt in bucket: {file_name}")

    if not os.path.exists(local_path):
        blob.download_to_filename(local_path)

    return local_path


@app.post("/generate")
def generate(req: GenRequest, x_streamlit_key: str = Header(default="")):
    if not API_KEY or x_streamlit_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    titel_datums = (
        f"{req.geboortedatum} – {req.overlijdensdatum}"
        if req.geboortedatum and req.overlijdensdatum
        else None
    )

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
        raise HTTPException(status_code=500, detail=f"Presentatie genereren mislukte: {str(e)}")

    return FileResponse(
        pptx_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename="warme_uitvaart_presentatie.pptx",
    )
