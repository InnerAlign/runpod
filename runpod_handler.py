import os
import tempfile
import requests
import boto3
import runpod

# -----------------------------
# URL normalization
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
    resp = requests.get(url, stream=True)
    resp.raise_for_status()

    fd, temp_path = tempfile.mkstemp(suffix=".mp3")
    with os.fdopen(fd, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    return temp_path

# -----------------------------
# Orpheus training
# -----------------------------
def run_orpheus_training(audio_path: str, user_id: str) -> str:
    """
    TODO: Replace this body with your real Orpheus training code.

    Shape you want:
    - Load Orpheus model (once, globally, when you’re ready)
    - Train a voice profile from `audio_path`
    - Save the resulting profile to a file
    - Return that file path
    """
    output_path = f"/tmp/{user_id}_voice_profile.json"
    with open(output_path, "w") as f:
        f.write('{"status": "ok", "note": "replace with real Orpheus profile"}')
    return output_path

# -----------------------------
# R2 upload
# -----------------------------
def upload_to_r2(local_path: str, user_id: str, filename: str) -> str:
    session = boto3.session.Session()

    s3 = session.client(
        service_name="s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )

    bucket = os.environ["R2_BUCKET"]
    r2_key = f"users/{user_id}/voice-profiles/{filename}"

    s3.upload_file(local_path, bucket, r2_key)

    return r2_key

# -----------------------------
# Main handler
# -----------------------------
def handler(event):
    # Expecting:
    # {
    #   "input": {
    #       "user_id": "...",
    #       "audio_url": "..."
    #   }
    # }
    inp = event.get("input", {})
    user_id = inp.get("user_id")
    audio_url = inp.get("audio_url")

    if not user_id or not audio_url:
        return {
            "status": "error",
            "message": "Missing user_id or audio_url in input."
        }

    # 1) Download source audio from Bubble
    local_audio_path = download_audio(audio_url)

    # 2) Run Orpheus training (replace internals with real training later)
    voice_profile_path = run_orpheus_training(local_audio_path, user_id)

    # 3) Upload Orpheus output to R2
    filename = os.path.basename(voice_profile_path)
    r2_key = upload_to_r2(voice_profile_path, user_id, filename)

    # 4) Construct a voice model ID you’ll reuse for TTS
    voice_model_id = f"orpheus-{user_id}-v1"

    # 5) Return metadata to Bubble
    return {
        "status": "success",
        "user_id": user_id,
        "audio_url_used": normalize_url(audio_url),
        "voice_profile_key": r2_key,
        "voice_model_id": voice_model_id,
    }

runpod.serverless.start({"handler": handler})
