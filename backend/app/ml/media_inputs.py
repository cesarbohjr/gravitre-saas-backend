"""Bounded local media decoding. Never fetch caller-supplied URLs.

Images are re-encoded to remove metadata. Video analysis uses sampled frames,
not a claim to exhaustive temporal understanding. Audio uses the existing STT.
"""
from __future__ import annotations

import base64
import io
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 16_000_000


def image_part(data: bytes) -> dict[str, Any]:
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_BYTES:
        raise ValueError("Media must contain 1-20 MiB of bytes")
    with Image.open(io.BytesIO(data)) as image:
        if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > MAX_PIXELS:
            raise ValueError("Bounded PNG, JPEG or WebP image required")
        image.load()
        image.thumbnail((2048, 2048))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=85)
    return {"type": "image_url", "image_url": {
        "url": "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"), "detail": "auto"}}


def decode_media(data: bytes, mime_type: str) -> tuple[list[dict[str, Any]], bytes | None, str]:
    if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_BYTES:
        raise ValueError("Media must contain 1-20 MiB of bytes")
    if mime_type in {"image/png", "image/jpeg", "image/webp"}:
        return [image_part(data)], None, "image"
    if mime_type not in {"audio/wav", "audio/mpeg", "audio/mp4", "video/mp4"}:
        raise ValueError("Unsupported media type")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ValueError("Media decoder is not installed")
    if mime_type == "audio/wav":
        if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            raise ValueError("WAV container required")
        demuxer = ["-f", "wav"]
    elif mime_type == "audio/mpeg":
        if not (data.startswith(b"ID3") or len(data) > 1 and data[0] == 255 and data[1] & 224 == 224):
            raise ValueError("MP3 container required")
        demuxer = ["-f", "mp3"]
    else:
        if data[4:8] != b"ftyp":
            raise ValueError("MP4 container required")
        demuxer = ["-f", "mov", "-enable_drefs", "0", "-use_absolute_path", "0"]
    import json
    with tempfile.TemporaryDirectory(prefix="gravitre-media-") as directory:
        root = Path(directory)
        source = root / "input.bin"
        source.write_bytes(data)
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries",
            "format=duration:stream=codec_type,width,height", "-of", "json", *demuxer, str(source),
        ], capture_output=True, check=True, timeout=10)
        info = json.loads(probe.stdout)
        duration = float(info.get("format", {}).get("duration", 0))
        if not 0 < duration <= 60:
            raise ValueError("Audio/video duration must be 1-60 seconds")
        streams = info.get("streams", [])
        if len(streams) > 16 or any(stream.get("width", 0) * stream.get("height", 0) > MAX_PIXELS for stream in streams):
            raise ValueError("Media stream dimensions/count exceed bounds")
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
        has_video = any(stream.get("codec_type") == "video" for stream in streams)
        if mime_type == "video/mp4" and not has_video:
            raise ValueError("Video stream required")
        if mime_type.startswith("audio/") and not has_audio:
            raise ValueError("Audio stream required")
        base = ["ffmpeg", "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe", *demuxer, "-threads", "2", "-filter_threads", "1", "-i", str(source)]
        parts = []
        if mime_type == "video/mp4":
            subprocess.run(base + ["-an", "-vf", "fps=1/10:start_time=0:round=up,scale=1024:1024:force_original_aspect_ratio=decrease", "-frames:v", "6",
                                   str(root / "frame-%02d.jpg")], check=True, capture_output=True, timeout=20)
            parts = [image_part(path.read_bytes()) for path in sorted(root.glob("frame-*.jpg"))]
            if not parts:
                raise ValueError("No video frames decoded")
        audio = None
        if has_audio:
            output = root / "audio.wav"
            subprocess.run(base + ["-vn", "-ac", "1", "-ar", "16000", "-t", "60", str(output)],
                           check=True, capture_output=True, timeout=20)
            audio = output.read_bytes()
        return parts, audio, "sampled_video_frames_and_transcript" if mime_type == "video/mp4" else "audio_transcript"
