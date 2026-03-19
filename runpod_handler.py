import runpod
from typing import Any, Dict, Optional

HANDLER_VERSION = "onboarding-contract-v1"


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

        # Optional metadata from Bubble / Screen 6
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


def validate_input(job_input: Dict[str, Any]) -> Optional[str]:
    required_fields = [
        "user_id",
        "pipeline_type",
        "script_text",
        "voice_source",
    ]

    for field in required_fields:
        if job_input.get(field) in [None, ""]:
            return f"Missing required field: {field}"

    if job_input["pipeline_type"] != "onboarding":
        return "pipeline_type must be 'onboarding'"

    if job_input["voice_source"] not in ["user_recording", "ai_default_voice"]:
        return "voice_source must be 'user_recording' or 'ai_default_voice'"

    if job_input["voice_source"] == "user_recording" and not job_input.get("source_audio_url"):
        return "source_audio_url is required when voice_source is 'user_recording'"

    if job_input["estimated_duration_seconds"] < 0:
        return "estimated_duration_seconds must be 0 or greater"

    return None


def process_onboarding(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Placeholder onboarding pipeline logic.
    Replace these sections with real implementations in sequence:
    1. Voice branch
    2. TTS generation
    3. Music generation
    4. Audio mixing
    5. R2 upload
    """

    voice_source = job_input["voice_source"]

    # Branch 1: determine voice model behavior
    if voice_source == "ai_default_voice":
        voice_model_key = "system/default"
        source_audio_used = ""
    else:
        # Later:
        # - download source_audio_url
        # - validate audio
        # - create voice model
        # - upload voice model artifact to R2
        voice_model_key = "r2://placeholder/user-voice-model"
        source_audio_used = job_input["source_audio_url"]

    # Placeholders for future real outputs
    tts_audio_key = "r2://placeholder/generated-tts-audio"
    music_audio_key = "r2://placeholder/generated-background-music"
    final_audio_key = "r2://placeholder/final-mixed-audio"

    return {
        "handler_version": HANDLER_VERSION,

        # Echo / debug fields
        "script_text_received": job_input["script_text"],
        "voice_source_received": voice_source,
        "source_audio_url_received": source_audio_used,

        # Metadata echoed back for Bubble sanity checks
        "voice_style": job_input["voice_style"],
        "music_style": job_input["music_style"],
        "music_intensity": job_input["music_intensity"],
        "energy_curve": job_input["energy_curve"],
        "breath_pacing_style": job_input["breath_pacing_style"],
        "pause_density": job_input["pause_density"],
        "estimated_duration_seconds": job_input["estimated_duration_seconds"],
        "meditation_title": job_input["meditation_title"],
        "meditation_subtitle": job_input["meditation_subtitle"],

        # Future production fields
        "voice_model_key": voice_model_key,
        "tts_audio_key": tts_audio_key,
        "music_audio_key": music_audio_key,
        "final_audio_key": final_audio_key,
    }


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    raw_input = job.get("input", {})
    job_input = normalize_input(raw_input)

    print("HANDLER_VERSION:", HANDLER_VERSION)
    print("JOB INPUT:", job_input)

    error = validate_input(job_input)
    if error:
        return build_response(
            status="failed",
            pipeline_type=job_input.get("pipeline_type", ""),
            user_id=job_input.get("user_id", ""),
            results={
                "handler_version": HANDLER_VERSION,
            },
            error_message=error,
        )

    try:
        if job_input["pipeline_type"] == "onboarding":
            results = process_onboarding(job_input)
        else:
            return build_response(
                status="failed",
                pipeline_type=job_input["pipeline_type"],
                user_id=job_input["user_id"],
                results={
                    "handler_version": HANDLER_VERSION,
                },
                error_message=f"Unsupported pipeline_type: {job_input['pipeline_type']}",
            )

        return build_response(
            status="completed",
            pipeline_type=job_input["pipeline_type"],
            user_id=job_input["user_id"],
            results=results,
            error_message="",
        )

    except Exception as e:
        print("UNHANDLED ERROR:", str(e))
        return build_response(
            status="failed",
            pipeline_type=job_input.get("pipeline_type", ""),
            user_id=job_input.get("user_id", ""),
            results={
                "handler_version": HANDLER_VERSION,
            },
            error_message=f"Unhandled exception: {str(e)}",
        )


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
