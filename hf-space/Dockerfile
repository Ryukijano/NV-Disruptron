FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SPACE_ENABLED_MODELS=dinov2,aiendo,vjepa2 \
    SPACE_DEFAULT_MODEL=dinov2 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_SERVER_RUN_ON_SAVE=false \
    COSMOS_SPACE_CACHE_DIR=/home/user/.cache/cosmos_sentinel \
    COSMOS_PREDICT_MODEL=2B/post-trained \
    HF_HOME=/home/user/.cache/huggingface \
    VLLM_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16 \
    VLLM_PORT=8000 \
    FASTAPI_PORT=8010 \
    STREAMLIT_PORT=8501 \
    PORT=7860

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    wget \
    procps \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    git-lfs \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    linux-headers-generic \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user && mkdir -p /app && chown user:user /app
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR /app

# Install base runtime dependencies for the existing Streamlit portfolio
COPY --chown=user runtime-requirements.txt /app/runtime-requirements.txt
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install -r /app/runtime-requirements.txt

# Install NV-Disruptron backend dependencies
COPY --chown=user disruptron/requirements.txt /app/disruptron/requirements.txt
RUN python3 -m pip install -r /app/disruptron/requirements.txt

# Download the small LLM used by NV-Disruptron at build time
RUN python3 -c "
import huggingface_hub, os
model = os.environ['VLLM_MODEL']
print('Downloading model', model)
huggingface_hub.snapshot_download(model, local_files_only=False)
print('Model download complete')
"

# Copy the rest of the application
COPY --chown=user . /app

EXPOSE 7860
CMD ["python3", "start_space.py"]
