# -*- coding: utf-8 -*-
"""
策略相关性分析 + 聚类合并
用法: python analyze_strategy_correlation.py
输出: strategy_clusters.json（聚类结果）+ 合并建议
"""
import json
import sys
import os
import numpy as np
from collections import defaultdict

def load_data(filepath="output/strategy_data.json"):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def build_return_matrix(strategies):
    """构建日收益率矩阵 (n_strategies x n_dates)"""
    # 收集所有日期
    all_dates = set()
    for s in strategies:
        for pt in s.get("equity_curve", []):
            all_dates.add(pt["date"])
    all_dates = sorted(all_dates)

    if len(all_dates) < 5:
        print(f"⚠️ 只有 {len(all_dates)} 个交易日，不足以计算相关性")
        return None, None, None

    date_idx = {d: i for i, d in enumerate(all_dates)}
    n = len(strategies)
    m = len(all_dates)

    # 构建权益矩阵
    equity = np.full((n, m), np.nan)
    for i, s in enumerate(strategies):
        for pt in s.get("equity_curve", []):
            if pt.get("value") is not None:
                j = date_idx[pt["date"]]
                equity[i, j] = pt["value"]

    # 计算日收益率（百分比变化）
    returns = np.full((n, m - 1), np.nan)
    for i in range(n):
        for j in range(m - 1):
            if not np.isnan(equity[i, j]) and not np.isnan(equity[i, j + 1]) and equity[i, j] > 0:
                returns[i, j] = (equity[i, j + 1] / equity[i, j]) - 1.0

    return returns, all_dates, equity

def compute_correlation(returns):
    """计算 pairwise Pearson 相关系数，处理 NaN"""
    n = returns.shape[0]
    corr_matrix = np.full((n, n), np.nan)

    for i in range(n):
        for j in range(i, n):
            ri = returns[i, :]
            rj = returns[j, :]
            # 只取两者都有有效收益的日期
            mask = ~np.isnan(ri) & ~np.isnan(rj)
            if mask.sum() < 5:  # 需要至少5个共同交易日
                corr_matrix[i, j] = corr_matrix[j, i] = 0.0
                continue
            # 计算相关系数
            ri_valid = ri[mask]
            rj_valid = rj[mask]
            # 如果其中一个是常量（无波动），corr = 0
            if np.std(ri_valid) < 1e-10 or np.std(rj_valid) < 1e-10:
                corr_matrix[i, j] = corr_matrix[j, i] = 0.0
            else:
                corr_coef = np.corrcoef(ri_valid, rj_valid)[0, 1]
                corr_matrix[i, j] = corr_matrix[j, i] = corr_coef

    return corr_matrix

def cluster_strategies(corr_matrix, strategies, threshold=0.8):
    """
    贪心聚类：
    1. 按 |ρ| 排序
    2. 找到所有对 |ρ| > threshold 的
    3. 用 union-find 聚类
    """
    n = len(strategies)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    # 找到所有高相关对
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            rho = corr_matrix[i, j]
            if not np.isnan(rho) and abs(rho) >= threshold:
                pairs.append((i, j, rho))

    pairs.sort(key=lambda x: -abs(x[2]))

    for i, j, rho in pairs:
        union(i, j)

    # 收集聚类
    clusters = defaultdict(list)
    for i in range(n):
        root = find(i)
        clusters[root].append(i)

    return dict(clusters), pairs

def pick_best_in_cluster(cluster_indices, strategies):
    """在每个聚类里选择最优策略（按 Sharpe 排序，其次总收益）"""
    members = []
    for idx in cluster_indices:
        s = strategies[idx]
        sharpe = s.get("sharpe_ratio", 0) or 0
        total_ret = s.get("total_return", 0) or 0
        max_dd = s.get("max_drawdown", 0) or 0
        trades = len(s.get("trades", []))
        win_rate = s.get("win_rate", 0) or 0
        members.append({
            "index": idx,
            "name": s["name"],
            "sharpe": sharpe,
            "total_return": total_ret,
            "max_drawdown": max_dd,
            "trades": trades,
            "win_rate": win_rate,
        })

    # 排序：Sharpe 降序 → 总收益降序
    members.sort(key=lambda x: (x["sharpe"], x["total_return"]), reverse=True)
    return members

def main():
    print("=" * 70)
    print("策略相关性分析与聚类合并")
    print("=" * 70)

    data = load_data()
    strategies = data["strategies"]
    print(f"\n📊 加载 {len(strategies)} 个策略")
    print(f"   回测区间: {data.get('backtest_start')} ~ {data.get('backtest_end')}")
    print(f"   交易日数: {data.get('backtest_days')}")

    # 构建收益率矩阵
    returns, all_dates, equity = build_return_matrix(strategies)
    if returns is None:
        print("❌ 数据不足，无法分析")
        return

    n_dates = returns.shape[1]
    print(f"\n📅 日收益率矩阵: {len(strategies)} 策略 × {n_dates} 天")

    # 过滤掉零成交策略（全是 NaN）
    zero_trade = []
    active_indices = []
    for i, s in enumerate(strategies):
        trades = len(s.get("trades", []))
        if trades == 0:
            zero_trade.append(i)
        else:
            active_indices.append(i)

    print(f"\n🔍 零成交策略: {len(zero_trade)} 个")
    for i in zero_trade:
        print(f"   ❌ {strategies[i]['name']}")

    # 只对有成交的算相关性
    active_returns = returns[active_indices, :]
    active_strategies = [strategies[i] for i in active_indices]

    print(f"   活跃策略: {len(active_strategies)} 个")
    print(f"\n🧮 计算 {len(active_strategies)}×{len(active_strategies)} 相关性矩阵...")

    corr_matrix = compute_correlation(active_returns)

    # --- 输出相关性最高的 pairs ---
    print("\n" + "=" * 70)
    print("🔗 最高相关的策略对（|ρ| ≥ 0.8）")
    print("=" * 70)

    high_pairs = []
    for i in range(len(active_strategies)):
        for j in range(i + 1, len(active_strategies)):
            rho = corr_matrix[i, j]
            if not np.isnan(rho) and abs(rho) >= 0.8:
                high_pairs.append((i, j, rho))

    high_pairs.sort(key=lambda x: -abs(x[2]))

    if high_pairs:
        for i, j, rho in high_pairs[:30]:  # 只展示 top 30
            s1 = active_strategies[i]["name"]
            s2 = active_strategies[j]["name"]
            print(f"  ρ={rho:+.3f}  |  {s1}  ↔  {s2}")
    else:
        print("  （无）")

    # --- 聚类 ---
    print("\n" + "=" * 70)
    print("🧩 聚类结果（|ρ| ≥ 0.8 → 同组）")
    print("=" * 70)

    clusters, all_pairs = cluster_strategies(corr_matrix, active_strategies, threshold=0.8)

    # 把零成交策略单独成组
    final_groups = {}
    group_id = 0

    # 先处理活跃聚类
    singleton_count = 0
    for root, indices in sorted(clusters.items(), key=lambda x: -len(x[1])):
        best_list = pick_best_in_cluster(indices, active_strategies)
        final_groups[f"group_{group_id}"] = {
            "size": len(indices),
            "members": best_list,
            "selected": best_list[0]["name"],
            "selected_sharpe": best_list[0]["sharpe"],
            "selected_return": best_list[0]["total_return"],
        }
        if len(indices) == 1:
            singleton_count += 1
        group_id += 1

    # 零成交的单独显示
    if zero_trade:
        zero_members = [{"name": strategies[i]["name"], "sharpe": 0, "total_return": 0} for i in zero_trade]
        final_groups["zero_trade"] = {
            "size": len(zero_trade),
            "members": zero_members,
            "selected": None,
            "note": "all zero trades — won't survive anyway"
        }

    # --- 按组大小输出 ---
    print(f"\n聚类统计:")
    print(f"  总策略: {len(strategies)}")
    print(f"  零成交: {len(zero_trade)}")
    print(f"  有成交: {len(active_strategies)}")
    print(f"  高相关对(|ρ|≥0.8): {len(all_pairs)}")
    print(f"  聚类数: {len(clusters)}（含 {singleton_count} 个独立策略）")
    print(f"  合并后预期: {len(clusters)} 个独立策略")

    # --- 详细输出 ---
    print("\n" + "=" * 70)
    print("📋 各聚类详情 & 选定策略")
    print("=" * 70)

    selected_strategies = []

    for gname, ginfo in sorted(final_groups.items(),
                                key=lambda x: -x[1]["size"] if x[0] != "zero_trade" else -1):
        if gname == "zero_trade":
            print(f"\n🗑️  零成交组 ({ginfo['size']} 个):")
            for m in ginfo["members"]:
                print(f"     {m['name']}")
            continue

        print(f"\n{'─' * 60}")
        print(f"📦 {gname} — {ginfo['size']} 个策略 → 选: ⭐ {ginfo['selected']}")
        print(f"{'─' * 60}")

        for rank, m in enumerate(ginfo["members"]):
            marker = "⭐ SELECTED" if rank == 0 else f"  #{rank + 1}"
            print(f"  {marker:<14} | Sharpe={m['sharpe']:>7.2f} | 收益={m['total_return']*100:>+7.2f}% | "
                  f"回撤={m['max_drawdown']*100:>5.1f}% | 交易={m['trades']:>3}笔 | {m['name']}")

        selected_strategies.append({
            "group": gname,
            "name": ginfo["selected"],
            "sharpe": ginfo["selected_sharpe"],
            "total_return": ginfo["selected_return"],
            "group_size": ginfo["size"],
        })

    # --- 总结 ---
    print("\n" + "=" * 70)
    print("🏆 合并后策略池")
    print("=" * 70)
    for i, s in enumerate(selected_strategies, 1):
        print(f"  {i:2}. {s['name']:<25} Sharpe={s['sharpe']:>6.2f} | "
              f"收益={s['total_return']*100:>+7.2f}% | 组内{s['group_size']}个")

    # --- 保存到 JSON ---
    output = {
        "analysis_date": data.get("update_time", "unknown"),
        "total_strategies": len(strategies),
        "zero_trade": len(zero_trade),
        "active_strategies": len(active_strategies),
        "high_correlation_pairs": len(all_pairs),
        "clusters_before_merge": len(final_groups) - (1 if zero_trade else 0),
        "selected_strategies": selected_strategies,
        "all_groups": {g: {
            "size": gi["size"], "selected": gi["selected"],
            "members": [m["name"] for m in gi["members"]]
        } for g, gi in final_groups.items()},
    }

    out_path = "output/strategy_clusters.json"
    os.makedirs("output", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✅ 完整结果已保存到: {out_path}")
    return output

if __name__ == "__main__":
    main()
