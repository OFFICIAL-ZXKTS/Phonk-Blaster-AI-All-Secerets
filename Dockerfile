FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,video,utility

# Install system dependencies (Python 3.10, FFmpeg, and audio libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3.10-dev \
    python3-pip \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgl1 \
    libsndfile1 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Symlink python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# Create non-root user for Hugging Face Spaces
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch with CUDA and all requirements
COPY requirements.txt /home/user/app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY --chown=user:user . /home/user/app

# Set temporary permissions
RUN mkdir -p /tmp/phonkblaster_renders /tmp/phonkblaster_studio && \
    chmod -R 777 /tmp

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

EXPOSE 7860

CMD ["python", "app.py"]
