"""Quản lý logging theo phiên làm việc (jobs/<job_id>/) tuân thủ Backend Job Logging Rule."""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import JOBS_DIR, ensure_directories
from src.core.security import (
    ensure_within_directory,
    generate_secure_job_id,
    redact_secrets,
    sanitize_safe_id,
)


def _utc_now_iso() -> str:
    """Trả về chuỗi thời gian ISO-8601 hiện tại."""
    return datetime.now(timezone.utc).isoformat()


class JobLogger:
    """Ghi nhận tức thời trạng thái, console log, LLM calls, API calls và kết quả cho mỗi job."""

    def __init__(self, job_id: Optional[str] = None, resume: bool = False) -> None:
        ensure_directories()
        if job_id:
            self.job_id = sanitize_safe_id(job_id, fallback="job")
        else:
            self.job_id = generate_secure_job_id("job")

        self.job_dir: Path = ensure_within_directory(JOBS_DIR, JOBS_DIR / self.job_id)
        self.job_dir.mkdir(parents=True, exist_ok=True)

        self.status_path = self.job_dir / "status.json"
        self.log_path = self.job_dir / "log.txt"
        self.llm_calls_path = self.job_dir / "llm_calls.json"
        self.api_calls_path = self.job_dir / "api_calls.json"
        self.result_path = self.job_dir / "result.json"
        self.checkpoint_db_path = self.job_dir / "checkpoints.db"

        self._lock = threading.Lock()
        self._llm_calls: List[Dict[str, Any]] = []
        self._api_calls: List[Dict[str, Any]] = []
        self._status_data: Dict[str, Any] = {}

        if resume and self.llm_calls_path.exists():
            self._llm_calls = self._read_json_list(self.llm_calls_path)
        else:
            if not self.llm_calls_path.exists():
                self._write_json(self.llm_calls_path, [])

        if resume and self.api_calls_path.exists():
            self._api_calls = self._read_json_list(self.api_calls_path)
        else:
            if not self.api_calls_path.exists():
                self._write_json(self.api_calls_path, [])

        if resume and self.status_path.exists():
            try:
                self._status_data = json.loads(self.status_path.read_text(encoding="utf-8"))
                self._status_data["resumed_count"] = self._status_data.get("resumed_count", 0) + 1
                self._status_data["status"] = "RUNNING"
                self._status_data["updated_at"] = _utc_now_iso()
                self._write_json(self.status_path, self._status_data)
            except Exception:
                self._init_fresh_status()
        else:
            self._init_fresh_status()

        mode_str = "RESUMED" if resume else "INITIALIZED"
        self.info(f"[JOB] {mode_str} job_id={self.job_id} tại {self.job_dir}")

    def _init_fresh_status(self) -> None:
        """Khởi tạo trạng thái ban đầu cho job mới."""
        self._status_data = {
            "job_id": self.job_id,
            "status": "PENDING",
            "current_stage": "init",
            "created_at": _utc_now_iso(),
            "updated_at": _utc_now_iso(),
            "resumed_count": 0,
            "progress": {},
            "metrics_so_far": {
                "llm_calls_count": 0,
                "total_prompt_tokens": 0,
                "total_output_tokens": 0,
                "total_thinking_tokens": 0,
                "total_cached_tokens": 0,
                "total_cost_usd": 0.0,
            },
        }
        self._write_json(self.status_path, self._status_data)

    @staticmethod
    def _read_json_list(path: Path) -> List[Dict[str, Any]]:
        """Đọc danh sách JSON an toàn khi khôi phục phiên chạy."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        """Ghi file JSON theo kiểu atomic tạm thời để tránh hỏng dữ liệu khi ngắt điện/crash."""
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def log(self, level: str, message: str, also_stderr: bool = False) -> None:
        """Append dòng log đã được che khóa bí mật vào log.txt ngay lập tức."""
        safe_msg = redact_secrets(message)
        line = f"[{_utc_now_iso()}] [{level}] {safe_msg}\n"
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
            if also_stderr:
                sys.stderr.write(line)
                sys.stderr.flush()

    def info(self, message: str) -> None:
        """Ghi log mức INFO."""
        self.log("INFO", message)

    def error(self, message: str) -> None:
        """Ghi log mức ERROR đồng thời đẩy ra stderr."""
        self.log("ERROR", message, also_stderr=True)

    def update_status(
        self,
        status: str,
        current_stage: Optional[str] = None,
        progress_patch: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Cập nhật tức thời file status.json."""
        with self._lock:
            self._status_data["status"] = status
            if current_stage is not None:
                self._status_data["current_stage"] = current_stage
            if progress_patch:
                self._status_data.setdefault("progress", {}).update(progress_patch)
            if error_message is not None:
                self._status_data["last_error"] = redact_secrets(error_message)
            self._status_data["updated_at"] = _utc_now_iso()
            self._write_json(self.status_path, self._status_data)

    def log_llm_call(self, record: Dict[str, Any]) -> None:
        """Lưu chi tiết lời gọi LLM vào llm_calls.json (tự động che khóa nhạy cảm) và cộng dồn chỉ số."""
        sanitized_record = dict(record)
        for text_field in ("prompt_preview", "response_preview"):
            if text_field in sanitized_record and isinstance(sanitized_record[text_field], str):
                sanitized_record[text_field] = redact_secrets(sanitized_record[text_field])
        enriched = {"timestamp": _utc_now_iso(), **sanitized_record}
        with self._lock:
            self._llm_calls.append(enriched)
            self._write_json(self.llm_calls_path, self._llm_calls)

            metrics = self._status_data.setdefault("metrics_so_far", {})
            metrics["llm_calls_count"] = len(self._llm_calls)
            metrics["total_prompt_tokens"] = sum(c.get("prompt_tokens", 0) for c in self._llm_calls)
            metrics["total_output_tokens"] = sum(c.get("output_tokens", 0) for c in self._llm_calls)
            metrics["total_thinking_tokens"] = sum(c.get("thinking_tokens", 0) for c in self._llm_calls)
            metrics["total_cached_tokens"] = sum(c.get("cached_tokens", 0) for c in self._llm_calls)
            metrics["total_cost_usd"] = round(
                sum(float(c.get("cost_usd", 0.0)) for c in self._llm_calls), 8
            )
            self._status_data["updated_at"] = _utc_now_iso()
            self._write_json(self.status_path, self._status_data)

    def log_api_call(self, record: Dict[str, Any]) -> None:
        """Lưu chi tiết lời gọi external API / yt-dlp / Kalodata vào api_calls.json."""
        enriched = {"timestamp": _utc_now_iso(), **record}
        with self._lock:
            self._api_calls.append(enriched)
            self._write_json(self.api_calls_path, self._api_calls)

    def write_result(self, result_payload: Dict[str, Any]) -> None:
        """Lưu kết quả cuối cùng vào result.json và đánh dấu SUCCESS."""
        with self._lock:
            self._write_json(self.result_path, result_payload)
        self.update_status(status="SUCCESS", current_stage="completed")
        self.info(f"[JOB] Đã lưu kết quả hoàn chỉnh tại {self.result_path}")

    def get_cost_summary(self) -> Dict[str, Any]:
        """Tổng hợp thống kê token và chi phí theo từng tầng xử lý (stage)."""
        by_stage: Dict[str, Dict[str, Any]] = {}
        for call in self._llm_calls:
            stage = call.get("stage", "unknown")
            bucket = by_stage.setdefault(
                stage,
                {
                    "calls": 0,
                    "prompt_tokens": 0,
                    "output_tokens": 0,
                    "thinking_tokens": 0,
                    "cached_tokens": 0,
                    "cost_usd": 0.0,
                    "latency_ms": 0.0,
                },
            )
            bucket["calls"] += 1
            bucket["prompt_tokens"] += int(call.get("prompt_tokens", 0))
            bucket["output_tokens"] += int(call.get("output_tokens", 0))
            bucket["thinking_tokens"] += int(call.get("thinking_tokens", 0))
            bucket["cached_tokens"] += int(call.get("cached_tokens", 0))
            bucket["cost_usd"] = round(bucket["cost_usd"] + float(call.get("cost_usd", 0.0)), 8)
            bucket["latency_ms"] = round(bucket["latency_ms"] + float(call.get("latency_ms", 0.0)), 2)

        return {
            "total_calls": len(self._llm_calls),
            "total_prompt_tokens": sum(c.get("prompt_tokens", 0) for c in self._llm_calls),
            "total_output_tokens": sum(c.get("output_tokens", 0) for c in self._llm_calls),
            "total_thinking_tokens": sum(c.get("thinking_tokens", 0) for c in self._llm_calls),
            "total_cached_tokens": sum(c.get("cached_tokens", 0) for c in self._llm_calls),
            "total_cost_usd": round(sum(float(c.get("cost_usd", 0.0)) for c in self._llm_calls), 8),
            "by_stage": by_stage,
        }
