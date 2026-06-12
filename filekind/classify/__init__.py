from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from filekind.classify.cluster import EmbeddingModel, classify_by_embedding, cluster_propagate
from filekind.classify.llm import apply_llm_result, try_load_llm
from filekind.classify.report import emit_stage_summary, format_llm_result_line
from filekind.classify.candidates import narrow_candidates
from filekind.classify.rules import apply_narrow_rule, apply_rules, collect_signals, is_classified
from filekind.models import AppConfig, FileRecord
from filekind.prompts import ClassifyPrompts, load_classify_prompts

ProgressFn = Callable[[str], None]


def classify_records(
    records: list[FileRecord],
    config: AppConfig,
    *,
    config_path: Path | None = None,
    prompts: ClassifyPrompts | None = None,
    on_progress: ProgressFn | None = None,
) -> list[FileRecord]:
    def say(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    threshold = config.runtime.llm_confidence_threshold
    classified_so_far = 0

    for record in records:
        collect_signals(record, config)
        apply_rules(record, config)
        apply_narrow_rule(record, config)

    unresolved = [r for r in records if not is_classified(r, threshold)]
    classified_so_far = emit_stage_summary(
        say,
        "规则与代号匹配",
        records,
        threshold,
        previous_classified=classified_so_far,
    )

    embedder: EmbeddingModel | None = None
    try:
        say("  加载向量模型…")
        embedder = EmbeddingModel.load(config.models.embedding)
        classify_by_embedding(records, unresolved, config, embedder)
        unresolved = [r for r in records if not is_classified(r, threshold)]
        cluster_propagate(
            records,
            unresolved,
            embedder,
            threshold=config.runtime.cluster_similarity_threshold,
        )
        classified_so_far = emit_stage_summary(
            say,
            "向量关联",
            records,
            threshold,
            previous_classified=classified_so_far,
        )
    except Exception:
        pass
    finally:
        if embedder is not None:
            embedder.release()
        embedder = None

    if prompts is None and config_path is not None:
        prompts = load_classify_prompts(config_path, config)

    unresolved = [r for r in records if not is_classified(r, threshold)]
    llm = try_load_llm(config, config_path=config_path, prompts=prompts)
    if llm is not None:
        total = len(unresolved)
        if total:
            say(f"  LLM 分类 {total} 个文件…")
            say("  LLM 分类结果:")
        llm_classified = 0
        candidate_limit = config.runtime.llm_max_candidates
        try:
            for index, record in enumerate(unresolved):
                try:
                    candidates = narrow_candidates(
                        record,
                        config.projects,
                        limit=candidate_limit,
                    )
                    result = llm.classify_merged(record, candidates)
                    apply_llm_result(record, result, threshold)
                except Exception:
                    record.project_id = "unclassified"
                    record.project_name = "未分类"
                    record.confidence = 0.0
                    record.classified_by = "llm"
                    record.reason = "LLM 解析失败"
                if is_classified(record, threshold):
                    llm_classified += 1
                say(f"    {format_llm_result_line(record, threshold)}")
                done = index + 1
                if total and done != total and done % max(1, total // 10) == 0:
                    say(f"    … LLM 进度 {done}/{total}")
        finally:
            llm.release()
        if total:
            say(
                f"  LLM 小结: 处理 {total} 个，"
                f"归入项目 {llm_classified} 个，"
                f"仍未分类 {total - llm_classified} 个"
            )
        classified_so_far = emit_stage_summary(
            say,
            "LLM 分类后",
            records,
            threshold,
            previous_classified=classified_so_far,
        )
    elif unresolved:
        say("  未配置 LLM，跳过 LLM 分类")

    for record in records:
        if not record.project_id:
            record.project_id = "unclassified"
            record.project_name = "未分类"
            record.confidence = 0.0
            record.classified_by = record.classified_by or "none"
            record.reason = record.reason or "无足够信号"

    return records
