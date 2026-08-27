#!/usr/bin/env python3
"""
策略数据分析脚本
分析62个策略的表现，生成综合评分、相关性分析和优化建议
"""

import json
import math
from collections import defaultdict

# 读取数据
with open(r'C:\Users\xrs08\Desktop\腾讯openclaw\stock_intelligence\multi_strategy_trading\output\strategy_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

strategies = data['strategies']
print(f"总共加载了 {len(strategies)} 个策略")

# ============================================
# 1. 计算每个策略的关键指标
# ============================================
strategy_metrics = []

for s in strategies:
    name = s['name']
    category = s['category']
    total_return = s['total_return'] * 100  # 转为百分比
    sharpe_ratio = s['sharpe_ratio']
    max_drawdown = s['max_drawdown'] * 100  # 转为百分比
    win_rate = s['win_rate']
    if win_rate > 1:
        win_rate = win_rate / 100.0  # 已是百分比，归一化到 0-1
    trade_count = len(s.get('trades', []))

    # 平均每笔收益 (使用已实现盈亏/交易次数)
    realized_pnl = s['realized_pnl']
    avg_profit_per_trade = realized_pnl / trade_count if trade_count > 0 else 0

    strategy_metrics.append({
        'name': name,
        'category': category,
        'total_return': total_return,
        'avg_profit_per_trade': avg_profit_per_trade,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'trade_count': trade_count,
        'realized_pnl': realized_pnl,
        'initial_capital': s['initial_capital'],
        'total_value': s['total_value']
    })

# ============================================
# 2. 计算综合评分
# ============================================
# 评分权重：总收益(30%)、夏普比率(25%)、胜率(20%)、最大回撤(15%)、交易次数(10%)

# 归一化函数 (Min-Max)
def normalize(values):
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [50.0] * len(values)
    return [(v - min_val) / (max_val - min_val) * 100 for v in values]

# 提取各指标
total_returns = [m['total_return'] for m in strategy_metrics]
sharpe_ratios = [m['sharpe_ratio'] for m in strategy_metrics]
win_rates = [m['win_rate'] for m in strategy_metrics]
max_drawdowns = [m['max_drawdown'] for m in strategy_metrics]  # 回撤越小越好
trade_counts = [m['trade_count'] for m in strategy_metrics]

# 归一化 (回撤是负向指标，取反)
norm_return = normalize(total_returns)
norm_sharpe = normalize(sharpe_ratios)
norm_winrate = normalize(win_rates)
norm_drawdown = [100 - v for v in normalize(max_drawdowns)]  # 回撤越小越好
norm_trades = normalize(trade_counts)

# 计算综合评分
weights = {
    'return': 0.30,
    'sharpe': 0.25,
    'winrate': 0.20,
    'drawdown': 0.15,
    'trades': 0.10
}

for i, m in enumerate(strategy_metrics):
    m['norm_return'] = norm_return[i]
    m['norm_sharpe'] = norm_sharpe[i]
    m['norm_winrate'] = norm_winrate[i]
    m['norm_drawdown'] = norm_drawdown[i]
    m['norm_trades'] = norm_trades[i]

    m['composite_score'] = (
        norm_return[i] * weights['return'] +
        norm_sharpe[i] * weights['sharpe'] +
        norm_winrate[i] * weights['winrate'] +
        norm_drawdown[i] * weights['drawdown'] +
        norm_trades[i] * weights['trades']
    )

# 按综合评分排序
strategy_metrics.sort(key=lambda x: x['composite_score'], reverse=True)

# ============================================
# 3. TOP5 和 BOTTOM5
# ============================================
top5 = strategy_metrics[:5]
bottom5 = strategy_metrics[-5:]

print("\n=== TOP5 策略 ===")
for i, s in enumerate(top5, 1):
    print(f"{i}. {s['name']} (评分: {s['composite_score']:.2f})")

print("\n=== BOTTOM5 策略 ===")
for i, s in enumerate(bottom5, 1):
    print(f"{i}. {s['name']} (评分: {s['composite_score']:.2f})")

# ============================================
# 4. 相关性分析 - 基于交易模式
# ============================================
# 由于没有每日收益率数据，我们基于策略的 category 和表现相似度进行相关性分析
# 实际代码中使用交易记录的profit_pct来模拟

def calc_correlation(x, y):
    """皮尔逊相关系数"""
    n = len(x)
    if n == 0:
        return 0
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

    if denom_x == 0 or denom_y == 0:
        return 0
    return numerator / (denom_x * denom_y)

# 基于交易收益率的相关性分析
def get_trade_returns(s):
    return [t['profit_pct'] for t in s.get('trades', [])]

# 计算策略两两相关性
high_corr_pairs = []
strategy_names = [s['name'] for s in strategies]

# 按名称建立索引
name_to_idx = {name: i for i, name in enumerate(strategy_names)}

for i in range(len(strategies)):
    for j in range(i + 1, len(strategies)):
        returns_i = get_trade_returns(strategies[i])
        returns_j = get_trade_returns(strategies[j])

        # 如果有足够的共同交易次数
        if len(returns_i) >= 3 and len(returns_j) >= 3:
            corr = calc_correlation(returns_i, returns_j)
            if corr > 0.9:
                high_corr_pairs.append({
                    'strategy1': strategies[i]['name'],
                    'strategy2': strategies[j]['name'],
                    'correlation': corr
                })

print(f"\n=== 高度相关策略对 (>0.9) ===")
print(f"找到 {len(high_corr_pairs)} 对高度相关的策略")

# ============================================
# 5. 按类别统计
# ============================================
category_stats = defaultdict(lambda: {'count': 0, 'total_return': 0, 'avg_sharpe': 0, 'win_rate': 0})

for m in strategy_metrics:
    cat = m['category']
    category_stats[cat]['count'] += 1
    category_stats[cat]['total_return'] += m['total_return']
    category_stats[cat]['avg_sharpe'] += m['sharpe_ratio']
    category_stats[cat]['win_rate'] += m['win_rate']

for cat in category_stats:
    stats = category_stats[cat]
    n = stats['count']
    stats['avg_return'] = stats['total_return'] / n
    stats['avg_sharpe'] = stats['avg_sharpe'] / n
    stats['avg_winrate'] = stats['win_rate'] / n

print("\n=== 类别统计 ===")
for cat, stats in sorted(category_stats.items(), key=lambda x: x[1]['avg_return'], reverse=True):
    print(f"{cat}: {stats['count']}个策略, 平均收益{stats['avg_return']:.2f}%, 平均夏普{stats['avg_sharpe']:.2f}")

# ============================================
# 6. 生成Markdown报告
# ============================================

report = """# 策略分析报告

> 生成时间: {update_time}
> 回测期间: {backtest_start} 至 {backtest_end} (共 {backtest_days} 天)
> 策略总数: {strategy_count}

---

## 1. 执行摘要

本报告对 **{strategy_count}** 个量化交易策略进行了全面分析，评估指标包括：
- 总收益率 (权重30%)
- 夏普比率 (权重25%)
- 胜率 (权重20%)
- 最大回撤 (权重15%)
- 交易次数 (权重10%)

### 1.1 整体表现概览

| 指标 | 平均值 | 最大值 | 最小值 |
|------|--------|--------|--------|
| 总收益率 | {avg_return:.2f}% | {max_return:.2f}% | {min_return:.2f}% |
| 夏普比率 | {avg_sharpe:.2f} | {max_sharpe:.2f} | {min_sharpe:.2f} |
| 胜率 | {avg_winrate:.2f}% | {max_winrate:.2f}% | {min_winrate:.2f}% |
| 最大回撤 | {avg_drawdown:.2f}% | {max_drawdown:.2f}% | {min_drawdown:.2f}% |
| 交易次数 | {avg_trades:.1f} | {max_trades} | {min_trades} |

---

## 2. TOP5 策略排名

以下策略综合评分最高，表现最为出色：

| 排名 | 策略名称 | 类别 | 综合评分 | 总收益 | 夏普比率 | 胜率 | 最大回撤 | 交易次数 |
|------|----------|------|----------|--------|----------|------|----------|----------|
""".format(
    update_time=data['update_time'],
    backtest_start=data['backtest_start'],
    backtest_end=data['backtest_end'],
    backtest_days=data['backtest_days'],
    strategy_count=data['strategy_count'],
    avg_return=sum(m['total_return'] for m in strategy_metrics) / len(strategy_metrics),
    max_return=max(m['total_return'] for m in strategy_metrics),
    min_return=min(m['total_return'] for m in strategy_metrics),
    avg_sharpe=sum(m['sharpe_ratio'] for m in strategy_metrics) / len(strategy_metrics),
    max_sharpe=max(m['sharpe_ratio'] for m in strategy_metrics),
    min_sharpe=min(m['sharpe_ratio'] for m in strategy_metrics),
    avg_winrate=sum(m['win_rate'] for m in strategy_metrics) / len(strategy_metrics),
    max_winrate=max(m['win_rate'] for m in strategy_metrics),
    min_winrate=min(m['win_rate'] for m in strategy_metrics),
    avg_drawdown=sum(m['max_drawdown'] for m in strategy_metrics) / len(strategy_metrics),
    max_drawdown=max(m['max_drawdown'] for m in strategy_metrics),
    min_drawdown=min(m['max_drawdown'] for m in strategy_metrics),
    avg_trades=sum(m['trade_count'] for m in strategy_metrics) / len(strategy_metrics),
    max_trades=max(m['trade_count'] for m in strategy_metrics),
    min_trades=min(m['trade_count'] for m in strategy_metrics)
)

for i, s in enumerate(top5, 1):
    report += f"| {i} | {s['name']} | {s['category']} | **{s['composite_score']:.2f}** | {s['total_return']:.2f}% | {s['sharpe_ratio']:.2f} | {s['win_rate']:.2f}% | {s['max_drawdown']:.2f}% | {s['trade_count']} |\n"

report += """
### TOP5 策略特点分析

"""

for i, s in enumerate(top5, 1):
    strengths = []
    if s['total_return'] > 20:
        strengths.append("高收益")
    if s['sharpe_ratio'] > 3:
        strengths.append("风险调整收益优秀")
    if s['win_rate'] > 55:
        strengths.append("胜率高")
    if s['max_drawdown'] < 10:
        strengths.append("回撤控制好")
    if s['trade_count'] > 10:
        strengths.append("交易活跃")

    report += f"**{i}. {s['name']}** ({', '.join(strengths) if strengths else '综合表现良好'})\n"
    report += f"   - 总收益率: {s['total_return']:.2f}%\n"
    report += f"   - 夏普比率: {s['sharpe_ratio']:.2f}\n"
    report += f"   - 胜率: {s['win_rate']:.2f}%\n"
    report += f"   - 最大回撤: {s['max_drawdown']:.2f}%\n\n"

report += """
---

## 3. BOTTOM5 策略排名

以下策略综合评分最低，需要重点关注或优化：

| 排名 | 策略名称 | 类别 | 综合评分 | 总收益 | 夏普比率 | 胜率 | 最大回撤 | 交易次数 |
|------|----------|------|----------|--------|----------|------|----------|----------|
"""

for i, s in enumerate(reversed(bottom5), 1):
    report += f"| {i} | {s['name']} | {s['category']} | {s['composite_score']:.2f} | {s['total_return']:.2f}% | {s['sharpe_ratio']:.2f} | {s['win_rate']:.2f}% | {s['max_drawdown']:.2f}% | {s['trade_count']} |\n"

report += """
### BOTTOM5 策略问题分析

"""

for i, s in enumerate(reversed(bottom5), 1):
    issues = []
    if s['total_return'] < 0:
        issues.append("负收益")
    if s['sharpe_ratio'] < 1:
        issues.append("夏普比率过低")
    if s['win_rate'] < 45:
        issues.append("胜率偏低")
    if s['max_drawdown'] > 20:
        issues.append("回撤过大")

    report += f"**{i}. {s['name']}** ({', '.join(issues) if issues else '综合表现欠佳'})\n"
    report += f"   - 总收益率: {s['total_return']:.2f}%\n"
    report += f"   - 夏普比率: {s['sharpe_ratio']:.2f}\n"
    report += f"   - 胜率: {s['win_rate']:.2f}%\n"
    report += f"   - 最大回撤: {s['max_drawdown']:.2f}%\n\n"

report += """
---

## 4. 策略相关性分析

### 4.1 高度相似策略对 (皮尔逊相关系数 > 0.9)

以下策略组合的交易收益模式高度相似，建议考虑合并或差异化配置：

| 策略1 | 策略2 | 相关系数 |
|-------|-------|----------|
"""

if high_corr_pairs:
    for pair in high_corr_pairs[:20]:  # 最多显示20对
        report += f"| {pair['strategy1']} | {pair['strategy2']} | {pair['correlation']:.4f} |\n"
else:
    report += "| - | 未发现高度相关策略对 | - |\n"

report += f"""
（共发现 {len(high_corr_pairs)} 对高度相关策略）

### 4.2 相关性分析结论

"""

if len(high_corr_pairs) > 10:
    report += """**发现较多相似策略，建议：**
1. 对高度相似的策略进行合并，减少策略冗余
2. 保留表现更好的版本，关闭表现较差的版本
3. 考虑将相似策略分配到不同的交易标的上，实现策略差异化

"""
elif len(high_corr_pairs) > 0:
    report += """**策略相关性处于合理范围**，策略组合具有一定多样性。

"""
else:
    report += """**所有策略相关性较低**，策略组合展现了良好的多样性。

"""

report += """
---

## 5. 类别表现对比

| 策略类别 | 策略数量 | 平均收益 | 平均夏普比率 | 平均胜率 |
|----------|----------|----------|--------------|----------|
"""

for cat, stats in sorted(category_stats.items(), key=lambda x: x[1]['avg_return'], reverse=True):
    report += f"| {cat} | {stats['count']} | {stats['avg_return']:.2f}% | {stats['avg_sharpe']:.2f} | {stats['avg_winrate']:.2f}% |\n"

report += """
### 类别分析结论

"""

best_cat = max(category_stats.items(), key=lambda x: x[1]['avg_return'])
worst_cat = min(category_stats.items(), key=lambda x: x[1]['avg_return'])

report += f"""- **表现最佳类别**: {best_cat[0]}，平均收益 {best_cat[1]['avg_return']:.2f}%，建议加大配置
- **表现最差类别**: {worst_cat[0]}，平均收益 {worst_cat[1]['avg_return']:.2f}%，建议减少配置或优化

---

## 6. 优化建议

### 6.1 优秀策略 (建议保留并适当增加仓位)

"""

for s in top5[:3]:
    report += f"""**{s['name']}**
- 当前表现: 总收益 {s['total_return']:.2f}%, 夏普比率 {s['sharpe_ratio']:.2f}
- 建议: 继续持有，可考虑适当增加仓位

"""

report += """### 6.2 需要优化的策略

"""

for s in bottom5:
    report += f"""**{s['name']}**
"""
    if s['total_return'] < 0:
        report += f"- 问题: 产生负收益 ({s['total_return']:.2f}%)\n"
    if s['sharpe_ratio'] < 1:
        report += f"- 问题: 夏普比率过低 ({s['sharpe_ratio']:.2f})，风险调整收益不理想\n"
    if s['win_rate'] < 45:
        report += f"- 问题: 胜率偏低 ({s['win_rate']:.2f}%)\n"
    if s['max_drawdown'] > 20:
        report += f"- 问题: 最大回撤过大 ({s['max_drawdown']:.2f}%)\n"

    # 个性化建议
    suggestions = []
    if s['win_rate'] < 50 and s['trade_count'] > 5:
        suggestions.append("优化入场时机，提高胜率")
    if s['max_drawdown'] > 15:
        suggestions.append("增加止损机制，严格控制回撤")
    if s['sharpe_ratio'] < 2:
        suggestions.append("考虑增加策略 filters，减少假信号")

    if suggestions:
        report += "- 优化建议: " + "; ".join(suggestions) + "\n"
    report += "\n"

report += """### 6.3 策略合并建议

"""

if high_corr_pairs:
    report += f"发现 {len(high_corr_pairs)} 对高度相似策略，建议:\n\n"
    # 按策略分组显示
    strategy_pair_count = defaultdict(list)
    for pair in high_corr_pairs:
        strategy_pair_count[pair['strategy1']].append(pair['strategy2'])

    for s1, related in list(strategy_pair_count.items())[:5]:
        report += f"- **{s1}** 与 {len(related)} 个策略高度相似: {', '.join(related[:3])}\n"
else:
    report += "未发现需要合并的相似策略。\n"

report += """
### 6.4 整体配置建议

1. **仓位分配**: 将资金集中到TOP5策略，减少或退出BOTTOM5策略
2. **风险控制**: 对回撤超过15%的策略添加或加强止损规则
3. **策略迭代**: 基于历史表现优化入场/出场逻辑，提高胜率
4. **分散投资**: 避免策略过度集中，保持策略类型的多样性

---

## 7. 附录: 完整策略排名

| 排名 | 策略名称 | 类别 | 综合评分 | 总收益 | 夏普比率 | 胜率 | 最大回撤 | 交易次数 |
|------|----------|------|----------|--------|----------|------|----------|----------|
"""

for i, s in enumerate(strategy_metrics, 1):
    report += f"| {i} | {s['name']} | {s['category']} | {s['composite_score']:.2f} | {s['total_return']:.2f}% | {s['sharpe_ratio']:.2f} | {s['win_rate']:.2f}% | {s['max_drawdown']:.2f}% | {s['trade_count']} |\n"

report += """

---

*报告由策略分析系统自动生成*
"""

# 写入文件
output_path = r'C:\Users\xrs08\Desktop\腾讯openclaw\stock_intelligence\multi_strategy_trading\docs\strategy_analysis_report.md'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(report)

print(f"\n报告已生成: {output_path}")
print(f"报告长度: {len(report)} 字符")