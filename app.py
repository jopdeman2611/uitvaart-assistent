import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from scripts.maak_presentatie import maak_presentatie_automatisch

app = FastAPI()

class PresentatieData(BaseModel):
    naam: str
    sjabloon: str
    fotos: list[str]
    datums: str | None = None

@app.get("/")
def home():
    return {"status": "online"}

@app.post("/generate")
def generate(data: PresentatieData):
    try:
        resultaat_pad = maak_presentatie_automatisch(
            sjabloon_pad=data.sjabloon,
            base44_foto_urls=data.fotos,
            titel_naam=data.naam,
            titel_datums=data.datums,
            ratio_mode="cover",
            repeat_if_insufficient=True
        )
        return {"status": "success", "download_url": resultaat_pad}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
