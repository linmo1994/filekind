from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from filekind.models import AppConfig, FileRecord, ProjectDef
from filekind.prompts import ClassifyPrompts, default_classify_prompts, load_classify_prompts


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
        candidates = [
            {
                "project_id": p.id,
                "project_name": p.name,
                "aliases": p.aliases,
                "codes": p.codes,
            }
            for p in projects
        ] + [
            {
                "project_id": "unclassified",
                "project_name": "未分类",
                "aliases": [],
                "codes": [],
            }
        ]
        system = self.prompts.merged_system.format(summary_max_chars=self.summary_max_chars)
        user = self.prompts.merged_user.format(
            filename=record.filename,
            parent_path=record.parent_path,
            detected_codes=record.detected_codes or "无",
            detected_names=record.detected_names or "无",
            candidate_projects_json=json.dumps(candidates, ensure_ascii=False),
            page_count=record.pages_extracted or "0",
            raw_snippet=record.raw_snippet[:6000] or "无文本",
        )
        response = self._llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=512,
        )
        content = response["choices"][0]["message"]["content"]
        return _parse_json(content)


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


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


def try_load_llm(
    config: AppConfig,
    *,
    config_path: Path | None = None,
    prompts: ClassifyPrompts | None = None,
) -> LocalLLM | None:
    path_str = (config.models.llm_gguf or "").strip()
    if not path_str:
        return None
    path = Path(path_str).expanduser()
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
