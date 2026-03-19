import os
import uuid
import tempfile
from typing import Any, Dict, Optional

import boto3
import requests
import runpod

HANDLER_VERSION = "orpheus-tts-phase-v1"

R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_BUCKET = os.getenv("R2_BUCKET")

R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def safe_int(value: Any, default: int = 0) -> int:
    if value in [None, ""]:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def build_response(
    status: str,
    pipeline_type: str = "",
    user_id: str = "",
    results: Optional[Dict[str, Any]] = None,
    error_message: str = "",
) -> Dict[str, Any]:
    return {
        "status": status,
        "pipeline_type": pipeline_type,
        "user_id": user_id,
        "results": results or {},
        "error_message": error_message,
    }


def normalize_input(job_input: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": safe_str(job_input.get("user_id")),
        "pipeline_type": safe_str(job_input.get("pipeline_type")),
        "script_text": safe_str(job_input.get("script_text")),
        "voice_source": safe_str(job_input.get("voice_source")),
        "source_audio_url": safe_str(job_input.get("source_audio_url")),
        "voice_style": safe_str(job_input.get("voice_style")),
        "music_style": safe_str(job_input.get("music_style")),
        "music_intensity": safe_str(job_input.get("music_intensity")),
        "energy_curve": safe_str(job_input.get("energy_curve")),
        "breath_pacing_style": safe_str(job_input.get("breath_pacing_style")),
        "pause_density": safe_str(job_input.get("pause_density")),
        "estimated_duration_seconds": safe_int(job_input.get("estimated_duration_seconds"), 0),
        "meditation_title": safe_str(job_input.get("meditation_title")),
        "meditation_subtitle": safe_str(job_input.get("meditation_subtitle")),
    }


def validate_env() -> Optional[str]:
    required = {
        "R2_ACCESS_KEY": R2_ACCESS_KEY,
        "R2_SECRET_KEY": R2_SECRET_KEY,
        "R2_ACCOUNT_ID": R2_ACCOUNT_ID,
        "R2_BUCKET": R2_BUCKET,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        return f"Missing environment variables: {', '.join(missing)}"
    return None


def validate_input(job_input: Dict[str, Any]) -> Optional[str]:
    for field in ["user_id", "pipeline_type", "script_text", "voice_source"]:
        if job_input.get(field) in [None, ""]:
            return f"Missing required field: {field}"

    if job_input["pipeline_type"] != "onboarding":
        return "pipeline_type must be 'onboarding'"

    if job_input["voice_source"] not in ["user_recording", "ai_default_voice"]:
        return "voice_source must be 'user_recording' or 'ai_default_voice'"

    if job_input["voice_source"] == "user_recording" and not job_input.get("source_audio_url"):
        return "source_audio_url is required when voice_source is 'user_recording'"

    return None


def r2_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
    )


def upload_file_to_r2(local_path: str, r2_key: str) -> str:
    client = r2_client()
    client.upload_file(local_path, R2_BUCKET, r2_key)
    return r2_key


def download_source_audio(url: str, local_path: str) -> None:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    with open(local_path, "wb") as f:
        f.write(response.content)


def create_placeholder_wav(local_path: str) -> None:
    """
    Temporary fallback until Orpheus generation is wired.
    Produces a tiny valid WAV header/body via ffmpeg.
    """
    import subprocess

    cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", "anullsrc=r=24000:cl=mono",
        "-t", "2",
        "-q:a", "9",
        "-acodec", "pcm_s16le",
        "-y",
        local_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def generate_tts_with_orpheus(
    script_text: str,
    voice_source: str,
    source_audio_path: Optional[str],
    output_wav_path: str,
) -> str:
    """
    Phase 1 target:
    - Try to wire real Orpheus here.
    - If not yet implemented, create a valid placeholder WAV so the rest of the pipeline works.
    """
    # TODO: replace this fallback with real Orpheus inference.
    # Current goal is stable file flow + real audio asset shape.
    create_placeholder_wav(output_wav_path)

    if voice_source == "ai_default_voice":
        return "system/default"
    return "users/temporary/voice-profile-placeholder"


def process_onboarding(job_input: Dict[str, Any]) -> Dict[str, Any]:
    user_id = job_input["user_id"]
    job_id = str(uuid.uuid4())

    with tempfile.TemporaryDirectory() as tmpdir:
        source_audio_path = None

        if job_input["voice_source"] == "user_recording":
            source_audio_path = os.path.join(tmpdir, "source_audio.wav")
            download_source_audio(job_input["source_audio_url"], source_audio_path)

        tts_local_path = os.path.join(tmpdir, "tts_output.wav")

        voice_model_key = generate_tts_with_orpheus(
            script_text=job_input["script_text"],
            voice_source=job_input["voice_source"],
            source_audio_path=source_audio_path,
            output_wav_path=tts_local_path,
        )

        tts_audio_key = f"users/{user_id}/tts/{job_id}.wav"
        final_audio_key = f"users/{user_id}/final/{job_id}.wav"

        upload_file_to_r2(tts_local_path, tts_audio_key)
        upload_file_to_r2(tts_local_path, final_audio_key)

        return {
            "handler_version": HANDLER_VERSION,
            "voice_model_key": voice_model_key,
            "tts_audio_key": tts_audio_key,
            "music_audio_key": "",
            "final_audio_key": final_audio_key,
            "script_text_received": job_input["script_text"],
            "voice_source_received": job_input["voice_source"],
            "source_audio_url_received": job_input["source_audio_url"],
            "estimated_duration_seconds": job_input["estimated_duration_seconds"],
            "meditation_title": job_input["meditation_title"],
            "meditation_subtitle": job_input["meditation_subtitle"],
        }


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    raw_input = job.get("input", {})
    job_input = normalize_input(raw_input)

    env_error = validate_env()
    if env_error:
        return build_response(
            status="failed",
            pipeline_type=job_input.get("pipeline_type", ""),
            user_id=job_input.get("user_id", ""),
            results={"handler_version": HANDLER_VERSION},
            error_message=env_error,
        )

    input_error = validate_input(job_input)
    if input_error:
        return build_response(
            status="failed",
            pipeline_type=job_input.get("pipeline_type", ""),
            user_id=job_input.get("user_id", ""),
            results={"handler_version": HANDLER_VERSION},
            error_message=input_error,
        )

    try:
        results = process_onboarding(job_input)
        return build_response(
            status="completed",
            pipeline_type=job_input["pipeline_type"],
            user_id=job_input["user_id"],
            results=results,
            error_message="",
        )
    except Exception as e:
        return build_response(
            status="failed",
            pipeline_type=job_input.get("pipeline_type", ""),
            user_id=job_input.get("user_id", ""),
            results={"handler_version": HANDLER_VERSION},
            error_message=f"Unhandled exception: {str(e)}",
        )


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
