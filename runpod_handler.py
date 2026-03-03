import runpod
import requests
import boto3
import os
import tempfile

# -----------------------------
# Normalize Bubble URL
# -----------------------------
def normalize_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if not url.startswith("http"):
        return "https://" + url
    return url

# -----------------------------
# Download audio from Bubble
# -----------------------------
def download_audio(url: str) -> str:
    url = normalize_url(url)
    response = requests.get(url, stream=True)
    response.raise_for_status()

    fd, temp_path = tempfile.mkstemp(suffix=".mp3")
    with os.fdopen(fd, "wb") as tmp:
        for chunk in response.iter_content(chunk_size=8192):
            tmp.write(chunk)

    return temp_path

# -----------------------------
# Upload file to R2
# -----------------------------
def upload_to_r2(local_path: str, user_id: str, filename: str) -> str:
    session = boto3.session.Session()

    s3 = session.client(
        service_name="s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"]
    )

    r2_key = f"users/{user_id}/voice-profiles/{filename}"

    s3.upload_file(local_path, os.environ["R2_BUCKET"], r2_key)

    return r2_key

# -----------------------------
# Main handler
# -----------------------------
def handler(event):
    user_id = event["input"]["user_id"]
    audio_url = event["input"]["audio_url"]

    # Step 1: Download audio
    local_audio_path = download_audio(audio_url)

    # Step 2: Run Orpheus training
    # Replace this with your actual Orpheus call
    # It must return the path to the generated file
    voice_profile_path = run_orpheus_training(local_audio_path, user_id)

    # Step 3: Upload Orpheus output to R2
    filename = os.path.basename(voice_profile_path)
    r2_key = upload_to_r2(voice_profile_path, user_id, filename)

    # Step 4: Return metadata to Bubble
    return {
        "status": "success",
        "user_id": user_id,
        "audio_url_used": normalize_url(audio_url),
        "voice_profile_key": r2_key
    }

runpod.serverless.start({"handler": handler})
