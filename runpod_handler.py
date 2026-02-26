import runpod
import requests
import soundfile as sf
import io
from orpheus import OrpheusModel

# Load Orpheus once per worker
orpheus = OrpheusModel.load("orpheus-v1")

def handler(job):
    """
    Voice cloning handler.

    Expects:
    {
      "input": {
        "audio_url": "https://your-r2-bucket/path/to/user_audio.wav",
        "user_id": "123"
      }
    }
    """
    input_data = job.get("input", {})

    audio_url = input_data.get("audio_url")
    user_id = input_data.get("user_id")

    if not audio_url or not user_id:
        return {
            "status": "error",
            "message": "Missing required fields: audio_url and/or user_id."
        }

    # 1. Download audio from R2 (or wherever it's stored)
    response = requests.get(audio_url)
    response.raise_for_status()
    audio_bytes = response.content

    # 2. Load audio into memory
    audio_data, sr = sf.read(io.BytesIO(audio_bytes))

    # 3. Create voice model with Orpheus
    voice_model = orpheus.create_voice_model(audio_data, sr)

    # TODO: Upload voice_model to R2 and generate a real voice_model_id
    # For now, we just return a placeholder so we can test the flow.
    voice_model_id = f"placeholder-voice-model-for-user-{user_id}"

    return {
        "status": "success",
        "voice_model_id": voice_model_id
    }

runpod.serverless.start({"handler": handler})
