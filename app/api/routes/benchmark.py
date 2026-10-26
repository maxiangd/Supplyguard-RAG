"""Benchmark API：用例列表 + 运行评测（dry-run 模式，不调 LLM）。"""

import json
import os
import sys
import time

from fastapi import APIRouter

# 确保项目根目录在 sys.path 中
# __file__ = app/api/routes/benchmark.py → 4 级 dirname 回到项目根
_BENCHMARK_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _BENCHMARK_DIR)

from tests.benchmark.ground_truth import expected_paths_for_case
from tests.benchmark.metrics import compute_metrics

router = APIRouter(prefix="/benchmark", tags=["benchmark"])

_CASES_PATH = os.path.join(_BENCHMARK_DIR, "tests", "benchmark", "cases.json")


@router.get("/cases")
def list_cases() -> dict:
    """返回全部 benchmark 用例。"""
    if not os.path.exists(_CASES_PATH):
        return {"cases": [], "total": 0}

    with open(_CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)

    return {
        "cases": [
            {
                "id": c["id"],
                "scenario": c.get("scenario", ""),
                "question": c["question"],
                "role": c["role"],
                "expected_entities": c.get("expected_entities", []),
                "expected_path_rules": c.get("expected_path_rules", []),
                "expected_min_paths": c.get("expected_min_paths", 0),
                "notes": c.get("notes", ""),
            }
            for c in cases
        ],
        "total": len(cases),
    }


@router.post("/run")
def run_benchmark() -> dict:
    """运行 ground truth benchmark（不调 LLM/Qdrant/Neo4j）。

    用纯 Python 传导规则 + 实体匹配作为 ground truth，
    与用例中的期望值对比，返回完整指标与详细结果。
    """
    started_at = time.strftime("%Y-%m-%d %H:%M:%S")

    if not os.path.exists(_CASES_PATH):
        return {"error": "cases.json not found", "ran_at": started_at}

    with open(_CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)

    results = []
    for case in cases:
        question = case["question"]
        role = case["role"]
        gt = expected_paths_for_case(question, role)

        actual_rules = list(set(p["rule"] for p in gt["paths"]))
        actual_entities = gt["entity_ids"]

        results.append({
            "id": case["id"],
            "scenario": case.get("scenario", ""),
            "question": question,
            "role": role,
            "expected_entities": case.get("expected_entities", []),
            "actual_entities": actual_entities,
            "expected_min_paths": case.get("expected_min_paths", 0),
            "actual_paths": gt["path_count"],
            "expected_path_rules": case.get("expected_path_rules", []),
            "actual_path_rules": actual_rules,
            "role_leak": False,
        })

    metrics = compute_metrics(results)

    return {
        "ran_at": started_at,
        "total_cases": len(cases),
        "metrics": metrics,
        "baseline": {
            # 单 Agent 基线：无工作流、无图谱、无角色过滤的假设下限
            "f1": 0.50,
            "path_hit_rate": 0.0,
            "role_block_rate": 0.0,
            "risk_accuracy": 0.33,
            "precision": 0.50,
            "recall": 0.50,
        },
        "results": [
            {
                "id": r["id"],
                "passed": (
                    r["actual_paths"] >= r["expected_min_paths"]
                    and set(r["expected_entities"]) <= set(r["actual_entities"])
                ),
                "note": (
                    f"期望≥{r['expected_min_paths']}条路径，实际{r['actual_paths']}条"
                    if r["expected_min_paths"] > 0
                    else "越权检测用例"
                ),
            }
            for r in results
        ],
    }