import logging
import sys

# ✅ Forceer alle logging naar STDERR zodat Cloud Run het ziet
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True
)

# ✅ Zet ook de Uvicorn loggers op DEBUG
uvicorn_loggers = ["uvicorn", "uvicorn.error", "uvicorn.access"]
for logger_name in uvicorn_loggers:
    logging.getLogger(logger_name).setLevel(logging.DEBUG)

import sys
import traceback

# Log uncaught exceptions rechtstreeks naar stderr
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    print("🔥 UNCAUGHT EXCEPTION 🔥", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)

sys.excepthook = handle_exception


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
    logging.debug(f"➡️ _sjabloon_pad_from_id gestart met: {sjabloon_id}")

    mapping = {
        "Rustig": "SjabloonRustig.pptx",
        "Bloemrijk": "SjabloonBloemrijk.pptx",
        "Modern": "SjabloonModern.pptx",
    }

    logging.debug(f"🧭 Beschikbare mappings: {mapping}")

    if sjabloon_id not in mapping:
        logging.error(f"❌ Onbekend sjabloon: {sjabloon_id}")
        raise HTTPException(status_code=400, detail="Onbekend sjabloon")

    file_name = mapping[sjabloon_id]
    logging.debug(f"📄 Gekozen file_name = {file_name}")

    blob_path = f"sjablonen/{file_name}"
    local_path = f"/tmp/{file_name}"

    logging.debug(f"🗂 Blob pad in bucket: {blob_path}")
    logging.debug(f"📌 Local path wordt: {local_path}")

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_path)

    logging.debug(f"🔍 Blob.exists() == {blob.exists()}")

    try:
        blob.reload()
        logging.debug(f"📏 Grootte blob: {blob.size}")
    except Exception as e:
        logging.error(f"⚠️ Blob reload fout: {e}")

    logging.debug(f"✅ Presentatie sjabloon lokaal opgeslagen: {local_path}")
    return local_path


@app.post("/generate")
def generate(req: GenRequest, x_streamlit_key: str = Header(default="")):
    logging.debug(f"🚀 POST /generate met request: {req}")

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
