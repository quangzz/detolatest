"""Trích xuất 9 khung hình quan trọng bằng FFmpeg và ghép lưới Contact Sheet 3x3 đóng dấu [mm:ss]."""

from __future__ import annotations

import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from src.config import SHEETS_CACHE_DIR, ensure_directories
from src.core.security import ensure_within_directory, sanitize_safe_id
from src.models.schemas import TikTokVideoMeta


def _probe_duration_sec(video_path: Path, fallback_sec: float = 30.0) -> float:
    """Lấy thời lượng chính xác của file video bằng ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        val = float((proc.stdout or "").strip())
        return val if val > 1.0 else fallback_sec
    except Exception:
        return fallback_sec


def _compute_strategic_timestamps(duration_sec: float, count: int = 9) -> List[float]:
    """Chọn 9 mốc thời gian chiến lược: Hook đầu (0.5s, 2.5s), thân bài test sản phẩm và CTA cuối."""
    dur = max(4.0, duration_sec)
    if dur <= 8.0:
        step = dur / (count + 1)
        return [round(step * (i + 1), 2) for i in range(count)]

    hook_1 = 0.5
    hook_2 = min(2.5, dur * 0.12)
    cta_last = max(dur * 0.88, dur - 2.0)

    mid_start = hook_2 + (cta_last - hook_2) * 0.12
    mid_end = cta_last - (cta_last - hook_2) * 0.10
    mid_count = count - 3
    if mid_count <= 1:
        mids = [(mid_start + mid_end) / 2.0]
    else:
        step = (mid_end - mid_start) / (mid_count - 1)
        mids = [mid_start + step * idx for idx in range(mid_count)]

    return [round(ts, 2) for ts in ([hook_1, hook_2] + mids + [cta_last])]


def _format_mmss(seconds: float) -> str:
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins:02d}:{secs:02d}"


def build_contact_sheet_3x3(
    handle: str,
    video: TikTokVideoMeta,
    video_file_path: Optional[Path],
    grid_size: int = 1080,
) -> Path:
    """Tạo ảnh JPEG lưới 3x3 (1080x1140) từ file MP4 hoặc tạo Storyboard mô phỏng nếu chạy dry-run/offline."""
    ensure_directories()
    safe_handle = sanitize_safe_id(handle, fallback="creator")
    safe_vid = sanitize_safe_id(video.video_id, fallback="video")
    out_path = ensure_within_directory(
        SHEETS_CACHE_DIR,
        SHEETS_CACHE_DIR / f"{safe_handle}_{safe_vid}_3x3.jpg",
    )
    if out_path.exists() and out_path.stat().st_size > 8_000:
        video.contact_sheet_path = str(out_path)
        return out_path

    header_h = 60
    canvas = Image.new("RGB", (grid_size, grid_size + header_h), color=(15, 23, 42))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    header_text = (
        f"@{handle} | Video ID: {video.video_id} | Views: {video.views:,} | Likes: {video.likes:,}"
    )
    draw.text((16, 20), header_text[:110], fill=(248, 250, 252), font=font)

    duration = (
        _probe_duration_sec(video_file_path, video.duration_sec or 32.0)
        if (video_file_path and video_file_path.exists())
        else (video.duration_sec or 32.0)
    )
    video.duration_sec = duration
    timestamps = _compute_strategic_timestamps(duration, count=9)
    tile_w = grid_size // 3
    tile_h = grid_size // 3

    extracted_frames: List[Optional[Image.Image]] = []
    if video_file_path and video_file_path.exists():
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            for idx, ts in enumerate(timestamps):
                frame_file = tmp_dir_path / f"frame_{idx}.jpg"
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{ts:.2f}",
                    "-i",
                    str(video_file_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "4",
                    str(frame_file),
                ]
                subprocess.run(cmd, capture_output=True, timeout=15, check=False)
                if frame_file.exists():
                    try:
                        with Image.open(frame_file) as im:
                            extracted_frames.append(im.convert("RGB").copy())
                    except Exception:
                        extracted_frames.append(None)
                else:
                    extracted_frames.append(None)
    else:
        extracted_frames = [None] * 9

    stage_labels = [
        "HOOK OPEN",
        "FACE / LIGHTING",
        "PRODUCT HOLD",
        "TEXTURE SWATCH",
        "SKIN APPLY",
        "BLEND & FINISH",
        "TONE / OIL CHECK",
        "CLOSE-UP PROOF",
        "FINAL LOOK & CTA",
    ]

    for idx in range(9):
        row = idx // 3
        col = idx % 3
        x0 = col * tile_w
        y0 = header_h + row * tile_h
        ts_str = _format_mmss(timestamps[idx])
        frame_img = extracted_frames[idx]

        if frame_img is not None:
            # Cắt/thu phóng ảnh vừa khít ô vuông giữ đúng tỷ lệ trung tâm
            src_w, src_h = frame_img.size
            scale = max(tile_w / max(1, src_w), tile_h / max(1, src_h))
            resized = frame_img.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
            left = max(0, (resized.width - tile_w) // 2)
            top = max(0, (resized.height - tile_h) // 2)
            cropped = resized.crop((left, top, left + tile_w, top + tile_h))
            canvas.paste(cropped, (x0, y0))
        else:
            # Vẽ ô Storyboard thông tin khi chạy dry-run hoặc video bị gỡ
            bg_palette = (30 + (idx * 7) % 40, 41 + (idx * 5) % 35, 59 + (idx * 9) % 45)
            draw.rectangle([x0 + 2, y0 + 2, x0 + tile_w - 2, y0 + tile_h - 2], fill=bg_palette)
            snippet = (video.transcript_text or video.description or video.title or "Beauty KOC Video")[
                idx * 22 : (idx + 1) * 22 + 60
            ]
            wrapped = "\n".join(textwrap.wrap(snippet, width=34)[:5])
            draw.text((x0 + 16, y0 + 60), f"[{stage_labels[idx]}]", fill=(110, 231, 183), font=font)
            draw.text((x0 + 16, y0 + 90), wrapped, fill=(226, 232, 240), font=font)

        # Đóng dấu nhãn [Ô số + mốc mm:ss] giúp Vision AI trích dẫn chính xác giây trong bằng chứng
        badge_text = f"#{idx + 1} [{ts_str}] {stage_labels[idx]}"
        draw.rectangle([x0 + 6, y0 + 6, x0 + min(tile_w - 6, 250), y0 + 28], fill=(15, 23, 42))
        draw.text((x0 + 12, y0 + 11), badge_text, fill=(250, 204, 21), font=font)
        draw.rectangle([x0, y0, x0 + tile_w - 1, y0 + tile_h - 1], outline=(51, 65, 85), width=1)

    canvas.save(out_path, format="JPEG", quality=82, optimize=True)
    video.contact_sheet_path = str(out_path)
    return out_path
