from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from filekind.models import AppConfig, FileRecord, ProjectDef
from filekind.prompts import ClassifyPrompts, default_classify_prompts, format_classify_user, load_classify_prompts


@dataclass
class LocalLLM:
    model_path: Path
    _llm: object
    summary_max_chars: int
    prompts: ClassifyPrompts

    @classmethod
    def load(
        cls,
        model_path: Path,
        *,
        summary_max_chars: int = 300,
        prompts: ClassifyPrompts | None = None,
    ) -> LocalLLM:
        from llama_cpp import Llama

        llm = Llama(
            model_path=str(model_path),
            n_ctx=4096,
            n_threads=0,
            verbose=False,
        )
        return cls(
            model_path=model_path,
            _llm=llm,
            summary_max_chars=summary_max_chars,
            prompts=prompts or default_classify_prompts(),
        )

    def release(self) -> None:
        self._llm = None

    def classify_merged(
        self,
        record: FileRecord,
        projects: list[ProjectDef],
    ) -> dict:
        candidates = _compact_candidates(projects)
        system = self.prompts.merged_system.format(summary_max_chars=self.summary_max_chars)
        user = format_classify_user(
            self.prompts.merged_user,
            {
                "filename": record.filename,
                "parent_path": record.parent_path,
                "detected_codes": ", ".join(record.detected_codes) if record.detected_codes else "无",
                "detected_names": ", ".join(record.detected_names) if record.detected_names else "无",
                "platform_prefixes": ", ".join(record.platform_prefixes)
                if record.platform_prefixes
                else "无",
                "candidate_projects_json": json.dumps(candidates, ensure_ascii=False),
                "page_count": str(record.pages_extracted or "0"),
                "raw_snippet": record.raw_snippet[:4000] or "无文本",
            },
        )
        response = self._llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=384,
        )
        content = response["choices"][0]["message"]["content"]
        return _parse_json(content)


def _compact_candidates(projects: list[ProjectDef]) -> list[dict]:
    rows: list[dict] = []
    for project in projects:
        row: dict = {
            "project_id": project.id,
            "project_name": project.name,
        }
        inv = project.inventory_code or (
            project.codes[0] if project.codes and _INVENTORY_SERIAL.match(project.codes[0]) else ""
        )
        if inv:
            row["inventory_code"] = inv
        elif project.codes:
            row["codes"] = project.codes[:4]
        if project.solution_name:
            row["solution_name"] = project.solution_name
        if project.board_type:
            row["board_type"] = project.board_type
        if project.year:
            row["year"] = project.year
        if project.aliases:
            row["aliases"] = project.aliases[:3]
        rows.append(row)
    rows.append({"project_id": "unclassified", "project_name": "未分类"})
    return rows


_INVENTORY_SERIAL = re.compile(r"(?i)^20\d{4}$")


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json(text: str) -> dict:
    text = _strip_code_fences(text)
    attempts = [text]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        attempts.append(match.group(0))

    for candidate in attempts:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    return _parse_json_fallback(text)


def _parse_json_fallback(text: str) -> dict:
    """Best-effort extraction when the model returns malformed JSON."""
    project_id = _regex_field(text, "project_id") or "unclassified"
    project_name = _regex_field(text, "project_name") or (
        "未分类" if project_id == "unclassified" else project_id
    )
    confidence_raw = _regex_field(text, "confidence")
    try:
        confidence = float(confidence_raw) if confidence_raw else 0.0
    except ValueError:
        confidence = 0.0
    summary = _regex_field(text, "summary") or ""
    matched_by = _regex_field(text, "matched_by") or "content"
    reason = _regex_field(text, "reason") or "LLM 输出格式不完整，已尽力解析"

    if project_id != "unclassified" and confidence <= 0:
        confidence = 0.7

    return {
        "project_id": project_id,
        "project_name": project_name,
        "confidence": confidence,
        "summary": summary,
        "matched_by": matched_by,
        "reason": reason,
    }


def _regex_field(text: str, key: str) -> str | None:
    match = re.search(
        rf'"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\])*)"',
        text,
        re.DOTALL,
    )
    if match:
        return match.group(1).replace('\\"', '"')
    match = re.search(rf'"{re.escape(key)}"\s*:\s*([^,}}\s]+)', text)
    if match:
        return match.group(1).strip().strip('"')
    return None


def apply_llm_result(record: FileRecord, result: dict, threshold: float) -> FileRecord:
    project_id = str(result.get("project_id") or "unclassified")
    confidence = float(result.get("confidence") or 0.0)
    summary = str(result.get("summary") or "").strip()
    if summary:
        record.summary = summary[:500]

    if project_id == "unclassified" or confidence < threshold:
        record.project_id = "unclassified"
        record.project_name = "未分类"
        record.confidence = confidence
        record.classified_by = "llm"
        record.matched_by = str(result.get("matched_by") or "content")
        record.reason = str(result.get("reason") or "置信度不足")
        return record

    record.project_id = project_id
    record.project_name = str(result.get("project_name") or project_id)
    record.confidence = confidence
    record.classified_by = "llm"
    record.matched_by = str(result.get("matched_by") or "mixed")
    record.reason = str(result.get("reason") or "LLM 分类")
    return record


def _resolve_llm_path(path_str: str, config_path: Path | None) -> Path:
    path = Path(path_str).expanduser()
    if path.is_file():
        return path.resolve()
    if not path.is_absolute() and config_path is not None:
        beside_config = config_path.resolve().parent / path
        if beside_config.is_file():
            return beside_config.resolve()
    return path


def try_load_llm(
    config: AppConfig,
    *,
    config_path: Path | None = None,
    prompts: ClassifyPrompts | None = None,
) -> LocalLLM | None:
    path_str = (config.models.llm_gguf or "").strip()
    if not path_str:
        return None
    path = _resolve_llm_path(path_str, config_path)
    if not path.is_file():
        return None
    if prompts is None and config_path is not None:
        prompts = load_classify_prompts(config_path, config)
    try:
        return LocalLLM.load(
            path,
            summary_max_chars=config.runtime.summary_max_chars,
            prompts=prompts,
        )
    except Exception:
        return None
