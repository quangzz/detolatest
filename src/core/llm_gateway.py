"""Cổng kết nối Gemini API hỗ trợ Structured Output, kiểm soát thinking_budget, đo token/cost và Dry-Run."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, List, Optional, Type, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import Settings, calculate_call_cost_usd
from src.core.job_logger import JobLogger
from src.core.security import SecurityViolationError

T = TypeVar("T", bound=BaseModel)


# Tự động ánh xạ các model 2.5 đã ngừng cấp cho khóa Google AI Studio mới sang dòng 3.5 ổn định
_DEPRECATED_MODEL_MIGRATION = {
    "gemini-2.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-2.5-flash": "gemini-3.5-flash-lite",
}


class GeminiGateway:
    """Wrapper tập trung gọi Gemini API với quản lý chi phí, timeout 45s, retry và mô phỏng dry-run."""

    def __init__(
        self,
        settings: Settings,
        job_logger: JobLogger,
        dry_run: bool = False,
    ) -> None:
        self.settings = settings
        self.job_logger = job_logger
        self.dry_run = dry_run
        self._client: Optional[genai.Client] = None

        if not self.dry_run:
            api_key = (self.settings.gemini_api_key or "").strip()
            if not api_key or api_key == "your_gemini_api_key_here":
                raise ValueError(
                    "Chưa cấu hình GEMINI_API_KEY trong file .env (hoặc thêm cờ --dry-run để kiểm thử luồng offline)."
                )
            # Chỉ bật Vertex AI mode khi cấu hình GEMINI_USE_VERTEXAI=true (mặc định dùng Gemini Developer API chuẩn cho cả khóa AIza và AQ.)
            use_vertex = bool(self.settings.gemini_use_vertexai)
            self.provider_mode = "vertexai" if use_vertex else "gemini_api"
            self._client = genai.Client(
                vertexai=True if use_vertex else None,
                api_key=api_key,
                http_options=types.HttpOptions(timeout=self.settings.llm_timeout_ms),
            )
        else:
            self.provider_mode = "dry_run"

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1.2, min=1.5, max=15),
        retry=retry_if_exception_type(Exception),
    )
    def _invoke_gemini(
        self,
        model_name: str,
        contents: List[Any],
        config: types.GenerateContentConfig,
    ) -> Any:
        """Thực thi lời gọi tới Google Gemini kèm tự động thử lại khi gặp lỗi mạng/rate limit."""
        assert self._client is not None
        return self._client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

    def generate_structured(
        self,
        *,
        stage: str,
        purpose: str,
        model_name: str,
        system_instruction: str,
        user_prompt: str,
        response_schema: Type[T],
        image_paths: Optional[List[Path]] = None,
        thinking_budget: int = 0,
        max_output_tokens: int = 2048,
        temperature: float = 0.15,
        mock_builder: Optional[Callable[[], T]] = None,
    ) -> T:
        """Gọi Gemini trả về đối tượng Pydantic chuẩn hóa, kiểm tra trần ngân sách (DoW) và ghi token/cost."""
        spent_usd = float(self.job_logger.get_cost_summary().get("total_cost_usd", 0.0))
        if spent_usd >= self.settings.max_job_cost_usd:
            raise SecurityViolationError(
                f"Đã chạm cầu chì bảo vệ ngân sách phiên chạy (${spent_usd:.4f} >= ${self.settings.max_job_cost_usd:.4f}) theo chuẩn LLM04:2025."
            )

        start_time = time.perf_counter()

        # Chế độ Dry-Run: mô phỏng số token sát thực tế để kiểm thử toàn trình & crash recovery không tốn tiền
        if self.dry_run:
            if mock_builder is None:
                raise RuntimeError(f"Thiếu mock_builder cho stage={stage} khi chạy chế độ --dry-run")
            parsed_obj = mock_builder()
            est_img_tokens = (len(image_paths) * 520) if image_paths else 0
            est_prompt_tokens = max(80, (len(system_instruction) + len(user_prompt)) // 4) + est_img_tokens
            serialized_resp = parsed_obj.model_dump_json()
            est_output_tokens = max(40, len(serialized_resp) // 4)
            est_thinking_tokens = min(thinking_budget, 320) if thinking_budget > 0 else 0
            cost_usd = calculate_call_cost_usd(
                model_name=model_name,
                prompt_tokens=est_prompt_tokens,
                cached_tokens=0,
                output_tokens=est_output_tokens,
                thinking_tokens=est_thinking_tokens,
            )
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            self.job_logger.log_llm_call(
                {
                    "mode": "dry_run_simulated",
                    "stage": stage,
                    "purpose": purpose,
                    "model": model_name,
                    "thinking_budget": thinking_budget,
                    "images_attached": len(image_paths or []),
                    "prompt_tokens": est_prompt_tokens,
                    "cached_tokens": 0,
                    "output_tokens": est_output_tokens,
                    "thinking_tokens": est_thinking_tokens,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                    "prompt_preview": user_prompt[:500],
                    "response_preview": serialized_resp[:500],
                }
            )
            return parsed_obj

        # Ghép danh sách multimodal contents (ảnh JPEG Contact Sheet + văn bản prompt)
        contents: List[Any] = []
        valid_images = 0
        if image_paths:
            for img_path in image_paths:
                if img_path and img_path.exists():
                    img_bytes = img_path.read_bytes()
                    contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"))
                    valid_images += 1
        contents.append(user_prompt)

        effective_model = _DEPRECATED_MODEL_MIGRATION.get(model_name, model_name)
        if effective_model != model_name:
            self.job_logger.info(
                f"[LLM] Tự động nâng cấp model cũ `{model_name}` -> `{effective_model}` cho tương thích khóa API mới."
            )

        config_kwargs: dict[str, Any] = {
            "system_instruction": system_instruction,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "response_mime_type": "application/json",
            "response_schema": response_schema,
        }
        # Chỉ gửi ThinkingConfig khi thinking_budget > 0 (dòng gemini-3.5-flash-lite không nhận thinking_budget=0)
        if thinking_budget > 0:
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)

        gen_config = types.GenerateContentConfig(**config_kwargs)

        response = self._invoke_gemini(
            model_name=effective_model,
            contents=contents,
            config=gen_config,
        )
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        cached_tokens = int(getattr(usage, "cached_content_token_count", 0) or 0) if usage else 0
        thinking_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0) if usage else 0
        output_tokens = int(
            (
                getattr(usage, "candidates_token_count", None)
                or getattr(usage, "response_token_count", None)
                or 0
            )
        ) if usage else 0
        if output_tokens == 0 and usage is not None:
            total_t = int(getattr(usage, "total_token_count", 0) or 0)
            if total_t > prompt_tokens:
                output_tokens = max(0, total_t - prompt_tokens - thinking_tokens)

        cost_usd = calculate_call_cost_usd(
            model_name=effective_model,
            prompt_tokens=prompt_tokens,
            cached_tokens=cached_tokens,
            output_tokens=output_tokens,
            thinking_tokens=thinking_tokens,
        )

        raw_text = response.text or "{}"
        parsed_result: Optional[T] = getattr(response, "parsed", None)
        if parsed_result is None or not isinstance(parsed_result, response_schema):
            parsed_result = response_schema.model_validate_json(raw_text)

        self.job_logger.log_llm_call(
            {
                "mode": "live",
                "stage": stage,
                "purpose": purpose,
                "model": effective_model,
                "thinking_budget": thinking_budget,
                "images_attached": valid_images,
                "prompt_tokens": prompt_tokens,
                "cached_tokens": cached_tokens,
                "output_tokens": output_tokens,
                "thinking_tokens": thinking_tokens,
                "cost_usd": cost_usd,
                "latency_ms": latency_ms,
                "prompt_preview": user_prompt[:600],
                "response_preview": raw_text[:600],
            }
        )
        return parsed_result
