from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from scripts.maak_presentatie import maak_presentatie_automatisch
import os

app = FastAPI()

class RequestData(BaseModel):
    naam: str
    sjabloon: str
    fotos: list
    datums: str | None = None

@app.get("/")
def root():
    return {"status": "ok", "info": "Presentatie API actief ✅"}

@app.post("/generate")
def generate_presentation(data: RequestData):
    try:
        resultaat_bestand = maak_presentatie_automatisch(
            sjabloon_pad=data.sjabloon,
            base44_foto_urls=data.fotos,
            titel_naam=data.naam,
            titel_datums=data.datums,
            ratio_mode="cover",
            repeat_if_insufficient=True
        )
        return {
            "status": "success",
            "download": resultaat_bestand
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))