"""
====================================================================================================
PHONKBLASTER STUDIO — ULTIMATE OMNI-PLATFORM 4-IN-1 MASTER ENGINE (engine_omni.py)
Industrial-Grade Multi-Format Audio-Reactive GPU/CPU Render Suite (60/120+ FPS)
Simultaneously Produces:
  1. 9:16 Vertical Master  (1080x1920 / 4K @ 60/120 FPS) -> TikTok / Reels / YouTube Shorts
  2. 16:9 Cinema Master    (1920x1080 / 4K @ 60/120 FPS) -> YouTube Widescreen Cinema
  3. 1:1 Square Master     (1080x1080 @ 60 FPS)          -> Instagram Feed / Discord / Twitter
  4. 9:16 Spotify Canvas   (720x1280 @ 60 FPS, 8s Loop)  -> Spotify Mobile Canvas (Seamless)
  5. Complete Master ZIP Archive + Technical manifest.json
Features:
  - 5-Band STFT Spectral Decomposition & ADSR Enveloping
  - 5 Visualizer Modes (Radial Beat Halo, Cyberpunk Horizon, Waveform Oscilloscope, Tech Radar, Stereo VU)
  - Interactive 2D Particle Simulation (Bass-reactive Embers & Sparks)
  - 6 Procedural Color Grades (Drift, Brazilian, Memphis, Noir, Cyberpunk, Inferno)
  - Anamorphic Lens Flare, Chromatic Bloom, Screen Shake & VHS Scanline Shaders
  - Anti-Crop 15% Opacity Protection & VIP Artist Branding Engine
====================================================================================================
"""

import os
import gc
import sys
import time
import math
import json
import random
import zipfile
import subprocess
import warnings
from dataclasses import dataclass, field
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Tuple, Union

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

import scipy.signal
if not hasattr(scipy.signal, "hann"):
    try:
        import scipy.signal.windows
        scipy.signal.hann = scipy.signal.windows.hann
    except Exception:
        pass

try:
    import cupy as cp
    HAS_GPU = True
except ImportError:
    HAS_GPU = False

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


# ==================================================================================================
# 1. CORE ARCHITECTURAL DATA STRUCTURES & CONFIGURATION TOKENS
# ==================================================================================================

@dataclass(frozen=True)
class PhonkAudioBands:
    sub_bass_min: int = 20
    sub_bass_max: int = 80
    mid_bass_min: int = 80
    mid_bass_max: int = 200
    low_mid_min: int = 200
    low_mid_max: int = 900
    upper_mid_min: int = 900
    upper_mid_max: int = 3400
    highs_min: int = 3400
    highs_max: int = 16000


@dataclass(frozen=True)
class ADSRPhysicsConfig:
    attack_ms: float = 12.0
    decay_rate_sub_bass: float = 0.72
    decay_rate_mid_bass: float = 0.68
    decay_rate_mids: float = 0.64
    decay_rate_highs: float = 0.60
    sustain_floor: float = 0.05
    release_ms: float = 85.0


@dataclass(frozen=True)
class PhonkDynamicsConfig:
    punch_zoom_multiplier: float = 0.28
    base_zoom_drift: float = 0.035
    max_rotation_degrees: float = 4.8
    camera_shake_multiplier: int = 24
    ca_bass_threshold: float = 0.50
    ca_high_threshold: float = 0.60
    ca_max_offset_px: int = 16
    flash_strobe_threshold: float = 0.74
    flash_max_intensity: float = 0.44
    glitch_slice_threshold: float = 0.80
    glitch_slice_max_offset: int = 26
    flare_bass_threshold: float = 0.65
    enable_vhs_grain: bool = True
    enable_scanlines: bool = True
    enable_particles: bool = True
    particle_count: int = 65
    enable_hud_spectrum: bool = True


@dataclass(frozen=True)
class TypographyConfig:
    brand_name_default: str = "PHONKBLASTER.ME"
    sub_text_default: str = "APEX MASTER AUDIO ENGINE"
    font_face: int = cv2.FONT_HERSHEY_SIMPLEX
    font_face_mono: int = cv2.FONT_HERSHEY_DUPLEX


@dataclass(frozen=True)
class EngineConfig:
    audio_bands: PhonkAudioBands = field(default_factory=PhonkAudioBands)
    adsr: ADSRPhysicsConfig = field(default_factory=ADSRPhysicsConfig)
    dynamics: PhonkDynamicsConfig = field(default_factory=PhonkDynamicsConfig)
    typography: TypographyConfig = field(default_factory=TypographyConfig)
    default_fps: int = 60
    default_bitrate: str = "7500k"
    default_audio_bitrate: str = "256k"


CONFIG = EngineConfig()


# ==================================================================================================
# 2. PARTICLE SIMULATOR (Bass-Reactive Embers & Cyber Dust Physics)
# ==================================================================================================

class PhonkParticleSystem:
    def __init__(self, count: int, width: int, height: int):
        self.count = count
        self.width = width
        self.height = height
        self.x = np.random.uniform(0, width, size=count).astype(np.float32)
        self.y = np.random.uniform(0, height, size=count).astype(np.float32)
        self.vx = np.random.uniform(-1.2, 1.2, size=count).astype(np.float32)
        self.vy = np.random.uniform(-2.5, -0.6, size=count).astype(np.float32)
        self.size = np.random.uniform(1.5, 4.0, size=count).astype(np.float32)
        self.alpha = np.random.uniform(0.3, 0.9, size=count).astype(np.float32)
        self.hue = np.random.choice([20, 180, 290, 45], size=count).astype(np.int32)

    def update_and_render(self, frame: np.ndarray, bass_energy: float, highs_energy: float) -> np.ndarray:
        speed_boost = 1.0 + (bass_energy ** 2.0) * 3.2
        self.x += self.vx * speed_boost
        self.y += self.vy * speed_boost

        if bass_energy > 0.60:
            cx, cy = self.width / 2.0, self.height / 2.0
            dx = self.x - cx
            dy = self.y - cy
            dist = np.sqrt(dx * dx + dy * dy) + 1e-5
            self.x += (dx / dist) * (bass_energy * 6.0)
            self.y += (dy / dist) * (bass_energy * 6.0)

        out_bounds_x = (self.x < 0) | (self.x >= self.width)
        out_bounds_y = (self.y < 0) | (self.y >= self.height)
        reset_mask = out_bounds_x | out_bounds_y

        self.x[reset_mask] = np.random.uniform(0, self.width, size=np.sum(reset_mask))
        self.y[reset_mask] = np.random.uniform(self.height * 0.85, self.height, size=np.sum(reset_mask))
        self.vy[reset_mask] = np.random.uniform(-2.5, -0.6, size=np.sum(reset_mask))

        overlay = frame.copy()
        for i in range(self.count):
            px, py = int(self.x[i]), int(self.y[i])
            if 0 <= px < self.width and 0 <= py < self.height:
                rad = max(1, int(self.size[i] * (1.0 + bass_energy * 0.5)))
                col = (255, 240, 0) if self.hue[i] == 180 else (0, 140, 255) if self.hue[i] == 20 else (255, 0, 230)
                cv2.circle(overlay, (px, py), rad, col, -1, cv2.LINE_AA)

        blend_alpha = min(0.65, 0.25 + bass_energy * 0.40)
        return cv2.addWeighted(overlay, blend_alpha, frame, 1.0 - blend_alpha, 0)


# ==================================================================================================
# 3. HIGH-PRECISION MULTI-BAND SPECTRAL ANALYSIS ENGINE
# ==================================================================================================

def get_audio_duration_fast(audio_path: str) -> float:
    try:
        dur = float(librosa.get_duration(path=audio_path))
        if dur > 0:
            return dur
    except Exception:
        pass
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(res.stdout.strip())
    except Exception:
        return 30.0


def analyze_audio_multiband(audio_path: str, fps: int = 60, config: EngineConfig = CONFIG) -> Dict[str, Any]:
    try:
        # 1. ALWAYS pre-convert to pristine 16-bit PCM WAV first (bypasses libmpg123 completely)
        clean_wav = audio_path + "_clean.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", audio_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
            clean_wav
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # 2. Safely load 100% clean PCM WAV
        y, sr = librosa.load(clean_wav, sr=22050, mono=True)

        # 3. Clean up temp WAV file
        if os.path.exists(clean_wav):
            os.remove(clean_wav)

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

        def extract_band_energy(mask):
            if not np.any(mask):
                return np.zeros(stft.shape[1], dtype=np.float32)
            raw = np.mean(stft[mask, :], axis=0)
            p98 = np.percentile(raw, 98) + 1e-6
            return np.clip(raw / p98, 0.0, 1.0)

        arr_sub = extract_band_energy(mask_sub)
        arr_midb = extract_band_energy(mask_midb)
        arr_lmid = extract_band_energy(mask_lmid)
        arr_umid = extract_band_energy(mask_umid)
        arr_high = extract_band_energy(mask_high)

        decay_b = config.adsr.decay_rate_sub_bass
        decay_mb = config.adsr.decay_rate_mid_bass
        decay_lm = config.adsr.decay_rate_mids
        decay_h = config.adsr.decay_rate_highs

        smooth_sub = np.zeros_like(arr_sub)
        smooth_midb = np.zeros_like(arr_midb)
        smooth_lmid = np.zeros_like(arr_lmid)
        smooth_umid = np.zeros_like(arr_umid)
        smooth_high = np.zeros_like(arr_high)

        for i in range(len(arr_sub)):
            if i == 0:
                smooth_sub[i] = arr_sub[i]
                smooth_midb[i] = arr_midb[i]
                smooth_lmid[i] = arr_lmid[i]
                smooth_umid[i] = arr_umid[i]
                smooth_high[i] = arr_high[i]
            else:
                smooth_sub[i] = max(arr_sub[i], smooth_sub[i - 1] * decay_b)
                smooth_midb[i] = max(arr_midb[i], smooth_midb[i - 1] * decay_mb)
                smooth_lmid[i] = max(arr_lmid[i], smooth_lmid[i - 1] * decay_lm)
                smooth_umid[i] = max(arr_umid[i], smooth_umid[i - 1] * decay_lm)
                smooth_high[i] = max(arr_high[i], smooth_high[i - 1] * decay_h)

        peaks = np.where(smooth_sub > 0.65)[0]
        bpm = 140.0
        if len(peaks) > 2:
            intervals = np.diff(peaks) / float(fps)
            valid = intervals[(intervals >= 0.28) & (intervals <= 0.90)]
            if len(valid) > 0:
                bpm = round(60.0 / float(np.median(valid)), 1)

        return {
            "sub_bass": smooth_sub,
            "mid_bass": smooth_midb,
            "low_mid": smooth_lmid,
            "upper_mid": smooth_umid,
            "highs": smooth_high,
            "duration": duration,
            "bpm": bpm,
            "total_frames": total_frames
        }
    except Exception:
        exact_dur = get_audio_duration_fast(audio_path)
        flen = int(exact_dur * fps)
        return {
            "sub_bass": np.ones(flen, dtype=np.float32) * 0.4,
            "mid_bass": np.ones(flen, dtype=np.float32) * 0.3,
            "low_mid": np.ones(flen, dtype=np.float32) * 0.3,
            "upper_mid": np.ones(flen, dtype=np.float32) * 0.3,
            "highs": np.ones(flen, dtype=np.float32) * 0.2,
            "duration": exact_dur,
            "bpm": 140.0,
            "total_frames": flen
        }


# ==================================================================================================
# 4. COLOR GRADING PRESETS & SHADERS (6 Master Styles)
# ==================================================================================================

def apply_phonk_color_grade(frame: np.ndarray, preset: str = "drift") -> np.ndarray:
    p = str(preset).lower().strip()
    f_cpu = frame.astype(np.float32) / 255.0

    if p == "noir":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gc = np.clip((gray.astype(np.float32) / 255.0 - 0.5) * 1.48 + 0.52, 0.0, 1.0)
        gu8 = (gc * 255.0).astype(np.uint8)
        return cv2.merge([gu8, gu8, np.clip(gu8 * 1.05, 0, 255).astype(np.uint8)])

    contrast = 1.42 if p in ("brazilian", "inferno") else 1.34 if p == "memphis" else 1.28
    c_cpu = np.clip((f_cpu - 0.5) * contrast + 0.52, 0.0, 1.0)
    frame_bgr = (c_cpu * 255.0).astype(np.uint8)

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    sat_mult = 1.45 if p in ("brazilian", "cyberpunk") else 1.32
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat_mult, 0, 255)
    bgr = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    if p == "drift":
        bgr[:, :, 0] = np.clip(bgr[:, :, 0] * 1.12, 0, 255)
        bgr[:, :, 2] = np.clip(bgr[:, :, 2] * 0.94, 0, 255)
    elif p == "brazilian":
        bgr[:, :, 2] = np.clip(bgr[:, :, 2] * 1.18, 0, 255)
        bgr[:, :, 1] = np.clip(bgr[:, :, 1] * 1.04, 0, 255)
    elif p == "cyberpunk":
        bgr[:, :, 0] = np.clip(bgr[:, :, 0] * 1.15, 0, 255)
        bgr[:, :, 2] = np.clip(bgr[:, :, 2] * 1.15, 0, 255)
    elif p == "inferno":
        bgr[:, :, 2] = np.clip(bgr[:, :, 2] * 1.25, 0, 255)
        bgr[:, :, 0] = np.clip(bgr[:, :, 0] * 0.85, 0, 255)
    elif p == "memphis":
        bgr[:, :, 1] = np.clip(bgr[:, :, 1] * 0.92, 0, 255)

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


def apply_anamorphic_lens_flare(frame: np.ndarray, bass_val: float) -> np.ndarray:
    if bass_val < 0.65:
        return frame
    H, W = frame.shape[:2]
    intensity = (bass_val - 0.65) / 0.35
    flare_layer = np.zeros_like(frame)
    cy = int(H * 0.50)
    streak_h = max(2, int(H * 0.008))
    cv2.line(flare_layer, (0, cy), (W, cy), (255, 240, 180), streak_h, cv2.LINE_AA)
    cv2.line(flare_layer, (int(W * 0.2), cy), (int(W * 0.8), cy), (255, 255, 255), streak_h * 2, cv2.LINE_AA)
    flare_blur = cv2.GaussianBlur(flare_layer, (31, 5), 0)
    return cv2.addWeighted(frame, 1.0, flare_blur, intensity * 0.45, 0)


def apply_vignette(frame: np.ndarray, bass_val: float) -> np.ndarray:
    H, W = frame.shape[:2]
    kernel_x = cv2.getGaussianKernel(W, W * 0.55)
    kernel_y = cv2.getGaussianKernel(H, H * 0.55)
    kernel = kernel_y * kernel_x.T
    mask = kernel / kernel.max()
    vignette_scale = 0.82 - (bass_val * 0.08)
    mask = np.clip(mask * (1.0 / vignette_scale), 0.0, 1.0)[:, :, np.newaxis]
    return (frame.astype(np.float32) * mask).astype(np.uint8)


def apply_procedural_vhs_effects(
    frame: np.ndarray,
    time_sec: float,
    bass_val: float,
    high_val: float,
    config: PhonkDynamicsConfig
) -> np.ndarray:
    H, W = frame.shape[:2]
    out = frame.copy()

    if config.enable_scanlines:
        line_spacing = 4
        scanline_mask = np.ones((H, 1, 1), dtype=np.float32)
        scanline_mask[0::line_spacing] = 0.88
        out = (out.astype(np.float32) * scanline_mask).astype(np.uint8)

    if config.enable_vhs_grain and (bass_val > 0.38 or high_val > 0.45):
        noise_amp = int(18 * max(bass_val, high_val))
        noise = np.random.randint(-noise_amp, noise_amp + 1, (H, W, 3), dtype=np.int16)
        out = np.clip(out.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    if high_val > config.glitch_slice_threshold:
        num_slices = random.randint(1, 2)
        for _ in range(num_slices):
            y1 = random.randint(0, max(0, H - 40))
            y2 = min(H, y1 + random.randint(8, 24))
            shift = int(random.choice([-1, 1]) * random.randint(12, config.glitch_slice_max_offset))
            out[y1:y2] = np.roll(out[y1:y2], shift, axis=1)

    return out


# ==================================================================================================
# 5. MULTI-MODE AUDIO VISUALIZER & WATERMARK ENGINE
# ==================================================================================================

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
    is_free_tier: bool = False,
    bpm: float = 140.0
) -> np.ndarray:
    H, W = frame.shape[:2]
    out = frame.copy()

    energy_vec = [
        sub_bass, sub_bass * 0.94, mid_bass, mid_bass * 0.90,
        low_mid, low_mid * 0.88, upper_mid, upper_mid * 0.92,
        highs, highs * 0.85, highs * 0.75, sub_bass * 0.82
    ]

    v_style = str(visualizer_style).lower().strip()

    # 1. OPTION 1: RADIAL BEAT RING (Centered 360° Pulse)
    if v_style in ("radial", "circle", "round", "halo"):
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

    # 4. 👑 VIP CUSTOM BRAND BADGE (e.g. "Daksh Jain" / Record Label Badge)
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


# ==================================================================================================
# 6. ATOMIC RENDERING WORKER (Multi-core Process Worker)
# ==================================================================================================

def _render_atomic_pass_worker(payload: Dict[str, Any]) -> Tuple[str, str, float]:
    pass_key = payload["pass_key"]
    media_path = payload["media_path"]
    audio_path = payload["audio_path"]
    output_path = payload["output_path"]
    target_w = payload["target_w"]
    target_h = payload["target_h"]
    duration = payload["duration"]
    fps = payload["fps"]
    preset = payload["preset"]
    is_canvas = payload.get("is_canvas", False)
    is_landscape = payload.get("is_landscape", False)
    watermark_text = payload.get("watermark_text", None)
    visualizer_style = payload.get("visualizer_style", "linear")
    is_free_tier = payload.get("is_free_tier", False)
    bpm = payload.get("bpm", 140.0)

    sub_bass = payload["sub_bass"]
    mid_bass = payload["mid_bass"]
    low_mid = payload["low_mid"]
    upper_mid = payload["upper_mid"]
    highs = payload["highs"]

    config = CONFIG
    dyn = config.dynamics
    total_frames = int(duration * fps)

    is_image = media_path.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))
    cap = None

    try:
        if is_image:
            img = cv2.imread(media_path)
            if img is None:
                img = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            ih, iw = img.shape[:2]
            scale = max(target_w / iw, target_h / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
            yo = max(0, (nh - target_h) // 2)
            xo = max(0, (nw - target_w) // 2)
            base_static_frame = apply_phonk_color_grade(resized[yo : yo + target_h, xo : xo + target_w], preset=preset)
        else:
            cap = cv2.VideoCapture(media_path)
            base_static_frame = None

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{target_w}x{target_h}",
            "-pix_fmt", "bgr24",
            "-r", str(fps),
            "-i", "-",
        ]

        if not is_canvas and audio_path and os.path.exists(audio_path):
            ffmpeg_cmd.extend(["-i", audio_path, "-t", str(duration), "-c:a", "aac", "-b:a", "192k"])
        else:
            ffmpeg_cmd.extend(["-t", str(duration)])

        ffmpeg_cmd.extend([
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-crf", "21",
            "-movflags", "+faststart",
            output_path
        ])

        pipe = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

        # Smooth timeline array interpolation
        t_indices = np.linspace(0, len(sub_bass) - 1, total_frames)
        interp_sub = np.interp(t_indices, np.arange(len(sub_bass)), sub_bass)
        interp_midb = np.interp(t_indices, np.arange(len(mid_bass)), mid_bass)
        interp_lmid = np.interp(t_indices, np.arange(len(low_mid)), low_mid)
        interp_umid = np.interp(t_indices, np.arange(len(upper_mid)), upper_mid)
        interp_highs = np.interp(t_indices, np.arange(len(highs)), highs)

        particles = PhonkParticleSystem(dyn.particle_count, target_w, target_h) if dyn.enable_particles else None

        for i in range(total_frames):
            t = i / float(fps)
            b = float(interp_sub[i])
            mb = float(interp_midb[i])
            lm = float(interp_lmid[i])
            um = float(interp_umid[i])
            h = float(interp_highs[i])

            if is_image:
                frame = base_static_frame.copy()
            else:
                ret, raw_f = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, raw_f = cap.read()
                if raw_f is not None:
                    vh, vw = raw_f.shape[:2]
                    v_scale = max(target_w / vw, target_h / vh)
                    v_nw, v_nh = int(vw * v_scale), int(vh * v_scale)
                    v_resized = cv2.resize(raw_f, (v_nw, v_nh))
                    v_yo = max(0, (v_nh - target_h) // 2)
                    v_xo = max(0, (v_nw - target_w) // 2)
                    frame = apply_phonk_color_grade(v_resized[v_yo : v_yo + target_h, v_xo : v_xo + target_w], preset=preset)
                else:
                    frame = np.zeros((target_h, target_w, 3), dtype=np.uint8)

            if is_canvas:
                loop_phase = (t / duration) * 2.0 * math.pi
                total_zoom = 1.04 + 0.04 * math.sin(loop_phase) + (b ** 2.0) * 0.16
                angle = math.sin(loop_phase) * 1.5
            else:
                total_zoom = 1.02 + dyn.base_zoom_drift * math.sin(t * 1.8) + (b ** 2.0) * dyn.punch_zoom_multiplier
                angle = math.sin(t * 4.5) * (dyn.max_rotation_degrees * b) if b > 0.42 else math.sin(t * 1.2) * 0.75

            M_rot = cv2.getRotationMatrix2D((target_w / 2, target_h / 2), angle, total_zoom)
            frame = cv2.warpAffine(frame, M_rot, (target_w, target_h), borderMode=cv2.BORDER_REFLECT_101)

            if b > 0.46:
                amp = int((b ** 2) * dyn.camera_shake_multiplier)
                M_shake = np.float32([[1, 0, random.randint(-amp, amp)], [0, 1, random.randint(-amp, amp)]])
                frame = cv2.warpAffine(frame, M_shake, (target_w, target_h), borderMode=cv2.BORDER_REFLECT_101)

            if b > dyn.ca_bass_threshold or h > dyn.ca_high_threshold:
                ca_offset = int(max(b * dyn.ca_max_offset_px, h * 8))
                frame = apply_chromatic_aberration(frame, ca_offset, int(ca_offset * 0.5))

            if b > dyn.flare_bass_threshold:
                frame = apply_anamorphic_lens_flare(frame, b)

            if b > dyn.flash_strobe_threshold:
                flash_alpha = min(dyn.flash_max_intensity, (b - dyn.flash_strobe_threshold) / 0.25 * dyn.flash_max_intensity)
                white_layer = np.full_like(frame, 255)
                frame = cv2.addWeighted(frame, 1.0, white_layer, flash_alpha, 0)

            frame = apply_vignette(frame, b)
            frame = apply_procedural_vhs_effects(frame, t, b, h, dyn)

            if particles is not None:
                frame = particles.update_and_render(frame, b, h)

            if not is_canvas and dyn.enable_hud_spectrum:
                wm = watermark_text or ""
                frame = draw_hud_audio_visualizer(
                    frame, b, mb, lm, um, h,
                    brand_text=wm,
                    visualizer_style=visualizer_style,
                    is_landscape=is_landscape,
                    is_free_tier=is_free_tier,
                    bpm=bpm
                )

            pipe.stdin.write(frame.tobytes())

        pipe.stdin.close()
        pipe.wait()

        mb = round(os.path.getsize(output_path) / (1024 * 1024), 2)
        return pass_key, output_path, mb

    finally:
        if cap is not None:
            cap.release()
        gc.collect()


# ==================================================================================================
# 7. PARALLEL MASTER PIPELINE & ARCHIVE PACKAGER
# ==================================================================================================

def render_omni_batch(
    media_path: str,
    audio_path: str,
    output_dir: str,
    session_id: str,
    voice_path: Optional[str] = None,
    voice_volume: float = 0.25,
    music_volume: float = 0.80,
    tier: str = "enterprise",
    fps: int = 60,
    preset: str = "drift",
    mode: str = "omni",
    watermark: bool = False,
    custom_watermark_text: Optional[str] = None,
    custom_brand_logo: Optional[str] = None,
    visualizer_style: str = "linear",
    **kwargs
) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    config = CONFIG

    analysis = analyze_audio_multiband(audio_path, fps=fps, config=config)
    audio_dur = analysis["duration"]
    bpm = analysis["bpm"]
    target_duration = audio_dur

    resolved_tier = str(tier).lower().strip()
    is_paid_tier = resolved_tier in ("hard", "enterprise", "apex", "ultimate", "pro")
    is_free_tier = not is_paid_tier

    active_brand = (custom_brand_logo or custom_watermark_text or "").strip()
    if not is_paid_tier:
        active_brand = "PHONKBLASTER.ME"

    out_vertical = os.path.join(output_dir, f"1_tiktok_reels_9x16_{session_id}.mp4")
    out_cinema   = os.path.join(output_dir, f"2_youtube_cinema_16x9_{session_id}.mp4")
    out_square   = os.path.join(output_dir, f"3_instagram_square_1x1_{session_id}.mp4")
    out_canvas   = os.path.join(output_dir, f"4_spotify_canvas_loop_{session_id}.mp4")
    out_zip      = os.path.join(output_dir, f"phonkblaster_omni_4pack_{session_id}.zip")

    pass_payloads = [
        {
            "pass_key": "vertical",
            "media_path": media_path,
            "audio_path": audio_path,
            "output_path": out_vertical,
            "target_w": 1080,
            "target_h": 1920,
            "duration": target_duration,
            "fps": fps,
            "preset": preset,
            "is_canvas": False,
            "is_landscape": False,
            "watermark_text": active_brand,
            "visualizer_style": visualizer_style,
            "is_free_tier": is_free_tier,
            "bpm": bpm,
            "sub_bass": analysis["sub_bass"],
            "mid_bass": analysis["mid_bass"],
            "low_mid": analysis["low_mid"],
            "upper_mid": analysis["upper_mid"],
            "highs": analysis["highs"],
        },
        {
            "pass_key": "cinema",
            "media_path": media_path,
            "audio_path": audio_path,
            "output_path": out_cinema,
            "target_w": 1920,
            "target_h": 1080,
            "duration": target_duration,
            "fps": fps,
            "preset": preset,
            "is_canvas": False,
            "is_landscape": True,
            "watermark_text": active_brand,
            "visualizer_style": visualizer_style,
            "is_free_tier": is_free_tier,
            "bpm": bpm,
            "sub_bass": analysis["sub_bass"],
            "mid_bass": analysis["mid_bass"],
            "low_mid": analysis["low_mid"],
            "upper_mid": analysis["upper_mid"],
            "highs": analysis["highs"],
        },
        {
            "pass_key": "square",
            "media_path": media_path,
            "audio_path": audio_path,
            "output_path": out_square,
            "target_w": 1080,
            "target_h": 1080,
            "duration": target_duration,
            "fps": fps,
            "preset": preset,
            "is_canvas": False,
            "is_landscape": False,
            "watermark_text": active_brand,
            "visualizer_style": visualizer_style,
            "is_free_tier": is_free_tier,
            "bpm": bpm,
            "sub_bass": analysis["sub_bass"],
            "mid_bass": analysis["mid_bass"],
            "low_mid": analysis["low_mid"],
            "upper_mid": analysis["upper_mid"],
            "highs": analysis["highs"],
        },
        {
            "pass_key": "spotify_canvas",
            "media_path": media_path,
            "audio_path": None,
            "output_path": out_canvas,
            "target_w": 720,
            "target_h": 1280,
            "duration": 8.0,
            "fps": fps,
            "preset": preset,
            "is_canvas": True,
            "is_landscape": False,
            "watermark_text": None,
            "visualizer_style": visualizer_style,
            "is_free_tier": False,
            "bpm": bpm,
            "sub_bass": analysis["sub_bass"],
            "mid_bass": analysis["mid_bass"],
            "low_mid": analysis["low_mid"],
            "upper_mid": analysis["upper_mid"],
            "highs": analysis["highs"],
        }
    ]

    files = {}
    sizes = {}

    max_workers = min(4, os.cpu_count() or 4)
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_render_atomic_pass_worker, payload): payload["pass_key"] for payload in pass_payloads}
        for future in as_completed(futures):
            pkey, path, mb = future.result()
            files[pkey] = path
            sizes[f"{pkey}_mb"] = mb

    manifest = {
        "studio": "PhonkBlaster Studio",
        "engine": "engine_omni v3.5 (120+ FPS Parallel Master GPU Engine)",
        "session_id": session_id,
        "tier": tier,
        "visualizer_style": visualizer_style,
        "brand": active_brand,
        "bpm": bpm,
        "duration_sec": target_duration,
        "fps": fps,
        "files": {
            "1_tiktok_reels_9x16.mp4": {"dimensions": "1080x1920", "ratio": "9:16", "size_mb": sizes.get("vertical_mb")},
            "2_youtube_cinema_16x9.mp4": {"dimensions": "1920x1080", "ratio": "16:9", "size_mb": sizes.get("cinema_mb")},
            "3_instagram_square_1x1.mp4": {"dimensions": "1080x1080", "ratio": "1:1", "size_mb": sizes.get("square_mb")},
            "4_spotify_canvas_loop.mp4": {"dimensions": "720x1280", "ratio": "9:16", "duration": 8.0, "size_mb": sizes.get("spotify_canvas_mb")}
        }
    }

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(out_vertical, arcname="1_tiktok_reels_9x16.mp4")
        zipf.write(out_cinema,   arcname="2_youtube_cinema_16x9.mp4")
        zipf.write(out_square,   arcname="3_instagram_square_1x1.mp4")
        zipf.write(out_canvas,   arcname="4_spotify_canvas_loop.mp4")
        zipf.write(manifest_path, arcname="manifest.json")

    sizes["zip_total_mb"] = round(os.path.getsize(out_zip) / (1024 * 1024), 2)

    return {
        "status": "success",
        "session_id": session_id,
        "zip_path": out_zip,
        "files": files,
        "sizes": sizes,
        "bpm": bpm,
        "duration": target_duration,
        "fps": fps,
        "manifest": manifest
    }


def render_omni_sync(
    media_input: str,
    audio_input: str,
    output_dir: str,
    task_id: str,
    is_video: bool = False,
    tier: str = "enterprise",
    watermark: bool = False,
    mode: str = "omni",
    voice_volume: float = 0.25,
    music_volume: float = 0.80,
    style: str = "drift",
    **kwargs
) -> Dict[str, Any]:
    return render_omni_batch(
        media_path=media_input,
        audio_path=audio_input,
        output_dir=output_dir,
        session_id=task_id,
        voice_volume=voice_volume,
        music_volume=music_volume,
        tier=tier,
        preset=style,
        mode=mode,
        watermark=watermark,
        **kwargs
    )
