FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Set working directory FIRST
WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3.10 python3-pip ffmpeg git curl wget unzip \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3.10 /usr/bin/python

# Copy requirements into the working directory
COPY requirements.txt .

RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of the repo into /app
COPY . .

# Run your handler
CMD ["python", "runpod_handler.py"]
