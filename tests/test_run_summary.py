from filekind.run_summary import compute_run_summary, format_run_summary_lines


def test_compute_run_summary_with_unmatched_projects() -> None:
    meta = {
        "inventory_project_count": 4,
        "inventory_projects": [
            {"id": "p1", "name": "项目甲"},
            {"id": "p2", "name": "项目乙"},
            {"id": "p3", "name": "项目丙"},
            {"id": "p4", "name": "项目丁"},
        ],
        "file_count": 5,
        "project_stats": [
            {"project_id": "p1", "project_name": "项目甲", "file_count": 2},
            {"project_id": "p2", "project_name": "项目乙", "file_count": 1},
            {"project_id": "unclassified", "project_name": "未分类", "file_count": 2},
        ],
    }
    summary = compute_run_summary(meta)
    assert summary["inventory_count"] == 4
    assert summary["classified_project_count"] == 2
    assert summary["total_files"] == 5
    assert summary["classified_files"] == 3
    assert summary["unclassified_files"] == 2
    assert summary["unmatched_projects"] == ["项目丙", "项目丁"]

    text = "\n".join(format_run_summary_lines(meta))
    assert "项目清单中共有 4 个项目" in text
    assert "已识别并归类到 2 个项目" in text
    assert "共处理 5 个文件" in text
    assert "其中 3 个已归入项目" in text
    assert "项目丙" in text
    assert "项目丁" in text


def test_format_run_summary_empty_when_no_stats() -> None:
    assert format_run_summary_lines({}) == []
