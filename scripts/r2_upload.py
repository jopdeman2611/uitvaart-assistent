import boto3, os
from dotenv import load_dotenv

# .env-bestand laden (zorgt dat sleutels uit .env gelezen worden)
load_dotenv()

# Verbinding maken met Cloudflare R2
session = boto3.session.Session()
s3 = session.client(
    's3',
    endpoint_url=os.getenv("R2_ENDPOINT"),
    aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("R2_SECRET_KEY")
)

def upload_bestand(file_path, doel_pad):
    """Upload een bestand naar de R2 bucket."""
    try:
        bucket = os.getenv("R2_BUCKET")
        s3.upload_file(file_path, bucket, doel_pad)
        print(f"✅ Bestand geüpload naar R2: {doel_pad}")
    except Exception as e:
        print("❌ Er ging iets mis bij het uploaden:", e)

def maak_tijdelijke_downloadlink(doel_pad, seconden=86400):
    """Maak een tijdelijke downloadlink (24 uur geldig)."""
    try:
        bucket = os.getenv("R2_BUCKET")
        url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': bucket, 'Key': doel_pad},
            ExpiresIn=seconden
        )
        return url
    except Exception as e:
        print("❌ Er ging iets mis bij het genereren van de link:", e)
        return None
