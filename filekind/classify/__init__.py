from __future__ import annotations

from pathlib import Path

from filekind.classify.cluster import EmbeddingModel, classify_by_embedding, cluster_propagate
from filekind.classify.llm import apply_llm_result, try_load_llm
from filekind.classify.rules import apply_rules, collect_signals, is_classified
from filekind.models import AppConfig, FileRecord
from filekind.prompts import ClassifyPrompts, load_classify_prompts


def classify_records(
    records: list[FileRecord],
    config: AppConfig,
    *,
    config_path: Path | None = None,
    prompts: ClassifyPrompts | None = None,
) -> list[FileRecord]:
    threshold = config.runtime.llm_confidence_threshold

    for record in records:
        collect_signals(record, config)
        apply_rules(record, config)

    unresolved = [
        r
        for r in records
        if not is_classified(r, threshold)
    ]

    embedder: EmbeddingModel | None = None
    try:
        embedder = EmbeddingModel.load(config.models.embedding)
        classify_by_embedding(records, unresolved, config, embedder)
        unresolved = [r for r in records if not is_classified(r, threshold)]
        cluster_propagate(
            records,
            unresolved,
            embedder,
            threshold=config.runtime.cluster_similarity_threshold,
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
        try:
            for record in unresolved:
                try:
                    result = llm.classify_merged(record, config.projects)
                    apply_llm_result(record, result, threshold)
                except Exception:
                    record.project_id = "unclassified"
                    record.project_name = "未分类"
                    record.confidence = 0.0
                    record.classified_by = "llm"
                    record.reason = "LLM 解析失败"
        finally:
            llm.release()

    for record in records:
        if not record.project_id:
            record.project_id = "unclassified"
            record.project_name = "未分类"
            record.confidence = 0.0
            record.classified_by = record.classified_by or "none"
            record.reason = record.reason or "无足够信号"

    return records
