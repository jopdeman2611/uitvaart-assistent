FROM python:3.11-slim

# System dependencies voor Pillow, fonts en PPTX rendering
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
