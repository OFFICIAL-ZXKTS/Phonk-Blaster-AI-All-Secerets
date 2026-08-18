"""
====================================================================================================
PHONKBLASTER STUDIO — AUDIO-REACTIVE PHOTO BOUNCE ENGINE (engine_photo.py)
Image-to-Video 60/120 FPS Phonk Drift Generator • Camera Bass Shakes • Multi-Band Spectrum Glow
Features: Dual Visualizer (Radial Halo & Cyberpunk Horizon) • Anti-Crop Protection • Custom Brand Logo
====================================================================================================
"""

import os
import gc
import sys
import math
import random
import subprocess
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

try:
    import librosa
except ImportError:
    librosa = None

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


@dataclass(frozen=True)
class PhotoAudioBands:
    sub_bass_min: int = 25
    sub_bass_max: int = 85
    mid_bass_min: int = 85
    mid_bass_max: int = 220
    low_mid_min: int = 220
    low_mid_max: int = 900
    upper_mid_min: int = 900
    upper_mid_max: int = 3400
    highs_min: int = 3400
    highs_max: int = 16000


@dataclass(frozen=True)
class PhotoDynamicsConfig:
    decay_rate_sub_bass: float = 0.74
    decay_rate_highs: float = 0.68
    punch_zoom_multiplier: float = 0.28
    base_zoom_drift: float = 0.035
    max_rotation_degrees: float = 4.5
    camera_shake_multiplier: int = 22
    ca_bass_threshold: float = 0.52
    ca_high_threshold: float = 0.62
    ca_max_offset_px: int = 14
    flash_strobe_threshold: float = 0.75
    flash_max_intensity: float = 0.40
    glitch_slice_threshold: float = 0.82
    glitch_slice_max_offset: int = 24
    enable_vhs_grain: bool = True
    enable_scanlines: bool = True
    enable_hud_spectrum: bool = True


@dataclass(frozen=True)
class PhotoEngineConfig:
    audio_bands: PhotoAudioBands = field(default_factory=PhotoAudioBands)
    dynamics: PhotoDynamicsConfig = field(default_factory=PhotoDynamicsConfig)


CONFIG = PhotoEngineConfig()


def get_audio_duration_fast(audio_path: str) -> float:
    try:
        duration = float(librosa.get_duration(path=audio_path))
        if duration > 0:
            return duration
    except Exception:
        pass

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except Exception:
        return 30.0


def analyze_photo_audio_multiband(
    audio_path: str,
    fps: int = 60,
    config: PhotoEngineConfig = CONFIG
) -> Dict[str, Any]:
    try:
        # 1. ALWAYS convert to clean 16-bit PCM WAV first (bypasses libmpg123 completely)
        clean_wav = audio_path + "_clean.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", audio_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
            clean_wav
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 2. Load the clean WAV
        y, sr = librosa.load(clean_wav, sr=22050, mono=True)

        # 3. Clean up temp WAV file
        if os.path.exists(clean_wav):
            os.remove(clean_wav)

        duration = float(librosa.get_duration(y=y, sr=sr))
        total_frames = int(duration * fps)

        duration = float(librosa.get_duration(y=y, sr=sr))
        total_frames = int(duration * fps)

        hop_length = max(1, int(sr / fps))
        stft = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop_length))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)

        bands = config.audio_bands
        mask_sub = (freqs >= bands.sub_bass_min) & (freqs <= bands.sub_bass_max)
        mask_midb = (freqs >= bands.mid_bass_min) & (freqs <= bands.mid_bass_max)
        mask_lmid = (freqs >= bands.low_mid_min) & (freqs <= bands.low_mid_max)
        mask_umid = (freqs >= bands.upper_mid_min) & (freqs <= bands.upper_mid_max)
        mask_high = (freqs >= bands.highs_min) & (freqs <= bands.highs_max)

        def get_band(mask):
            if not np.any(mask):
                return np.zeros(stft.shape[1], dtype=np.float32)
            energy = np.mean(stft[mask, :], axis=0)
            p98 = np.percentile(energy, 98) + 1e-6
            return np.clip(energy / p98, 0.0, 1.0)

        arr_sub = get_band(mask_sub)
        arr_midb = get_band(mask_midb)
        arr_lmid = get_band(mask_lmid)
        arr_umid = get_band(mask_umid)
        arr_high = get_band(mask_high)

        decay_b = config.dynamics.decay_rate_sub_bass
        decay_h = config.dynamics.decay_rate_highs
        smooth_sub = np.zeros_like(arr_sub)
        smooth_high = np.zeros_like(arr_high)

        for i in range(len(arr_sub)):
            smooth_sub[i] = arr_sub[i] if i == 0 else max(arr_sub[i], smooth_sub[i - 1] * decay_b)
            smooth_high[i] = arr_high[i] if i == 0 else max(arr_high[i], smooth_high[i - 1] * decay_h)

        return {
            "sub_bass": smooth_sub,
            "mid_bass": arr_midb,
            "low_mid": arr_lmid,
            "upper_mid": arr_umid,
            "highs": smooth_high,
            "duration": duration,
            "total_frames": total_frames
        }
    except Exception:
        exact_dur = get_audio_duration_fast(audio_path)
        fallback_len = int(exact_dur * fps)
        return {
            "sub_bass": np.ones(fallback_len, dtype=np.float32) * 0.4,
            "mid_bass": np.ones(fallback_len, dtype=np.float32) * 0.3,
            "low_mid": np.ones(fallback_len, dtype=np.float32) * 0.3,
            "upper_mid": np.ones(fallback_len, dtype=np.float32) * 0.3,
            "highs": np.ones(fallback_len, dtype=np.float32) * 0.2,
            "duration": exact_dur,
            "total_frames": fallback_len
        }


def apply_photo_phonk_color_grade(frame: np.ndarray, preset: str = "drift") -> np.ndarray:
    f_cpu = frame.astype(np.float32) / 255.0
    if preset == "noir":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gc = np.clip((gray.astype(np.float32) / 255.0 - 0.5) * 1.46 + 0.52, 0.0, 1.0)
        gu8 = (gc * 255.0).astype(np.uint8)
        return cv2.merge([gu8, gu8, (gu8 * 1.05).clip(0, 255).astype(np.uint8)])
    
    contrast_mult = 1.40 if preset == "brazilian" else 1.35 if preset == "memphis" else 1.28
    c_cpu = np.clip((f_cpu - 0.5) * contrast_mult + 0.52, 0.0, 1.0)
    frame_bgr = (c_cpu * 255.0).astype(np.uint8)

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.35, 0, 255)
    bgr = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    if preset == "drift":
        bgr[:, :, 0] = np.clip(bgr[:, :, 0] * 1.10, 0, 255)
        bgr[:, :, 2] = np.clip(bgr[:, :, 2] * 0.95, 0, 255)
    elif preset == "brazilian":
        bgr[:, :, 2] = np.clip(bgr[:, :, 2] * 1.15, 0, 255)
    return bgr


def apply_chromatic_aberration(frame: np.ndarray, offset_x: int, offset_y: int) -> np.ndarray:
    if abs(offset_x) < 1 and abs(offset_y) < 1:
        return frame
    b, g, r = cv2.split(frame)
    rows, cols = frame.shape[:2]
    M_red = np.float32([[1, 0, offset_x], [0, 1, offset_y]])
    M_blue = np.float32([[1, 0, -offset_x], [0, 1, -offset_y]])
    r_s = cv2.warpAffine(r, M_red, (cols, rows), borderMode=cv2.BORDER_REFLECT_101)
    b_s = cv2.warpAffine(b, M_blue, (cols, rows), borderMode=cv2.BORDER_REFLECT_101)
    return cv2.merge([b_s, g, r_s])


def apply_procedural_vhs_effects(
    frame: np.ndarray,
    bass_val: float,
    high_val: float,
    config: PhotoDynamicsConfig
) -> np.ndarray:
    H, W = frame.shape[:2]
    out = frame.copy()

    if config.enable_scanlines:
        out[0::4, :] = (out[0::4, :].astype(np.float32) * 0.88).astype(np.uint8)

    if high_val > config.glitch_slice_threshold:
        for _ in range(random.randint(1, 2)):
            y1 = random.randint(0, max(0, H - 40))
            y2 = min(H, y1 + random.randint(8, 24))
            shift = int(random.choice([-1, 1]) * random.randint(10, config.glitch_slice_max_offset))
            out[y1:y2] = np.roll(out[y1:y2], shift, axis=1)

    return out


def draw_hud_audio_visualizer(
    frame: np.ndarray,
    sub_bass: float,
    mid_bass: float,
    low_mid: float,
    upper_mid: float,
    highs: float,
    brand_text: str = "",
    visualizer_style: str = "linear",
    is_landscape: bool = False,
    is_free_tier: bool = False
) -> np.ndarray:
    H, W = frame.shape[:2]
    out = frame.copy()

    energy_vec = [
        sub_bass, sub_bass * 0.92, mid_bass, mid_bass * 0.88,
        low_mid, low_mid * 0.90, upper_mid, upper_mid * 0.95,
        highs, highs * 0.85, highs * 0.75, sub_bass * 0.80
    ]

    # 1. OPTION 1: RADIAL BEAT RING (Centered 360° Pulse)
    if str(visualizer_style).lower() in ("radial", "circle", "round", "halo"):
        cx, cy = W // 2, H // 2
        base_radius = int(min(W, H) * (0.16 if is_landscape else 0.18))
        bass_radius = int(base_radius * (1.0 + (sub_bass ** 1.8) * 0.24))

        ring_color = (255, int(240 * (1.0 - sub_bass * 0.3)), int(200 * sub_bass))
        cv2.circle(out, (cx, cy), bass_radius, ring_color, 3, cv2.LINE_AA)

        if sub_bass > 0.55:
            aura_radius = int(bass_radius * 1.15)
            cv2.circle(out, (cx, cy), aura_radius, (200, 80, 255), 1, cv2.LINE_AA)

        num_rays = 36
        angle_step = 360.0 / num_rays
        max_ray_len = int(min(W, H) * 0.12)

        for i in range(num_rays):
            deg = i * angle_step
            rad = math.radians(deg)
            val = energy_vec[i % len(energy_vec)]
            ray_len = int(max(4, val * max_ray_len * (1.0 + sub_bass * 0.3)))

            x1 = int(cx + (bass_radius + 2) * math.cos(rad))
            y1 = int(cy + (bass_radius + 2) * math.sin(rad))
            x2 = int(cx + (bass_radius + 2 + ray_len) * math.cos(rad))
            y2 = int(cy + (bass_radius + 2 + ray_len) * math.sin(rad))

            cv2.line(out, (x1, y1), (x2, y2), (255, 230, 0), 2, cv2.LINE_AA)

    # 2. OPTION 2: CYBERPUNK HORIZON (Bottom Symmetrical Spectrum)
    else:
        num_bars = 20 if is_landscape else 16
        bar_width = int(W * (0.012 if is_landscape else 0.018))
        bar_gap = int(W * 0.006)
        total_w = num_bars * (bar_width + bar_gap)
        start_x = (W - total_w) // 2
        base_y = int(H * 0.90)
        max_h = int(H * 0.09)

        overlay_box_w = int(total_w * 1.12)
        overlay_box_h = int(max_h * 1.25)
        box_x1 = max(0, start_x - int(total_w * 0.06))
        box_y1 = max(0, base_y - overlay_box_h)
        box_x2 = min(W, box_x1 + overlay_box_w)
        box_y2 = min(H, base_y + 8)

        overlay = out.copy()
        cv2.rectangle(overlay, (box_x1, box_y1), (box_x2, box_y2), (10, 10, 15), -1)
        cv2.addWeighted(overlay, 0.45, out, 0.55, 0, out)

        half = num_bars // 2
        for i in range(num_bars):
            dist_from_center = abs(i - half) / float(half)
            idx = int(dist_from_center * (len(energy_vec) - 1))
            val = float(energy_vec[idx])
            
            bh = int(max(3, val * max_h * (1.0 + sub_bass * 0.15)))
            bx = start_x + i * (bar_width + bar_gap)
            by = base_y - bh

            color = (
                int(255 - dist_from_center * 80),
                int(243 - dist_from_center * 160),
                int(dist_from_center * 220)
            )
            cv2.rectangle(out, (bx, by), (bx + bar_width, base_y), color, -1, cv2.LINE_AA)

    # 3. 🛡️ UNCROPPABLE 15% OPACITY WATERMARK (Free Tier Only)
    if is_free_tier:
        uncrop_text = "PHONKBLASTER.ME"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = W / 950.0
        thickness = 2
        
        text_size, _ = cv2.getTextSize(uncrop_text, font, font_scale, thickness)
        tw, th = text_size
        center_x = (W - tw) // 2
        center_y = int(H * 0.62)

        watermark_layer = out.copy()
        cv2.putText(watermark_layer, uncrop_text, (center_x, center_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
        cv2.addWeighted(watermark_layer, 0.15, out, 0.85, 0, out)

    # 4. 👑 CUSTOM BRAND BADGE (e.g. "Daksh Jain" or Official Badge)
    if brand_text:
        clean_text = brand_text.upper().strip()
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = W / 1400.0
        thickness = 2
        text_size, _ = cv2.getTextSize(clean_text, font, font_scale, thickness)
        tw, th = text_size

        px = int(W * 0.04)
        py = int(H * 0.95)

        pill_pad = 8
        pill_overlay = out.copy()
        cv2.rectangle(
            pill_overlay,
            (px - pill_pad, py - th - pill_pad),
            (px + tw + pill_pad, py + pill_pad),
            (0, 0, 0),
            -1
        )
        cv2.addWeighted(pill_overlay, 0.60, out, 0.40, 0, out)
        cv2.putText(out, clean_text, (px, py), font, font_scale, (255, 243, 0), thickness, cv2.LINE_AA)

    return out


def generate_phonk_image_render(
    image_path: str,
    audio_path: str,
    output_path: str,
    mode: str = "short",
    resolution: str = "1080p",
    fps: int = 60,
    style: str = "drift",
    tier: str = "enterprise",
    watermark: bool = False,
    custom_watermark_text: Optional[str] = None,
    custom_brand_logo: Optional[str] = None,
    visualizer_style: str = "linear"
) -> str:
    config = CONFIG
    dyn = config.dynamics

    mode_str = str(mode).lower().strip()
    is_landscape = mode_str in ("long", "cinema", "widescreen", "16:9", "16x9", "youtube")
    is_square = mode_str in ("square", "1:1", "1x1", "instagram")

    if is_landscape:
        res_table = {
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "4k": (3840, 2160),
        }
        target_w, target_h = res_table.get(resolution, (1920, 1080))
    elif is_square:
        res_table = {
            "720p": (720, 720),
            "1080p": (1080, 1080),
            "4k": (2160, 2160),
        }
        target_w, target_h = res_table.get(resolution, (1080, 1080))
    else:
        res_table = {
            "720p": (720, 1280),
            "1080p": (1080, 1920),
            "4k": (2160, 3840),
        }
        target_w, target_h = res_table.get(resolution, (1080, 1920))

    target_fps = int(fps) if fps in (30, 60, 120) else 60

    analysis = analyze_photo_audio_multiband(audio_path, fps=target_fps, config=config)
    sub_bass = analysis["sub_bass"]
    mid_bass = analysis["mid_bass"]
    low_mid = analysis["low_mid"]
    upper_mid = analysis["upper_mid"]
    highs = analysis["highs"]
    
    target_dur = analysis["duration"]
    total_frames = int(target_dur * target_fps)

    resolved_tier = str(tier).lower().strip()
    is_paid_tier = resolved_tier in ("hard", "enterprise", "apex", "ultimate", "pro")
    is_free_tier = not is_paid_tier

    active_brand = (custom_brand_logo or custom_watermark_text or "").strip()
    if not is_paid_tier:
        active_brand = "PHONKBLASTER.ME"

    img = cv2.imread(image_path)
    if img is None:
        img = np.zeros((target_h, target_w, 3), dtype=np.uint8)

    ih, iw = img.shape[:2]
    scale = max(target_w / iw, target_h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    yo = max(0, (nh - target_h) // 2)
    xo = max(0, (nw - target_w) // 2)
    BASE_FRAME = apply_photo_phonk_color_grade(resized[yo : yo + target_h, xo : xo + target_w], preset=style)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{target_w}x{target_h}",
        "-pix_fmt", "bgr24",
        "-r", str(target_fps),
        "-i", "-",
        "-i", audio_path,
        "-t", str(target_dur),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ]

    pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    t_indices = np.linspace(0, len(sub_bass) - 1, total_frames)
    interp_sub = np.interp(t_indices, np.arange(len(sub_bass)), sub_bass)
    interp_midb = np.interp(t_indices, np.arange(len(mid_bass)), mid_bass)
    interp_lmid = np.interp(t_indices, np.arange(len(low_mid)), low_mid)
    interp_umid = np.interp(t_indices, np.arange(len(upper_mid)), upper_mid)
    interp_highs = np.interp(t_indices, np.arange(len(highs)), highs)

    for i in range(total_frames):
        t = i / float(target_fps)
        b = float(interp_sub[i])
        mb = float(interp_midb[i])
        lm = float(interp_lmid[i])
        um = float(interp_umid[i])
        h = float(interp_highs[i])

        base_zoom = 1.02 + dyn.base_zoom_drift * math.sin(t * 1.8)
        bass_zoom = (b ** 2.0) * dyn.punch_zoom_multiplier
        total_zoom = base_zoom + bass_zoom
        angle = math.sin(t * 4.5) * (dyn.max_rotation_degrees * b) if b > 0.42 else math.sin(t * 1.2) * 0.8

        M_zoom = cv2.getRotationMatrix2D((target_w / 2, target_h / 2), angle, total_zoom)
        frame = cv2.warpAffine(BASE_FRAME, M_zoom, (target_w, target_h), borderMode=cv2.BORDER_REFLECT_101)

        if b > 0.48:
            amp = int((b ** 2) * dyn.camera_shake_multiplier)
            M_shake = np.float32([[1, 0, random.randint(-amp, amp)], [0, 1, random.randint(-amp, amp)]])
            frame = cv2.warpAffine(frame, M_shake, (target_w, target_h), borderMode=cv2.BORDER_REFLECT_101)

        if b > dyn.ca_bass_threshold or h > dyn.ca_high_threshold:
            ca_val = int(max(b * dyn.ca_max_offset_px, h * 8))
            frame = apply_chromatic_aberration(frame, ca_val, int(ca_val * 0.5))

        if b > dyn.flash_strobe_threshold:
            flash_alpha = min(dyn.flash_max_intensity, (b - dyn.flash_strobe_threshold) / 0.25 * dyn.flash_max_intensity)
            white_layer = np.full_like(frame, 255)
            frame = cv2.addWeighted(frame, 1.0, white_layer, flash_alpha, 0)

        frame = apply_procedural_vhs_effects(frame, b, h, dyn)

        if dyn.enable_hud_spectrum:
            wm_label = active_brand if (watermark or active_brand) else ""
            frame = draw_hud_audio_visualizer(
                frame, b, mb, lm, um, h,
                brand_text=wm_label,
                visualizer_style=visualizer_style,
                is_landscape=is_landscape,
                is_free_tier=is_free_tier
            )

        pipe.stdin.write(frame.tobytes())

    pipe.stdin.close()
    pipe.wait()

    return output_path


def generate_phonk_video(image_input_path: str, audio_input_path: str, video_output_path: str):
    return generate_phonk_image_render(
        image_path=image_input_path,
        audio_path=audio_input_path,
        output_path=video_output_path,
        mode="long"
    )


def generate_phonk_short(image_path: str, audio_path: str, output_path: str):
    return generate_phonk_image_render(
        image_path=image_path,
        audio_path=audio_path,
        output_path=output_path,
        mode="short"
    )


def render_photo_bounce(
    image_input: str,
    audio_input: str,
    output_path: str,
    mode: str = "short",
    watermark: bool = False,
    resolution: str = "1080p",
    fps: int = 60,
    style: str = "drift",
    tier: str = "enterprise",
    custom_watermark_text: Optional[str] = None,
    custom_brand_logo: Optional[str] = None,
    visualizer_style: str = "linear",
    **kwargs
) -> str:
    return generate_phonk_image_render(
        image_path=image_input,
        audio_path=audio_input,
        output_path=output_path,
        mode=mode,
        resolution=resolution,
        fps=fps,
        style=style,
        tier=tier,
        watermark=watermark,
        custom_watermark_text=custom_watermark_text,
        custom_brand_logo=custom_brand_logo,
        visualizer_style=visualizer_style
    )
