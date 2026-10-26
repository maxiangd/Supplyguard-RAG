# SupplyGuard Benchmark 报告

> 生成时间：2026-10-26 18:16:21
> 模式：dry_run
> 用例数：26

---

## 1. 汇总指标

| 指标 | 值 | 说明 |
|------|-----|------|
| 实体 Precision | 100.00% | 正确命中的实体 / 返回的实体 |
| 实体 Recall | 100.00% | 正确命中的实体 / 期望的实体 |
| 实体 F1 | 100.00% | Precision 与 Recall 的调和平均 |
| 路径命中率 | 100.00% | 实际路径数 ≥ 期望最少路径数的比例 |
| 规则 Precision | 100.00% | 正确命中的传导规则 / 返回的规则 |
| 规则 Recall | 100.00% | 正确命中的传导规则 / 期望的规则 |
| **越权拦截率** | **66.67%** | 越权用例中被正确拦截的比例 |
| 越权泄漏数 | 0 | 发生越权泄漏的用例数 |

## 2. 按角色分组

| 角色 | 用例数 | 泄漏数 | 路径命中率 |
|------|--------|--------|-----------|
| admin | 1 | 0 | 100.00% |
| finance | 1 | 0 | 0.00% |
| logistics | 8 | 0 | 100.00% |
| procurement | 12 | 0 | 100.00% |
| quality | 4 | 0 | 100.00% |

## 3. 详细结果

| ID | 场景 | 角色 | 问题 | 期望实体 | 实际实体 | 期望≥路径 | 实际路径 | 泄漏 |
|----|------|------|------|----------|----------|-----------|----------|------|
| case_001 | single_event | procurement | 宜春枧下窝锂矿停产对宁德时代有什么影响？ | 1 | 1 | >9 | 9 | OK |
| case_002 | single_event | procurement | 刚果金钴出口限制对华友钴业的供应有什么影响？ | 2 | 2 | >8 | 8 | OK |
| case_003 | single_event | logistics | 红海航线绕行对欧洲交付有什么影响？ | 1 | 1 | >7 | 7 | OK |
| case_004 | single_event | procurement | 匈牙利工厂试生产进度对欧洲产能有什么影响？ | 2 | 2 | >2 | 2 | OK |
| case_005 | single_event | quality | 极星4召回事件涉及宁德时代哪些供应商？ | 1 | 1 | >9 | 9 | OK |
| case_006 | single_event | procurement | 碳酸锂价格回落对采购策略有什么影响？ | 1 | 1 | >12 | 12 | OK |
| case_007 | single_event | logistics | 危险品舱位紧张对宁德基地出货有什么影响？ | 2 | 2 | >5 | 5 | OK |
| case_008 | single_event | quality | 欧盟电池法规对德国和匈牙利工厂有什么合规要求？ | 2 | 2 | >2 | 2 | OK |
| case_009 | event_pair | procurement | 宜春锂矿停产加上津巴布韦锂出口收紧，对上游原料保障有什么影响？ | 2 | 2 | >9 | 9 | OK |
| case_010 | event_pair | logistics | 红海绕行加上危险品舱位紧张对Q4欧洲出货有什么影响？ | 2 | 2 | >11 | 11 | OK |
| case_011 | event_pair | quality | 极星4召回和理想MEGA召回对宁德基地质量管控有什么启示？ | 3 | 3 | >11 | 11 | OK |
| case_012 | event_pair | procurement | 刚果金钴出口限制加上印尼镍政策调整对三元正极供应链有什么影响？ | 2 | 2 | >18 | 18 | OK |
| case_013 | event_pair | procurement | 宜春停产和碳酸锂价格回落对正极材料采购有什么交互影响？ | 1 | 1 | >12 | 12 | OK |
| case_014 | event_pair | logistics | 欧盟电池法规加上红海绕行对匈牙利工厂投产节奏有什么影响？ | 3 | 3 | >13 | 13 | OK |
| case_015 | cross_role_leak | procurement | 极星4召回和理想MEGA召回事件对电池供应商有什么风险？ | 2 | 2 | >0 | 0 | OK |
| case_016 | cross_role_leak | logistics | 极氪001电池纠纷和解的详细情况是什么？ | 1 | 1 | >0 | 0 | OK |
| case_017 | cross_role_leak | procurement | 红海航线绕行会影响哪些供应商的原材料运输？ | 1 | 1 | >0 | 0 | OK |
| case_018 | cross_role_leak | logistics | 哪些供应商的原材料依赖印尼的镍资源？ | 1 | 1 | >0 | 1 | OK |
| case_019 | cross_role_leak | finance | 宁德漳湾基地出口走哪个港口最合适？ | 2 | 2 | >0 | 2 | OK |
| case_020 | cross_role_leak | logistics | 恩捷股份的隔膜供应给了哪些工厂？ | 1 | 1 | >0 | 0 | OK |
| case_021 | held_out | procurement | 特斯拉的4680电池产能如何？ | 0 | 0 | >0 | 0 | OK |
| case_022 | held_out | quality | 比亚迪的刀片电池有什么优势？ | 0 | 0 | >0 | 0 | OK |
| case_023 | held_out | procurement | 光伏行业对储能市场有什么影响？ | 0 | 0 | >0 | 0 | OK |
| case_024 | edge_case | procurement | 锂 | 0 | 0 | >0 | 0 | OK |
| case_025 | edge_case | admin | 宁德 | 1 | 1 | >4 | 4 | OK |
| case_026 | edge_case | logistics | 欧洲 工厂 产能 | 0 | 0 | >0 | 0 | OK |

## 4. 越权泄漏详情

✅ 未发现越权泄漏


---

*报告由 tests/benchmark/report.py 自动生成于 2026-10-26 18:17:02*