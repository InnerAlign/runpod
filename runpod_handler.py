import os
import tempfile
from typing import Any, Dict, Optional

import requests
import runpod


def validate_input(job_input: Dict[str, Any]) -> Optional[str]:
    required_fields = [
        "user_id",
        "pipeline_type",
        "script_text",
        "voice_source",
    ]

    for field in required_fields:
        if not job_input.get(field):
            return f"Missing required field: {field}"

    pipeline_type = job_input.get("pipeline_type")
    allowed_pipeline_types = ["onboarding"]

    if pipeline_type not in allowed_pipeline_types:
        return f"pipeline_type must be one of: {', '.join(allowed_pipeline_types)}"

    voice_source = job_input.get("voice_source")
    if voice_source not in ["user_recording", "ai_default_voice"]:
        return "voice_source must be 'user_recording' or 'ai_default_voice'"

    if voice_source == "user_recording" and not job_input.get("source_audio_url"):
        return "source_audio_url is required when voice_source is 'user_recording'"

    return None


def download_file(url: str, suffix: str = ".wav") -> str:
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    with open(temp_path, "wb") as f:
        f.write(response.content)

    return temp_path


def create_voice_profile(source_audio_path: str, user_id: str) -> Dict[str, Any]:
    # Placeholder for Orpheus voice-profile creation
    return {
        "status": "completed",
        "voice_model_key": f"users/{user_id}/voice-profiles/default_v1.bin"
    }


def generate_tts(script_text: str, voice_source: str, user_id: str) -> Dict[str, Any]:
    # Placeholder for Orpheus TTS generation
    return {
        "status": "completed",
        "tts_audio_key": f"users/{user_id}/tts/generated_tts.wav"
    }


def generate_music(music_prompt: str, user_id: str) -> Dict[str, Any]:
    # Placeholder for InspireMusic generation
    return {
        "status": "completed",
        "music_audio_key": f"users/{user_id}/music/generated_music.wav"
    }


def mix_audio(user_id: str) -> Dict[str, Any]:
    # Placeholder for FFmpeg mixing
    return {
        "status": "completed",
        "final_audio_key": f"users/{user_id}/final/final_meditation.wav"
    }


def handle_onboarding_pipeline(job_input: Dict[str, Any]) -> Dict[str, Any]:
    user_id = job_input["user_id"]
    script_text = job_input["script_text"]
    voice_source = job_input["voice_source"]
    source_audio_url = job_input.get("source_audio_url", "")
    music_prompt = job_input.get("music_prompt", "")

    results: Dict[str, Any] = {
        "voice_model_key": "",
        "tts_audio_key": "",
        "music_audio_key": "",
        "final_audio_key": "",
    }

    try:
        if voice_source == "user_recording":
            source_audio_path = download_file(source_audio_url)
            voice_profile_result = create_voice_profile(source_audio_path, user_id)
            results["voice_model_key"] = voice_profile_result["voice_model_key"]
        else:
            results["voice_model_key"] = "system/default"

        tts_result = generate_tts(script_text, voice_source, user_id)
        results["tts_audio_key"] = tts_result["tts_audio_key"]

        music_result = generate_music(music_prompt, user_id)
        results["music_audio_key"] = music_result["music_audio_key"]

        mix_result = mix_audio(user_id)
        results["final_audio_key"] = mix_result["final_audio_key"]

        return {
            "status": "completed",
            "user_id": user_id,
            "pipeline_type": "onboarding",
            "results": results,
            "error_message": ""
        }

    except Exception as e:
        return {
            "status": "failed",
            "user_id": user_id,
            "pipeline_type": "onboarding",
            "results": results,
            "error_message": str(e)
        }


def handler(event: Dict[str, Any]) -> Dict[str, Any]:
    job_input = event.get("input", {})

    error = validate_input(job_input)
    if error:
        return {
            "status": "failed",
            "results": {},
            "error_message": error
        }

    pipeline_type = job_input["pipeline_type"]

    if pipeline_type == "onboarding":
        return handle_onboarding_pipeline(job_input)

    return {
        "status": "failed",
        "results": {},
        "error_message": f"Unsupported pipeline_type: {pipeline_type}"
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
