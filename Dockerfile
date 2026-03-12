FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface \
    TORCH_HOME=/root/.cache/torch

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    git \
    git-lfs \
    ffmpeg \
    curl \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN git lfs install

COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install -r /app/requirements.txt

# Install InspireMusic from the official repo so its Python package and CLI are available.
RUN git clone https://github.com/FunAudioLLM/FunMusic.git /opt/FunMusic && \
    cd /opt/FunMusic && \
    python3 -m pip install -e .

# Optional: preload InspireMusic model repo structure expected by official examples.
# This can fail if the remote is unavailable; it is safe to comment out and mount/provide models another way.
RUN mkdir -p /opt/FunMusic/pretrained_models && \
    git clone https://www.modelscope.cn/iic/InspireMusic.git /opt/FunMusic/pretrained_models/InspireMusic || true

COPY runpod_handler.py /app/runpod_handler.py

CMD ["python3", "-u", "runpod_handler.py"]
