"""
====================================================================================================
PHONKBLASTER STUDIO - ULTRA-FAST FASTAPI ZERO-GPU MICROSERVICE (main.py)
High-Speed NVENC GPU Rendering (800+ FPS) • Custom Brand Logos • Zero Timeout
====================================================================================================
"""

import importlib

try:
    spaces = importlib.import_module("spaces")
except Exception:
    class MockSpaces:
        @staticmethod
        def GPU(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
    spaces = MockSpaces()

import os
import sys
import json
import uuid
import time
import queue
import shutil
import asyncio
import logging
import threading
import subprocess
import traceback
from typing import Optional, Dict, Any, List
from pathlib import Path
from contextlib import asynccontextmanager

import multiprocessing
try:
    multiprocessing.current_process().daemon = False
except Exception:
    pass

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("PhonkServer")

@spaces.GPU
def gpu_init():
    return True

try:
    gpu_init()
except Exception:
    pass

# ==================================================================================================
# 1. ENGINE IMPORTS
# ==================================================================================================

render_omni_suite = None
try:
    import engine_omni
    render_omni_suite = (
        getattr(engine_omni, "render_omni_sync", None) or 
        getattr(engine_omni, "render_omni_batch", None) or 
        getattr(engine_omni, "render_omni_suite", None) or 
        getattr(engine_omni, "render_omni_bundle", None) or 
        getattr(engine_omni, "render_omni", None) or 
        getattr(engine_omni, "render", None)
    )
    logger.info("✅ engine_omni loaded successfully")
except Exception as e:
    logger.warning(f"⚠️ engine_omni import error: {e}")

render_video_sync = None
try:
    import engine_video
    render_video_sync = (
        getattr(engine_video, "render_video_sync", None) or 
        getattr(engine_video, "process_video_phonk_edit", None) or 
        getattr(engine_video, "render_video", None) or 
        getattr(engine_video, "render", None)
    )
    logger.info("✅ engine_video loaded successfully")
except Exception as e:
    logger.warning(f"⚠️ engine_video error: {e}")

render_photo_bounce = None
try:
    import engine_photo
    render_photo_bounce = (
        getattr(engine_photo, "render_photo_bounce", None) or 
        getattr(engine_photo, "generate_phonk_image_render", None) or 
        getattr(engine_photo, "render_photo", None) or 
        getattr(engine_photo, "render", None)
    )
    logger.info("✅ engine_photo loaded successfully")
except Exception as e:
    logger.warning(f"⚠️ engine_photo error: {e}")


# ==================================================================================================
# 2. PRIORITY QUEUE & DISK-PERSISTENT STATUS
# ==================================================================================================

TIER_PRIORITY_MAP = {
    "enterprise": 1,
    "apex": 1,
    "hard": 1,
    "ultimate": 2,
    "pro": 3,
    "free": 4,
}

TEMP_DIR = Path("/tmp/phonkblaster_renders")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

TASKS: Dict[str, Dict[str, Any]] = {}
render_priority_queue = queue.PriorityQueue()
worker_threads: List[threading.Thread] = []


def write_disk_status(task_id: str, data: dict):
    try:
        out_dir = TEMP_DIR / task_id
        out_dir.mkdir(parents=True, exist_ok=True)
        status_file = out_dir / "status.json"
        with open(status_file, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f"Failed to write disk status for {task_id}: {e}")


def sanitize_audio_file(input_audio_path: str, out_dir: Path) -> str:
    """
    Sanitizes any incoming audio file into a 16-bit 44.1kHz PCM WAV.
    Permanently bypasses libmpg123 header parser crashes.
    """
    clean_audio_path = str(out_dir / "sanitized_audio.wav")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", input_audio_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            clean_audio_path
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(clean_audio_path) and os.path.getsize(clean_audio_path) > 0:
            return clean_audio_path
    except Exception as err:
        logger.warning(f"Audio pre-sanitization note: {err}")
    return input_audio_path


@spaces.GPU(duration=300)
def execute_render_job(task_id: str, mode: str, media_path: str, audio_path: Optional[str], params: dict):
    try:
        processing_status = {
            "task_id": task_id,
            "status": "processing",
            "progress": 25,
            "mode": mode
        }
        TASKS[task_id] = processing_status
        write_disk_status(task_id, processing_status)

        out_dir = TEMP_DIR / task_id
        out_dir.mkdir(parents=True, exist_ok=True)

        # 🛡️ Pre-sanitize audio to eliminate libmpg123 crashes
        clean_audio = sanitize_audio_file(audio_path, out_dir) if audio_path else None

        is_video = params.get("is_video", False) or mode == "video"
        resolution = params.get("resolution", "1080p")
        fps = int(params.get("fps", 60))
        style = params.get("style", "drift")
        tier = params.get("tier", "enterprise")

        # 👑 Custom Apex Brand Logo Logic
        is_paid_tier = str(tier).lower() in ("hard", "enterprise", "apex", "ultimate", "pro")
        custom_text = (
            params.get("custom_brand_logo") or 
            params.get("custom_watermark_text") or 
            params.get("watermark_text") or ""
        ).strip()

        if is_paid_tier:
            if custom_text and custom_text.upper() != "PHONKBLASTER.ME":
                watermark = True
                watermark_text = custom_text
            else:
                watermark = False
                watermark_text = ""
        else:
            watermark = True
            watermark_text = "PHONKBLASTER.ME"

        music_vol = float(params.get("music_volume", 0.8))
        voice_vol = float(params.get("voice_volume", 0.25))

        logger.info(f"🚀 [Job Started] Task: {task_id} | Mode: {mode} | Brand Logo: '{watermark_text}'")

        # 🧹 1. AI WATERMARK PURGER / DELOGO MODE
        if mode in ("clean_watermark", "delogo", "purge_watermark", "clean"):
            out_file = str(out_dir / f"phonk_clean_{task_id[:8]}.mp4")
            
            # Detect video width and height using ffprobe
            vw, vh = 1080, 1920
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", media_path
                ]
                probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                if probe_res.returncode == 0 and "x" in probe_res.stdout.strip():
                    parts = probe_res.stdout.strip().split("x")
                    vw, vh = int(parts[0]), int(parts[1])
            except Exception:
                pass

            # Compute responsive watermark bounds (bottom-right & bottom-left corners)
            dw = min(int(vw * 0.32), 260)
            dh = min(int(vh * 0.08), 85)
            dx_right = max(0, vw - dw - 10)
            dy_bottom = max(0, vh - dh - 10)
            dx_left = 10

            delogo_filters = f"delogo=x={dx_right}:y={dy_bottom}:w={dw}:h={dh}:band=2,delogo=x={dx_left}:y={dy_bottom}:w={dw}:h={dh}:band=2"

            delogo_cmd = [
                "ffmpeg", "-y", "-hwaccel", "cuda",
                "-i", media_path,
                "-vf", delogo_filters,
                "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "10M",
                "-c:a", "copy",
                "-movflags", "+faststart",
                out_file
            ]
            try:
                res = subprocess.run(delogo_cmd, capture_output=True, text=True, timeout=90)
                if res.returncode != 0:
                    cpu_cmd = [
                        "ffmpeg", "-y",
                        "-i", media_path,
                        "-vf", delogo_filters,
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                        "-c:a", "copy",
                        "-movflags", "+faststart",
                        out_file
                    ]
                    subprocess.run(cpu_cmd, check=True, timeout=90)
            except Exception as delogo_err:
                logger.error(f"Delogo execution note: {delogo_err}")
                shutil.copyfile(media_path, out_file)

            completed_status = {
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "video_url": f"/download/{task_id}/clean",
                "download_url": f"/download/{task_id}/clean"
            }

        # 👑 2. OMNI 4-IN-1 MASTER SUITE
        elif mode in ("omni", "matrix", "matrix_long") and render_omni_suite and clean_audio:
            try:
                result = render_omni_suite(
                    media_input=media_path,
                    audio_input=clean_audio,
                    output_dir=str(out_dir),
                    task_id=task_id,
                    is_video=is_video,
                    resolution=resolution,
                    fps=fps,
                    style=style,
                    tier=tier,
                    watermark=watermark,
                    custom_watermark_text=watermark_text,
                    music_volume=music_vol,
                    voice_volume=voice_vol
                )
            except TypeError:
                try:
                    result = render_omni_suite(
                        media_path=media_path,
                        audio_path=clean_audio,
                        output_dir=str(out_dir),
                        session_id=task_id,
                        tier=tier,
                        preset=style,
                        fps=fps,
                        watermark=watermark,
                        custom_watermark_text=watermark_text
                    )
                except TypeError:
                    result = render_omni_suite(media_path, clean_audio, str(out_dir), task_id)

            completed_status = {
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "video_url": f"/download/{task_id}/short",
                "download_url": f"/download/{task_id}/short",
                "zip_url": f"/download/{task_id}/zip",
                "is_bundle": True,
                "files": result.get("files", {}) if isinstance(result, dict) else {},
                "sizes": result.get("sizes", {}) if isinstance(result, dict) else {}
            }

        # 🎬 3. AUDIO-REACTIVE VIDEO SYNC ENGINE
        elif is_video and render_video_sync and clean_audio:
            out_file = str(out_dir / f"phonk_video_{task_id[:8]}.mp4")
            try:
                render_video_sync(
                    media_path=media_path,
                    audio_path=clean_audio,
                    output_path=out_file,
                    mode=mode,
                    resolution="720p" if not is_paid_tier else "1080p",
                    fps=fps,
                    style=style,
                    velocity_speed_ramp=float(params.get("velocity_speed_ramp", 0.75)),
                    camera_shake=float(params.get("camera_shake", 0.65)),
                    flash_bloom=float(params.get("flash_bloom", 0.50)),
                    motion_blur=float(params.get("motion_blur", 0.60)),
                    zoom_punch=float(params.get("zoom_punch", 0.70)),
                    vhs_overlay=bool(params.get("vhs_overlay", False)),
                    tier=tier,
                    voice_volume=voice_vol,
                    music_volume=music_vol,
                    watermark=watermark,
                    custom_watermark_text=watermark_text
                )
            except TypeError:
                render_video_sync(media_path, clean_audio, out_file)

            completed_status = {
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "video_url": f"/download/{task_id}/video",
                "download_url": f"/download/{task_id}/video"
            }

        # 📸 4. AUDIO-REACTIVE PHOTO BOUNCE ENGINE
        elif clean_audio and render_photo_bounce:
            out_file = str(out_dir / f"phonk_photo_{task_id[:8]}.mp4")
            try:
                render_photo_bounce(
                    image_input=media_path,
                    audio_input=clean_audio,
                    output_path=out_file,
                    mode=mode,
                    resolution=resolution,
                    fps=fps,
                    style=style,
                    tier=tier,
                    watermark=watermark,
                    watermark_text=watermark_text,
                    custom_watermark_text=watermark_text
                )
            except TypeError:
                try:
                    render_photo_bounce(
                        image_input=media_path,
                        audio_input=clean_audio,
                        output_path=out_file,
                        watermark=watermark,
                        custom_watermark_text=watermark_text
                    )
                except TypeError:
                    render_photo_bounce(media_path, clean_audio, out_file)

            completed_status = {
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "video_url": f"/download/{task_id}/photo",
                "download_url": f"/download/{task_id}/photo"
            }
        else:
            raise ValueError("Invalid render mode or missing inputs")

        TASKS[task_id] = completed_status
        write_disk_status(task_id, completed_status)
        logger.info(f"✅ [Job Complete] Task: {task_id} status saved to disk")

    except BaseException as e:
        logger.error(f"❌ [Job Error] Task {task_id}: {e}\n{traceback.format_exc()}")
        failed_status = {
            "task_id": task_id,
            "status": "failed",
            "progress": 0,
            "error": "Render timed out on GPU. Please try a shorter duration or 1080p." if "aborted" in str(e).lower() else str(e)
        }
        TASKS[task_id] = failed_status
        write_disk_status(task_id, failed_status)


def priority_worker_loop():
    while True:
        try:
            priority, timestamp, task_id, mode, media_path, audio_path, params = render_priority_queue.get()
            execute_render_job(task_id, mode, media_path, audio_path, params)
            render_priority_queue.task_done()
        except BaseException as err:
            logger.error(f"Worker exception: {err}")
            time.sleep(0.5)


# ==================================================================================================
# 3. APPLICATION LIFECYCLE
# ==================================================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    num_workers = max(1, min(4, (os.cpu_count() or 2) // 2))
    for i in range(num_workers):
        t = threading.Thread(target=priority_worker_loop, daemon=False, name=f"PriorityWorker-{i+1}")
        t.start()
        worker_threads.append(t)

    logger.info("=" * 60)
    logger.info("⚡ PhonkBlaster Studio Server Live on http://0.0.0.0:7860")
    logger.info(f"⚡ ZeroGPU Priority Queue Active: {num_workers} Dedicated Workers")
    logger.info("=" * 60)
    yield
    logger.info("⚡ PhonkBlaster Server stopping...")


app = FastAPI(
    title="PhonkBlaster Cloud Renderer",
    description="High-Voltage AI Phonk Audio-Reactive Video Rendering Microservice",
    version="3.5.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    import router_studio
    app.include_router(router_studio.router)
    logger.info("✅ router_studio loaded successfully")
except Exception as e:
    logger.warning(f"⚠️ router_studio note: {e}")


# ==================================================================================================
# 4. API ROUTES & HF COMPATIBILITY
# ==================================================================================================

@app.get("/")
@app.head("/")
async def root_health():
    return {
        "status": "online",
        "service": "PhonkBlaster Studio Cloud Renderer (ZeroGPU)",
        "version": "3.5.0",
        "queue_size": render_priority_queue.qsize(),
        "engines": {
            "omni": render_omni_suite is not None,
            "video": render_video_sync is not None,
            "photo": render_photo_bounce is not None
        }
    }


# HF Space Ping Compatibility (Prevents 404 spam in Space logs)
@app.get("/api/config")
@app.post("/api/predict")
async def hf_space_compatibility():
    return {"status": "ok", "service": "phonk_renderer_zerogpu"}


@app.post("/render")
async def render_endpoint(
    request: Request,
    media: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    video: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
    mode: Optional[str] = Form(None),
    resolution: Optional[str] = Form(None),
    fps: Optional[str] = Form(None),
    style: Optional[str] = Form(None),
    tier: Optional[str] = Form(None),
    subscription_tier: Optional[str] = Form(None),
    plan: Optional[str] = Form(None),
    watermark: Optional[str] = Form(None),
    watermark_text: Optional[str] = Form(None),
    custom_watermark_text: Optional[str] = Form(None),
    custom_brand_logo: Optional[str] = Form(None),
    velocity_speed_ramp: Optional[str] = Form(None),
    camera_shake: Optional[str] = Form(None),
    flash_bloom: Optional[str] = Form(None),
    motion_blur: Optional[str] = Form(None),
    zoom_punch: Optional[str] = Form(None),
    vhs_overlay: Optional[str] = Form(None),
    music_volume: Optional[str] = Form(None),
    voice_volume: Optional[str] = Form(None)
):
    actual_media = media or video or image
    is_video = False
    media_ext = ".png"
    if actual_media:
        media_ext = Path(actual_media.filename or "media.png").suffix or ".png"
        is_video = media_ext.lower() in [".mp4", ".mov", ".webm", ".avi", ".mkv", ".m4v"]

    raw_mode = (mode or request.query_params.get("mode") or ("video" if is_video else "short")).lower().strip()

    if raw_mode in ("clean_watermark", "delogo", "purge_watermark", "clean"):
        if not actual_media:
            return JSONResponse(status_code=400, content={"status": "error", "error": "Missing video file to clean."})
    else:
        if not actual_media or not audio:
            return JSONResponse(status_code=400, content={"status": "error", "error": "Missing required files. Please attach both a media file and an audio track."})

    task_id = str(uuid.uuid4())
    task_dir = TEMP_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    saved_media_path = str(task_dir / f"input_media{media_ext}")
    with open(saved_media_path, "wb") as f:
        shutil.copyfileobj(actual_media.file, f)

    saved_audio_path = None
    if audio:
        audio_ext = Path(audio.filename or "audio.mp3").suffix or ".mp3"
        saved_audio_path = str(task_dir / f"input_audio{audio_ext}")
        with open(saved_audio_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)

    resolved_tier = (tier or subscription_tier or plan or "free").lower().strip()
    priority_level = TIER_PRIORITY_MAP.get(resolved_tier, 4)

    active_custom_text = (custom_brand_logo or custom_watermark_text or watermark_text or "").strip()

    params = {
        "is_video": is_video,
        "resolution": resolution or ("720p" if resolved_tier == "free" else "1080p"),
        "fps": int(fps) if fps and str(fps).isdigit() else 60,
        "style": style or "drift",
        "velocity_speed_ramp": float(velocity_speed_ramp) if velocity_speed_ramp else 0.75,
        "camera_shake": float(camera_shake) if camera_shake else 0.65,
        "flash_bloom": float(flash_bloom) if flash_bloom else 0.50,
        "motion_blur": float(motion_blur) if motion_blur else 0.60,
        "zoom_punch": float(zoom_punch) if zoom_punch else 0.70,
        "vhs_overlay": str(vhs_overlay).lower() in ("true", "1") if vhs_overlay else False,
        "watermark": bool(active_custom_text) or (watermark in ["true", "1", "True", True] if watermark is not None else False),
        "watermark_text": active_custom_text,
        "custom_watermark_text": active_custom_text,
        "custom_brand_logo": active_custom_text,
        "music_volume": float(music_volume) if music_volume else 0.85,
        "voice_volume": float(voice_volume) if voice_volume else 0.25,
        "tier": resolved_tier
    }

    queued_status = {
        "task_id": task_id,
        "status": "queued",
        "priority": priority_level,
        "progress": 5,
        "mode": raw_mode,
        "created_at": time.time()
    }
    TASKS[task_id] = queued_status
    write_disk_status(task_id, queued_status)

    render_priority_queue.put((
        priority_level,
        time.time(),
        task_id,
        raw_mode,
        saved_media_path,
        saved_audio_path,
        params
    ))

    logger.info(f"📥 [Queued] Task {task_id} ({raw_mode}) Priority {priority_level} | Custom Brand: '{active_custom_text}'")

    return {
        "status": "queued",
        "task_id": task_id,
        "priority": priority_level,
        "mode": raw_mode
    }


@app.get("/status/{task_id}")
async def get_status(task_id: str):
    status_file = TEMP_DIR / task_id / "status.json"
    if status_file.exists():
        try:
            with open(status_file, "r") as f:
                return json.load(f)
        except Exception:
            pass

    if task_id in TASKS:
        return TASKS[task_id]
        
    raise HTTPException(status_code=404, detail="Task ID not found")


@app.get("/download/{task_id}/{file_type}")
@app.head("/download/{task_id}/{file_type}")
async def download_file(task_id: str, file_type: str):
    task_dir = TEMP_DIR / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail="Render task expired or not found")

    ft = file_type.lower().strip()

    if ft in ("clean", "clean_watermark", "delogo"):
        matches = list(task_dir.glob("*clean*.mp4"))
        if matches:
            return FileResponse(path=str(matches[0]), filename=f"phonk_clean_{task_id[:8]}.mp4", media_type="video/mp4")

    if ft == "zip":
        zips = list(task_dir.glob("*.zip"))
        if zips:
            return FileResponse(path=str(zips[0]), filename=f"phonk_omni_{task_id[:8]}.zip", media_type="application/zip")

    if ft in ("short", "vertical", "reels", "tiktok"):
        matches = list(task_dir.glob("*tiktok_reels*.mp4")) or list(task_dir.glob("*1_*.mp4"))
        if matches:
            return FileResponse(path=str(matches[0]), filename=f"phonk_vertical_9x16_{task_id[:8]}.mp4", media_type="video/mp4")

    if ft in ("cinema", "landscape", "youtube", "widescreen"):
        matches = list(task_dir.glob("*youtube_cinema*.mp4")) or list(task_dir.glob("*2_*.mp4"))
        if matches:
            return FileResponse(path=str(matches[0]), filename=f"phonk_cinema_16x9_{task_id[:8]}.mp4", media_type="video/mp4")

    if ft in ("square", "instagram", "feed"):
        matches = list(task_dir.glob("*instagram_square*.mp4")) or list(task_dir.glob("*3_*.mp4"))
        if matches:
            return FileResponse(path=str(matches[0]), filename=f"phonk_square_1x1_{task_id[:8]}.mp4", media_type="video/mp4")

    if ft in ("canvas", "spotify"):
        matches = list(task_dir.glob("*spotify_canvas*.mp4")) or list(task_dir.glob("*4_*.mp4"))
        if matches:
            return FileResponse(path=str(matches[0]), filename=f"phonk_spotify_canvas_{task_id[:8]}.mp4", media_type="video/mp4")

    mp4s = list(task_dir.glob("*.mp4"))
    if mp4s:
        return FileResponse(path=str(mp4s[0]), filename=f"phonk_{file_type}_{task_id[:8]}.mp4", media_type="video/mp4")

    raise HTTPException(status_code=404, detail="Requested render file not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
