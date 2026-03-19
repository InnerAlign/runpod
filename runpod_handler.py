import runpod

HANDLER_VERSION = "minimum-build-v1"


def validate_input(job_input):
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

    return None


def handler(job):
    job_input = job.get("input", {})

    print("HANDLER_VERSION:", HANDLER_VERSION)
    print("JOB INPUT:", job_input)

    error = validate_input(job_input)
    if error:
        return {
            "status": "failed",
            "results": {
                "handler_version": HANDLER_VERSION,
            },
            "error_message": error,
        }

    return {
        "status": "completed",
        "pipeline_type": job_input["pipeline_type"],
        "user_id": job_input["user_id"],
        "results": {
            "handler_version": HANDLER_VERSION,
            "script_text_received": job_input["script_text"],
            "voice_source_received": job_input["voice_source"],
            "source_audio_url_received": job_input.get("source_audio_url", ""),
        },
        "error_message": "",
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
