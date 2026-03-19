import runpod
import requests
import boto3
import os
import uuid

HANDLER_VERSION = "file-pipeline-v1"

# ENV VARIABLES (set these in RunPod)
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_BUCKET = os.getenv("R2_BUCKET")

R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


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
        return "Invalid voice_source"

    if job_input["voice_source"] == "user_recording" and not job_input.get("source_audio_url"):
        return "source_audio_url required for user_recording"

    return None


def download_file(url, local_path):
    response = requests.get(url)
    response.raise_for_status()

    with open(local_path, "wb") as f:
        f.write(response.content)


def upload_to_r2(local_path, r2_key):
    s3 = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
    )

    s3.upload_file(local_path, R2_BUCKET, r2_key)


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

    user_id = job_input["user_id"]

    temp_id = str(uuid.uuid4())
    local_input_path = f"/tmp/input_{temp_id}.wav"
    local_output_path = f"/tmp/output_{temp_id}.txt"

    # STEP 1: Download user audio if needed
    if job_input["voice_source"] == "user_recording":
        download_file(job_input["source_audio_url"], local_input_path)
        print("Downloaded user audio")

    # STEP 2: Create dummy output file (simulating pipeline result)
    with open(local_output_path, "w") as f:
        f.write(f"Generated meditation for user {user_id}")

    # STEP 3: Upload to R2
    r2_key = f"users/{user_id}/final/{temp_id}.txt"
    upload_to_r2(local_output_path, r2_key)

    print("Uploaded to R2:", r2_key)

    return {
        "status": "completed",
        "pipeline_type": job_input["pipeline_type"],
        "user_id": user_id,
        "results": {
            "handler_version": HANDLER_VERSION,
            "final_audio_key": r2_key,
            "voice_model_key": "placeholder_voice_model",
            "tts_audio_key": "placeholder_tts",
            "music_audio_key": "placeholder_music",
        },
        "error_message": "",
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
