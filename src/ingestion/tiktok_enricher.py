"""Làm giàu thông tin KOC từ TikTok công khai bằng yt-dlp (metadata video, phụ đề 0-token & tải MP4 nhẹ)."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yt_dlp

from src.config import SUBS_CACHE_DIR, VIDEOS_CACHE_DIR, ensure_directories
from src.core.checkpoint import GlobalEntityCache
from src.core.job_logger import JobLogger
from src.core.security import (
    ensure_within_directory,
    sanitize_safe_id,
    validate_safe_tiktok_url,
)
from src.models.schemas import KocCandidate, TikTokVideoMeta


def parse_vtt_to_compact_transcript(vtt_content: str, max_chars: int = 1800) -> str:
    """Nén file phụ đề .vtt/.srt của TikTok thành chuỗi văn bản gắn mốc [mm:ss] tiết kiệm token."""
    lines = vtt_content.splitlines()
    segments: List[str] = []
    current_ts = ""
    seen_texts = set()

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("WEBVTT") or line.isdigit():
            continue
        # Bắt dòng thời gian dạng 00:00:03.120 --> 00:00:06.000 hoặc 00:03.120 --> ...
        ts_match = re.match(r"(?:(\d{2}):)?(\d{2}):(\d{2})\.\d+\s*-->", line)
        if ts_match:
            mins = int(ts_match.group(2)) + (int(ts_match.group(1) or 0) * 60)
            secs = int(ts_match.group(3))
            current_ts = f"[{mins:02d}:{secs:02d}]"
            continue

        clean_text = re.sub(r"<[^>]+>", "", line).strip()
        if clean_text and clean_text.lower() not in seen_texts:
            seen_texts.add(clean_text.lower())
            prefix = f"{current_ts} " if current_ts else ""
            segments.append(f"{prefix}{clean_text}")

    joined = " | ".join(segments)
    return joined[:max_chars]


class TikTokEnricher:
    """Thu thập danh sách video tiêu biểu, phụ đề có sẵn và file MP4 nhẹ qua yt-dlp."""

    def __init__(
        self,
        job_logger: JobLogger,
        global_cache: GlobalEntityCache,
        dry_run: bool = False,
    ) -> None:
        ensure_directories()
        self.job_logger = job_logger
        self.global_cache = global_cache
        self.dry_run = dry_run

    def enrich_candidate_videos(
        self,
        candidate: KocCandidate,
        max_recent_videos: int = 6,
    ) -> KocCandidate:
        """Lấy danh sách video gần đây trên kênh TikTok nếu hồ sơ Kalodata chưa có sẵn link video."""
        if candidate.recent_videos or self.dry_run:
            return candidate

        cached = self.global_cache.get("tiktok_profile_videos", candidate.handle)
        if cached:
            candidate.recent_videos = [TikTokVideoMeta.model_validate(v) for v in cached]
            return candidate

        safe_handle = sanitize_safe_id(candidate.handle, fallback="creator")
        profile_url = validate_safe_tiktok_url(
            f"https://www.tiktok.com/@{safe_handle}",
            resolve_dns=True,
        )
        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "playlistend": max_recent_videos,
            "socket_timeout": 15,
            "ignoreerrors": True,
        }

        start = time.perf_counter()
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(profile_url, download=False)
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)

            entries = (info or {}).get("entries") or []
            videos: List[TikTokVideoMeta] = []
            for entry in entries:
                if not entry or not isinstance(entry, dict):
                    continue
                vid = str(entry.get("id") or "")
                webpage_url = str(entry.get("webpage_url") or entry.get("url") or "")
                if not vid or not webpage_url:
                    continue
                desc = str(entry.get("description") or entry.get("title") or "").strip()
                hashtags = re.findall(r"#([\wÀ-ỹ]+)", desc)
                videos.append(
                    TikTokVideoMeta(
                        video_id=vid,
                        url=webpage_url,
                        title=str(entry.get("title") or desc[:80]),
                        description=desc,
                        duration_sec=float(entry.get("duration") or 0.0),
                        views=int(entry.get("view_count") or 0),
                        likes=int(entry.get("like_count") or 0),
                        comments=int(entry.get("comment_count") or 0),
                        shares=int(entry.get("repost_count") or 0),
                        published_at=str(entry.get("upload_date") or ""),
                        hashtags=hashtags[:10],
                    )
                )

            if videos:
                candidate.recent_videos = videos
                if candidate.avg_video_views == 0:
                    candidate.avg_video_views = int(sum(v.views for v in videos) / len(videos))
                self.global_cache.set(
                    "tiktok_profile_videos",
                    candidate.handle,
                    [v.model_dump() for v in videos],
                )

            self.job_logger.log_api_call(
                {
                    "provider": "tiktok_ytdlp_profile",
                    "target": profile_url,
                    "status": "ok",
                    "videos_found": len(videos),
                    "latency_ms": elapsed_ms,
                }
            )
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
            self.job_logger.log_api_call(
                {
                    "provider": "tiktok_ytdlp_profile",
                    "target": profile_url,
                    "status": "error",
                    "error": str(exc)[:300],
                    "latency_ms": elapsed_ms,
                }
            )
            self.job_logger.info(f"[WARN] Không lấy được danh sách video live cho @{candidate.handle}: {exc}")

        return candidate

    def select_best_videos_for_analysis(
        self,
        candidate: KocCandidate,
        keywords: List[str],
        limit: int = 2,
    ) -> List[TikTokVideoMeta]:
        """Ưu tiên chọn các video có từ khóa kem chống nắng/skincare và lượt xem tốt nhất."""
        if not candidate.recent_videos:
            return []

        lower_kws = [k.lower() for k in keywords]

        def _priority_key(v: TikTokVideoMeta) -> tuple[int, int]:
            haystack = f"{v.title} {v.description} {' '.join(v.hashtags)}".lower()
            kw_hits = sum(1 for kw in lower_kws if kw in haystack)
            return (kw_hits, v.views)

        ranked = sorted(candidate.recent_videos, key=_priority_key, reverse=True)
        return ranked[:limit]

    def download_video_and_subtitles(
        self,
        video: TikTokVideoMeta,
    ) -> Optional[Path]:
        """Tải MP4 độ phân giải vừa đủ (<=576p/720p) và phụ đề có sẵn của TikTok (có chặn SSRF & Path Traversal)."""
        safe_vid = sanitize_safe_id(video.video_id, fallback="video")
        safe_video_url = validate_safe_tiktok_url(video.url, resolve_dns=not self.dry_run)

        mp4_path = ensure_within_directory(VIDEOS_CACHE_DIR, VIDEOS_CACHE_DIR / f"{safe_vid}.mp4")
        cached_sub_path = ensure_within_directory(SUBS_CACHE_DIR, SUBS_CACHE_DIR / f"{safe_vid}.txt")

        if cached_sub_path.exists() and not video.transcript_text:
            video.transcript_text = cached_sub_path.read_text(encoding="utf-8")
            video.transcript_source = "tiktok_cc_cached"

        if self.dry_run:
            if not video.transcript_text:
                video.transcript_text = video.description or video.title
                video.transcript_source = "caption_fallback"
            return mp4_path if mp4_path.exists() else None

        if mp4_path.exists() and mp4_path.stat().st_size > 10_000:
            return mp4_path

        ydl_opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "format": "best[ext=mp4][height<=720]/best[ext=mp4]/mp4/best",
            "outtmpl": str(VIDEOS_CACHE_DIR / f"{safe_vid}.%(ext)s"),
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["vi.*", "vi", "en.*"],
            "socket_timeout": 20,
        }

        start = time.perf_counter()
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(safe_video_url, download=True)
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)

            # Tìm file phụ đề vừa tải về (nếu có) và trích xuất văn bản 0-token
            vtt_candidates = list(VIDEOS_CACHE_DIR.glob(f"{safe_vid}*.vtt")) + list(
                VIDEOS_CACHE_DIR.glob(f"{safe_vid}*.srt")
            )
            if vtt_candidates:
                raw_sub = vtt_candidates[0].read_text(encoding="utf-8", errors="ignore")
                parsed_sub = parse_vtt_to_compact_transcript(raw_sub)
                if parsed_sub:
                    video.transcript_text = parsed_sub
                    video.transcript_source = "tiktok_cc"
                    cached_sub_path.write_text(parsed_sub, encoding="utf-8")
                for sub_f in vtt_candidates:
                    sub_f.unlink(missing_ok=True)

            if not video.transcript_text:
                video.transcript_text = video.description or video.title
                video.transcript_source = "caption_fallback"

            # Tìm file video đã tải
            downloaded_files = [
                p
                for p in VIDEOS_CACHE_DIR.glob(f"{safe_vid}.*")
                if p.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}
            ]
            final_video_path = downloaded_files[0] if downloaded_files else None

            self.job_logger.log_api_call(
                {
                    "provider": "tiktok_ytdlp_video",
                    "video_id": video.video_id,
                    "target": video.url,
                    "status": "ok" if final_video_path else "missing_file",
                    "transcript_source": video.transcript_source,
                    "latency_ms": elapsed_ms,
                }
            )
            return final_video_path
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
            if not video.transcript_text:
                video.transcript_text = video.description or video.title
                video.transcript_source = "caption_fallback"
            self.job_logger.log_api_call(
                {
                    "provider": "tiktok_ytdlp_video",
                    "video_id": video.video_id,
                    "target": video.url,
                    "status": "error",
                    "error": str(exc)[:300],
                    "latency_ms": elapsed_ms,
                }
            )
            self.job_logger.info(f"[WARN] Không tải được file MP4 {video.video_id}, chuyển sang fallback storyboard: {exc}")
            return None
