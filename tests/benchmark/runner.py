"""Benchmark 运行器：用 ground truth 对比真实链路输出。

用法：
  python -m tests.benchmark.runner          # 运行全部用例
  python -m tests.benchmark.runner --role procurement  # 只跑指定角色
  python -m tests.benchmark.runner --scenario cross_role_leak  # 只跑某类场景
  python -m tests.benchmark.runner --dry-run  # 只跑 ground truth，不调真实链路
"""

import argparse
import json
import os
import sys
import time
from typing import Any

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.benchmark.ground_truth import (
    compute_paths,
    expected_paths_for_case,
    load_graph,
    match_entities,
)
from tests.benchmark.metrics import compute_metrics


def run_ground_truth_only(cases: list[dict]) -> list[dict]:
    """只跑 ground truth（不调真实链路），验证用例与预期一致性。"""
    results = []
    for case in cases:
        gt = expected_paths_for_case(case["question"], case["role"])
        actual_rules = list(set(p["rule"] for p in gt["paths"]))
        actual_entities = gt["entity_ids"]

        results.append({
            "id": case["id"],
            "scenario": case.get("scenario", ""),
            "question": case["question"],
            "role": case["role"],
            "expected_entities": case.get("expected_entities", []),
            "actual_entities": actual_entities,
            "expected_min_paths": case.get("expected_min_paths", 0),
            "actual_paths": len(gt["paths"]),
            "expected_path_rules": case.get("expected_path_rules", []),
            "actual_path_rules": actual_rules,
            "role_leak": False,  # ground truth 没有真实调用，不会有泄漏
            "gt_paths": gt["paths"],
        })
    return results


def run_against_real_api(cases: list[dict], base_url: str = "http://127.0.0.1:8000") -> list[dict]:
    """调真实后端 API 运行 Benchmark。

    对每个用例：
    1. 登录获取 token
    2. 调 POST /api/graph/impact 获取图谱结果
    3. 对比 ground truth
    """
    import urllib.request
    import urllib.error

    # 缓存各角色的 token
    tokens: dict[str, str] = {}

    def get_token(role: str) -> str:
        if role not in tokens:
            username = f"catl_{role}"
            body = json.dumps({"username": username, "password": "catl123"}).encode()
            req = urllib.request.Request(
                f"{base_url}/api/auth/login",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    tokens[role] = data["access_token"]
            except Exception as e:
                print(f"  [WARN] 登录失败 ({role}): {e}")
                tokens[role] = ""
        return tokens[role]

    results = []
    graph = load_graph()

    for i, case in enumerate(cases):
        print(f"\n[{i + 1}/{len(cases)}] {case['id']}: {case['question'][:50]}... (role={case['role']})")
        role = case["role"]
        token = get_token(role)
        if not token:
            print("  跳过（无 token）")
            continue

        # 调图谱影响分析接口
        body = json.dumps({"question": case["question"]}).encode()
        req = urllib.request.Request(
            f"{base_url}/api/graph/impact",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.reason}")
            results.append({
                "id": case["id"],
                "scenario": case.get("scenario", ""),
                "question": case["question"],
                "role": role,
                "expected_entities": case.get("expected_entities", []),
                "actual_entities": [],
                "expected_min_paths": case.get("expected_min_paths", 0),
                "actual_paths": 0,
                "expected_path_rules": case.get("expected_path_rules", []),
                "actual_path_rules": [],
                "role_leak": False,
                "api_error": f"HTTP {e.code}",
            })
            continue
        except Exception as e:
            print(f"  请求失败: {e}")
            continue

        actual_entities = [e["id"] for e in data.get("entities", [])]
        actual_paths_list = data.get("paths", [])
        actual_rules = list(set(p["rule"] for p in actual_paths_list))

        # 检查越权泄漏：检查路径中的节点是否都对当前角色可见
        role_leak = False
        node_map = {n["id"]: n for n in graph["nodes"]}
        for path in actual_paths_list:
            for node in path.get("nodes", []):
                nid = node.get("id", "")
                graph_node = node_map.get(nid, {})
                allowed = graph_node.get("allowed_roles", [])
                if role != "admin" and role not in allowed:
                    role_leak = True
                    print(f"  [LEAK] 路径包含节点 {nid}({node.get('name', '?')})，角色 {role} 不可见")
                    break
            if role_leak:
                break

        result = {
            "id": case["id"],
            "scenario": case.get("scenario", ""),
            "question": case["question"],
            "role": role,
            "expected_entities": case.get("expected_entities", []),
            "actual_entities": actual_entities,
            "expected_min_paths": case.get("expected_min_paths", 0),
            "actual_paths": len(actual_paths_list),
            "expected_path_rules": case.get("expected_path_rules", []),
            "actual_path_rules": actual_rules,
            "role_leak": role_leak,
        }
        results.append(result)

        # 简要输出
        entity_ok = set(case.get("expected_entities", [])) <= set(actual_entities)
        path_ok = len(actual_paths_list) >= case.get("expected_min_paths", 0)
        print(f"  实体: {'OK' if entity_ok else 'MISS'} | 路径: {len(actual_paths_list)} (>={case.get('expected_min_paths', 0)} {'OK' if path_ok else 'FAIL'}) | 泄漏: {'YES' if role_leak else 'NO'}")

        # 避免请求太快
        time.sleep(0.3)

    return results


def main():
    parser = argparse.ArgumentParser(description="SupplyGuard Benchmark Runner")
    parser.add_argument("--role", help="只跑指定角色")
    parser.add_argument("--scenario", help="只跑某类场景")
    parser.add_argument("--dry-run", action="store_true", help="只跑 ground truth，不调 API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API 地址")
    parser.add_argument("--output", default="tests/benchmark/results.json", help="结果输出路径")
    args = parser.parse_args()

    # 加载用例
    cases_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "cases.json"
    )
    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)

    # 过滤
    if args.role:
        cases = [c for c in cases if c["role"] == args.role]
    if args.scenario:
        cases = [c for c in cases if c.get("scenario") == args.scenario]

    print(f"加载 {len(cases)} 条用例")

    if args.dry_run:
        print("模式: ground truth only（不调 API）")
        results = run_ground_truth_only(cases)
    else:
        print(f"模式: 调真实 API ({args.base_url})")
        results = run_against_real_api(cases, args.base_url)

    # 计算指标
    metrics = compute_metrics(results)

    # 输出
    report = {
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "dry_run" if args.dry_run else "api",
        "total_cases": len(cases),
        "total_results": len(results),
        "metrics": metrics,
        "results": results,
    }

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Benchmark 完成：{len(results)} 条结果")
    print(f"实体 Precision: {metrics['entity_precision']:.2%}")
    print(f"实体 Recall:    {metrics['entity_recall']:.2%}")
    print(f"实体 F1:        {metrics['entity_f1']:.2%}")
    print(f"路径命中率:     {metrics['path_hit_rate']:.2%}")
    print(f"规则 Precision: {metrics['rule_precision']:.2%}")
    print(f"越权拦截率:     {metrics['leak_block_rate']:.2%}")
    print(f"越权泄漏:       {metrics['leak_count']} 条")
    print(f"\n结果已保存到 {args.output}")


if __name__ == "__main__":
    main()