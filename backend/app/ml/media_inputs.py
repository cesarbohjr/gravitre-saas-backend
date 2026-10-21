"""Bounded local media decoding. Never fetch caller-supplied URLs.

Images are re-encoded to remove metadata. Video analysis uses sampled frames,
not a claim to exhaustive temporal understanding. Audio uses the existing STT.
"""
from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 16_000_000


def reencode_image(data: bytes, *, output_format: str, expected_size: tuple[int,int] | None = None) -> bytes:
    """Allowlisted bounded raster decode, using the same installed media codec.

    No Pillow dependency or voice-library version change. Re-encoding drops
    metadata; only one raster frame is accepted for this image operation.
    """
    import json
    if not isinstance(data,bytes) or not 1 <= len(data) <= MAX_BYTES:
        raise ValueError('Media must contain 1-20 MiB of bytes')
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        demuxer = 'png_pipe'
    elif data.startswith(b'\xff\xd8\xff'):
        demuxer = 'jpeg_pipe'
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        demuxer = 'webp_pipe'
    else:
        raise ValueError('PNG, JPEG or WebP container required')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise ValueError('Media decoder is not installed')
    with tempfile.TemporaryDirectory(prefix='gravitre-image-') as directory:
        source = Path(directory)/'input.bin'
        source.write_bytes(data)
        info = subprocess.run(['ffprobe','-v','error','-max_alloc','67108864','-f',demuxer,
            '-protocol_whitelist','file,pipe','-show_entries','stream=width,height','-of','json',str(source)],
            capture_output=True,check=True,timeout=10)
        streams = json.loads(info.stdout).get('streams',[])
        if len(streams) != 1:
            raise ValueError('Exactly one raster stream required')
        width,height = streams[0].get('width',0),streams[0].get('height',0)
        if not width or not height or width*height > MAX_PIXELS:
            raise ValueError('Image dimensions exceed pixel bounds')
        if expected_size and (width,height) != expected_size:
            raise ValueError('Generated image does not match requested dimensions')
        if output_format not in {'jpeg','png'}:
            raise ValueError('Unsupported image output format')
        command = ['ffmpeg','-nostdin','-v','error','-max_alloc','67108864','-threads','2',
            '-filter_threads','1','-f',demuxer,'-protocol_whitelist','file,pipe','-max_pixels',str(MAX_PIXELS),
            '-i',str(source),'-map_metadata','-1','-an','-frames:v','1']
        if output_format == 'jpeg':
            command += ['-vf',"scale='min(2048,iw)':'min(2048,ih)':force_original_aspect_ratio=decrease,sidedata=mode=delete",
                        '-c:v','mjpeg','-q:v','3']
        else:
            command += ['-vf','sidedata=mode=delete','-c:v','png']
        result = subprocess.run(command+['-f','image2pipe','pipe:1'],capture_output=True,check=True,timeout=20)
        if not 1 <= len(result.stdout) <= MAX_BYTES:
            raise ValueError('Decoded image exceeds output bounds')
        return result.stdout


def image_part(data: bytes) -> dict[str, Any]:
    encoded = reencode_image(data,output_format='jpeg')
    return {"type": "image_url", "image_url": {
        "url": "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii"), "detail": "auto"}}


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
            subprocess.run(base + ["-an", "-vf", "fps=1/10:start_time=0:round=up,scale=1024:1024:force_original_aspect_ratio=decrease,sidedata=mode=delete", "-frames:v", "6",
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
