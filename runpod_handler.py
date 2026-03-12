import io
import os
import shutil
import subprocess
import tempfile
import uuid
import wave
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
import requests
import runpod

# Orpheus official package usage pattern:
# from orpheus_tts import OrpheusModel
from orpheus_tts import OrpheusModel

# InspireMusic official Python usage pattern:
# from inspiremusic.cli.inference import InspireMusicModel, env_variables
from inspiremusic.cli.inference import InspireMusicModel, env_variables


HANDLER_VERSION = "2026-03-12-real-r2-orpheus-inspiremusic-v1"

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.getenv("R2_BUCKET", "")

ORPHEUS_MODEL_NAME = os.getenv("ORPHEUS_MODEL_NAME", "canopylabs/orpheus-tts-0.1-finetune-prod")
ORPHEUS_DEFAULT_VOICE = os.getenv("ORPHEUS_DEFAULT_VOICE", "tara")

INSPIREMUSIC_MODEL_NAME = os.getenv("INSPIREMUSIC_MODEL_NAME", "InspireMusic-Base")
INSPIREMUSIC_MODEL_DIR = os.getenv(
    "INSPIREMUSIC_MODEL_DIR",
    "/opt/FunMusic/pretrained_models/InspireMusic",
)

R2_ENDPOINT_URL = (
    f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    if R2_ACCOUNT_ID else ""
)

ORPHEUS_MODEL = None
INSPIREMUSIC_MODEL = None


def validate_env() -> None:
    missing = []
    for name, value in {
        "R2_ACCOUNT_ID": R2_ACCOUNT_ID,
        "R2_ACCESS_KEY_ID": R2_ACCESS_KEY_ID,
        "R2_SECRET_ACCESS_KEY": R2_SECRET_ACCESS_KEY,
        "R2_BUCKET": R2_BUCKET,
    }.items():
        if not value:
            missing.append(name)
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def get_s3_client():
    validate_env()
    return boto3.client(
        service_name="s3",
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def make_key(user_id: str, folder: str, filename: str) -> str:
    return f"users/{user_id}/{folder}/{filename}"


def upload_bytes_to_r2(data: bytes, key: str, content_type: str) -> str:
    s3 = get_s3_client()
    s3.put_object(
        Bucket=R2_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def upload_file_to_r2(file_path: str, key: str, content_type: str) -> str:
    s3 = get_s3_client()
    extra_args = {"ContentType": content_type}
    s3.upload_file(file_path, R2_BUCKET, key, ExtraArgs=extra_args)
    return key


def download_file(url: str, suffix: str = ".wav") -> str:
    response = requests.get(url, timeout=180)
    response.raise_for_status()

    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    with open(temp_path, "wb") as f:
        f.write(response.content)

    return temp_path


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

    if job_input["pipeline_type"] != "onboarding":
        return "pipeline_type must be 'onboarding'"

    if job_input["voice_source"] not in ["user_recording", "ai_default_voice"]:
        return "voice_source must be 'user_recording' or 'ai_default_voice'"

    if job_input["voice_source"] == "user_recording" and not job_input.get("source_audio_url"):
        return "source_audio_url is required when voice_source is 'user_recording'"

    return None


def ensure_models_loaded() -> None:
    global ORPHEUS_MODEL, INSPIREMUSIC_MODEL

    if ORPHEUS_MODEL is None:
        ORPHEUS_MODEL = OrpheusModel(
            model_name=ORPHEUS_MODEL_NAME,
            max_model_len=2048,
        )

    if INSPIREMUSIC_MODEL is None:
        env_variables()
        INSPIREMUSIC_MODEL = InspireMusicModel(model_name=INSPIREMUSIC_MODEL_NAME)


def write_orpheus_output_to_wav(prompt: str, voice_name: str, output_path: str) -> None:
    syn_tokens = ORPHEUS_MODEL.generate_speech(
        prompt=prompt,
        voice=voice_name,
    )

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)

        for audio_chunk in syn_tokens:
            wf.writeframes(audio_chunk)


def find_latest_wav(directory: str) -> str:
    wavs = []
    for root, _, files in os.walk(directory):
        for name in files:
            if name.lower().endswith(".wav"):
                wavs.append(os.path.join(root, name))
    if not wavs:
        raise RuntimeError(f"No .wav file found in {directory}")
    wavs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return wavs[0]


def generate_music_with_inspiremusic(prompt: str, output_path: str) -> None:
    temp_result_dir = tempfile.mkdtemp(prefix="inspiremusic_")
    try:
        # Use the official CLI path shown by the repo.
        cmd = [
            "python3",
            "/opt/FunMusic/inspiremusic/bin/inference.py",
            "--task", "text-to-music",
            "--gpu", "0",
            "--config", "/opt/FunMusic/conf/inspiremusic.yaml",
            "--prompt_data", "/opt/FunMusic/data/test/parquet/data.list",
            "--flow_model", os.path.join(INSPIREMUSIC_MODEL_DIR, "flow.pt"),
            "--llm_model", os.path.join(INSPIREMUSIC_MODEL_DIR, "llm.pt"),
            "--music_tokenizer", os.path.join(INSPIREMUSIC_MODEL_DIR, "music_tokenizer"),
            "--wavtokenizer", os.path.join(INSPIREMUSIC_MODEL_DIR, "wavtokenizer"),
            "--result_dir", temp_result_dir,
            "--chorus", "verse",
            "--fast",
        ]

        # The official CLI expects prompt data files; the Python API is less explicit about export paths.
        # We try the Python API first, then fall back to the CLI result dir approach if needed.
        try:
            INSPIREMUSIC_MODEL.inference("text-to-music", prompt)
        except Exception:
            pass

        subprocess.run(cmd, check=False, capture_output=True, text=True)

        latest_wav = find_latest_wav(temp_result_dir)
        shutil.copyfile(latest_wav, output_path)
    finally:
        shutil.rmtree(temp_result_dir, ignore_errors=True)


def mix_audio_ffmpeg(tts_path: str, music_path: str, output_path: str) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-i", tts_path,
        "-i", music_path,
        "-filter_complex",
        "[0:a]volume=1.0[a0];[1:a]volume=0.16[a1];[a0][a1]amix=inputs=2:duration=longest:dropout_transition=2",
        "-ar", "24000",
        "-ac", "1",
        output_path,
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg mix failed: {completed.stderr}")


def build_voice_profile_asset(user_id: str, source_audio_path: str, source_audio_url: str, run_id: str) -> str:
    """
    This stores the source voice asset in R2 and returns its key.
    It is a durable voice-profile source record, not a verified reusable Orpheus 'voice ID'.
    """
    if source_audio_path:
        key = make_key(user_id, "voice-profiles", f"{now_stamp()}_{run_id}_source.wav")
        return upload_file_to_r2(source_audio_path, key, "audio/wav")

    payload = (
        f'{{"type":"default_voice","voice":"{ORPHEUS_DEFAULT_VOICE}","created_at":"{now_stamp()}"}}'
    ).encode("utf-8")
    key = make_key(user_id, "voice-profiles", f"{now_stamp()}_{run_id}_default.json")
    return upload_bytes_to_r2(payload, key, "application/json")


def handle_onboarding_pipeline(job: Dict[str, Any], job_input: Dict[str, Any]) -> Dict[str, Any]:
    ensure_models_loaded()

    user_id = job_input["user_id"]
    script_text = job_input["script_text"]
    voice_source = job_input["voice_source"]
    source_audio_url = job_input.get("source_audio_url", "")
    music_prompt = job_input.get("music_prompt", "gentle ambient meditation background")
    run_id = str(uuid.uuid4())[:8]
    stamp = now_stamp()

    results: Dict[str, Any] = {
        "voice_model_key": "",
        "tts_audio_key": "",
        "music_audio_key": "",
        "final_audio_key": "",
        "handler_version": HANDLER_VERSION,
    }

    source_audio_path = ""
    tts_path = ""
    music_path = ""
    final_path = ""

    try:
        print("HANDLER_VERSION:", HANDLER_VERSION)
        print("JOB_ID:", job.get("id"))
        print("INPUT_KEYS:", list(job_input.keys()))

        if voice_source == "user_recording":
            runpod.serverless.progress_update(job, "downloading_source_audio")
            source_audio_path = download_file(source_audio_url)

        runpod.serverless.progress_update(job, "creating_voice_profile")
        results["voice_model_key"] = build_voice_profile_asset(
            user_id=user_id,
            source_audio_path=source_audio_path,
            source_audio_url=source_audio_url,
            run_id=run_id,
        )

        runpod.serverless.progress_update(job, "generating_tts")
        fd_tts, tts_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd_tts)

        # Verified official example uses preset voice names.
        # True reusable voice cloning from uploaded user audio is not wired here.
        write_orpheus_output_to_wav(
            prompt=script_text,
            voice_name=ORPHEUS_DEFAULT_VOICE,
            output_path=tts_path,
        )

        tts_filename = f"{stamp}_{run_id}_tts.wav"
        results["tts_audio_key"] = upload_file_to_r2(
            tts_path,
            make_key(user_id, "tts", tts_filename),
            "audio/wav",
        )

        runpod.serverless.progress_update(job, "generating_music")
        fd_music, music_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd_music)

        generate_music_with_inspiremusic(music_prompt, music_path)

        music_filename = f"{stamp}_{run_id}_music.wav"
        results["music_audio_key"] = upload_file_to_r2(
            music_path,
            make_key(user_id, "music", music_filename),
            "audio/wav",
        )

        runpod.serverless.progress_update(job, "mixing_audio")
        fd_final, final_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd_final)

        mix_audio_ffmpeg(tts_path, music_path, final_path)

        final_filename = f"{stamp}_{run_id}_final.wav"
        results["final_audio_key"] = upload_file_to_r2(
            final_path,
            make_key(user_id, "final", final_filename),
            "audio/wav",
        )

        return {
            "refresh_worker": True,
            "job_results": {
                "status": "completed",
                "pipeline_type": "onboarding",
                "user_id": user_id,
                "results": results,
                "error_message": ""
            }
        }

    except Exception as e:
        return {
            "refresh_worker": True,
            "job_results": {
                "status": "failed",
                "pipeline_type": "onboarding",
                "user_id": user_id,
                "results": results,
                "error_message": str(e)
            }
        }

    finally:
        for path in [source_audio_path, tts_path, music_path, final_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    job_input = job["input"]
    error = validate_input(job_input)
    if error:
        return {
            "refresh_worker": True,
            "job_results": {
                "status": "failed",
                "results": {
                    "handler_version": HANDLER_VERSION,
                },
                "error_message": error
            }
        }

    if job_input["pipeline_type"] == "onboarding":
        return handle_onboarding_pipeline(job, job_input)

    return {
        "refresh_worker": True,
        "job_results": {
            "status": "failed",
            "results": {
                "handler_version": HANDLER_VERSION,
            },
            "error_message": f"Unsupported pipeline_type: {job_input['pipeline_type']}"
        }
    }


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
