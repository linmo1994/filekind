from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from filekind.models import AppConfig, FileRecord, ProjectDef


@dataclass
class EmbeddingModel:
    model_name: str
    _model: object

    @classmethod
    def load(cls, model_name: str) -> EmbeddingModel:
        from fastembed import TextEmbedding

        return cls(model_name=model_name, _model=TextEmbedding(model_name))

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0))
        vectors = list(self._model.embed(texts))
        return np.array(vectors, dtype=np.float32)

    def release(self) -> None:
        self._model = None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _record_text(record: FileRecord) -> str:
    parts = [record.filename, record.raw_snippet[:2000]]
    if record.summary:
        parts.append(record.summary)
    return "\n".join(p for p in parts if p).strip()


def _project_seed_text(project: ProjectDef) -> str:
    return " ".join(
        [project.name, *project.aliases, *project.codes, project.description]
    ).strip()


def classify_by_embedding(
    records: list[FileRecord],
    unresolved: list[FileRecord],
    config: AppConfig,
    embedder: EmbeddingModel,
) -> None:
    if not unresolved or not config.projects:
        return

    threshold = config.runtime.cluster_similarity_threshold
    project_texts = [_project_seed_text(p) for p in config.projects]
    project_vecs = embedder.embed(project_texts)

    texts = [_record_text(r) for r in unresolved]
    if not any(texts):
        return
    file_vecs = embedder.embed(texts)

    for record, vec in zip(unresolved, file_vecs):
        if not np.any(vec):
            continue
        best_score = 0.0
        best_project: ProjectDef | None = None
        for project, pvec in zip(config.projects, project_vecs):
            score = _cosine(vec, pvec)
            if score > best_score:
                best_score = score
                best_project = project
        if best_project and best_score >= threshold:
            record.project_id = best_project.id
            record.project_name = best_project.name
            record.confidence = round(min(0.92, best_score), 3)
            record.classified_by = "cluster"
            record.matched_by = "content"
            record.reason = f"内容关联度 {best_score:.2f}"


def cluster_propagate(
    records: list[FileRecord],
    unresolved: list[FileRecord],
    embedder: EmbeddingModel,
    *,
    threshold: float,
) -> None:
    """If files are similar and one is classified, propagate to neighbors."""
    if len(unresolved) < 2:
        return

    texts = [_record_text(r) for r in unresolved]
    vecs = embedder.embed(texts)
    classified = [r for r in records if r.project_id and r.project_id != "unclassified"]

    if not classified:
        return

    class_texts = [_record_text(r) for r in classified]
    class_vecs = embedder.embed(class_texts)

    for record, vec in zip(unresolved, vecs):
        if record.project_id:
            continue
        best_score = 0.0
        best_ref: FileRecord | None = None
        for ref, ref_vec in zip(classified, class_vecs):
            score = _cosine(vec, ref_vec)
            if score > best_score:
                best_score = score
                best_ref = ref
        if best_ref and best_score >= threshold:
            record.project_id = best_ref.project_id
            record.project_name = best_ref.project_name
            record.confidence = round(min(0.85, best_score * 0.95), 3)
            record.classified_by = "cluster"
            record.matched_by = "content"
            record.reason = f"与同批已分类文件关联 {best_score:.2f}"
