from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from scripts.maak_presentatie import maak_presentatie_automatisch

class PresentatieRequest(BaseModel):
    naam: str
    fotos: list
    sjabloon: str
    datums: str | None = None

app = FastAPI()

@app.post("/generate")
async def generate_presentation(req: PresentatieRequest):
    try:
        resultaat_pad = maak_presentatie_automatisch(
            sjabloon_pad=req.sjabloon,
            base44_foto_urls=req.fotos,
            titel_naam=req.naam,
            titel_datums=req.datums,
            ratio_mode="cover",
            repeat_if_insufficient=True
        )

        return JSONResponse(content={
            "status": "success",
            "download_url": resultaat_pad
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))