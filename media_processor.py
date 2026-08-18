import os
import subprocess
import logging
from typing import Optional

logger = logging.getLogger("MediaProcessor")

class MediaProcessor:
    @staticmethod
    def trim_and_fade_audio(
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        fade_in: bool = True,
        fade_out: bool = True,
        fade_duration: float = 0.5
    ) -> str:
        filters = []
        if fade_in:
            filters.append(f"afade=t=in:st=0:d={fade_duration}")
        if fade_out and duration > fade_duration:
            out_start = max(0.0, duration - fade_duration)
            filters.append(f"afade=t=out:st={out_start:.2f}:d={fade_duration}")

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start_time:.3f}",
            "-t", f"{duration:.3f}",
            "-i", input_path
        ]
        if filters:
            cmd.extend(["-af", ",".join(filters)])
        cmd.extend(["-c:a", "aac", "-b:a", "192k", output_path])

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_path

    @staticmethod
    def crop_and_trim_video(
        input_path: str,
        output_path: str,
        crop_x: int,
        crop_y: int,
        crop_w: int,
        crop_h: int,
        start_time: Optional[float] = None,
        duration: Optional[float] = None
    ) -> str:
        cmd = ["ffmpeg", "-y"]
        if start_time is not None:
            cmd.extend(["-ss", f"{start_time:.3f}"])
        if duration is not None:
            cmd.extend(["-t", f"{duration:.3f}"])
        cmd.extend(["-i", input_path])

        crop_w = crop_w - (crop_w % 2)
        crop_h = crop_h - (crop_h % 2)
        crop_filter = f"crop=w={crop_w}:h={crop_h}:x={crop_x}:y={crop_y}"

        cmd.extend([
            "-vf", crop_filter,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            output_path
        ])
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_path

    @staticmethod
    def crop_image(input_path: str, output_path: str, crop_x: int, crop_y: int, crop_w: int, crop_h: int) -> str:
        crop_w = crop_w - (crop_w % 2)
        crop_h = crop_h - (crop_h % 2)
        crop_filter = f"crop=w={crop_w}:h={crop_h}:x={crop_x}:y={crop_y}"
        cmd = ["ffmpeg", "-y", "-i", input_path, "-vf", crop_filter, output_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_path
