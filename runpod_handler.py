import runpod
import requests
import os
import tempfile
import base64

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
# Convert file to Base64
# -----------------------------
def file_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

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
    # It should return the path to the generated voice profile file(s)
    voice_profile_path = run_orpheus_training(local_audio_path, user_id)

    # Step 3: Convert output file to Base64 for Bubble
    voice_profile_b64 = file_to_base64(voice_profile_path)

    # Step 4: Return the file directly to Bubble
    return {
        "status": "success",
        "user_id": user_id,
        "audio_url_used": normalize_url(audio_url),
        "voice_profile_file_base64": voice_profile_b64,
        "voice_profile_filename": os.path.basename(voice_profile_path)
    }

runpod.serverless.start({"handler": handler})
