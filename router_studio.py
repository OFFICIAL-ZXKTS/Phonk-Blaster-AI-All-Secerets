"""
====================================================================================================
PHONKBLASTER STUDIO — STUDIO MEDIA & AUDIO TRIMMER ROUTER (router_studio.py)
====================================================================================================
"""

import os
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse

try:
    from media_processor import MediaProcessor
except ImportError:
    MediaProcessor = None

router = APIRouter(prefix="/api/studio", tags=["Studio Trimmer"])
STUDIO_TEMP_DIR = Path("/tmp/phonkblaster_studio")
STUDIO_TEMP_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/process-cuts")
async def process_studio_cuts(
    media_file: UploadFile = File(...),
    audio_file: UploadFile = File(...),
    start_time: float = Form(0.0),
    end_time: Optional[float] = Form(None),
    duration: Optional[float] = Form(None),
    crop_x: int = Form(0),
    crop_y: int = Form(0),
    crop_w: int = Form(0),
    crop_h: int = Form(0),
    fade_in: str = Form("true"),
    fade_out: str = Form("true"),
    media_type: str = Form("image")
):
    job_id = str(uuid.uuid4())[:8]
    job_dir = STUDIO_TEMP_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    media_ext = Path(media_file.filename or "media.png").suffix or ".png"
    audio_ext = Path(audio_file.filename or "audio.mp3").suffix or ".mp3"
    raw_media = str(job_dir / f"raw_media{media_ext}")
    raw_audio = str(job_dir / f"raw_audio{audio_ext}")

    with open(raw_media, "wb") as f:
        shutil.copyfileobj(media_file.file, f)
    with open(raw_audio, "wb") as f:
        shutil.copyfileobj(audio_file.file, f)

    processed_audio = str(job_dir / f"trimmed_audio_{job_id}.mp3")
    processed_media = str(job_dir / f"cropped_media_{job_id}{media_ext}")

    # Determine duration: if not provided or 0, keep full duration
    if end_time is not None and end_time > start_time:
        calc_dur = end_time - start_time
    elif duration is not None and duration > 0:
        calc_dur = duration
    else:
        calc_dur = None  # Full duration

    # 1. Trim & Fade Audio
    if MediaProcessor and hasattr(MediaProcessor, "trim_and_fade_audio"):
        await asyncio.to_thread(
            MediaProcessor.trim_and_fade_audio,
            raw_audio,
            processed_audio,
            start_time,
            calc_dur or 3600.0,
            fade_in.lower() in ["true", "1", "yes"],
            fade_out.lower() in ["true", "1", "yes"]
        )
    else:
        shutil.copyfile(raw_audio, processed_audio)

    # 2. Crop Media (Image or Video)
    if crop_w > 0 and crop_h > 0 and MediaProcessor:
        if media_type == "video" and hasattr(MediaProcessor, "crop_and_trim_video"):
            await asyncio.to_thread(
                MediaProcessor.crop_and_trim_video,
                raw_media,
                processed_media,
                crop_x,
                crop_y,
                crop_w,
                crop_h
            )
        elif hasattr(MediaProcessor, "crop_image"):
            await asyncio.to_thread(
                MediaProcessor.crop_image,
                raw_media,
                processed_media,
                crop_x,
                crop_y,
                crop_w,
                crop_h
            )
        else:
            shutil.copyfile(raw_media, processed_media)
    else:
        shutil.copyfile(raw_media, processed_media)

    return JSONResponse({
        "status": "success",
        "job_id": job_id,
        "duration": round(calc_dur, 2) if calc_dur else "full",
        "media_type": media_type,
        "processed_audio_url": f"/api/studio/download/{job_id}/audio",
        "processed_media_url": f"/api/studio/download/{job_id}/media",
    })


@router.get("/download/{job_id}/{file_type}")
async def download_studio_cut(job_id: str, file_type: str):
    """Serves the processed audio or cropped media file."""
    job_dir = STUDIO_TEMP_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Studio job expired or not found")

    ft = file_type.lower().strip()

    if ft == "audio":
        audios = list(job_dir.glob("trimmed_audio_*.*")) or list(job_dir.glob("raw_audio.*"))
        if audios:
            return FileResponse(
                path=str(audios[0]),
                filename=f"trimmed_audio_{job_id}.mp3",
                media_type="audio/mpeg"
            )

    if ft in ("media", "image", "video"):
        medias = list(job_dir.glob("cropped_media_*.*")) or list(job_dir.glob("raw_media.*"))
        if medias:
            ext = medias[0].suffix.lower()
            mime = "video/mp4" if ext in [".mp4", ".mov", ".webm", ".avi"] else "image/png"
            return FileResponse(
                path=str(medias[0]),
                filename=f"processed_media_{job_id}{ext}",
                media_type=mime
            )

    raise HTTPException(status_code=404, detail=f"File '{file_type}' not found for job {job_id}")
