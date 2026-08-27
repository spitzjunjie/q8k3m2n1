# -*- coding: utf-8 -*-
"""
策略评估报告生成器
读取回测结果，生成Markdown评估报告
"""

import json
import os
from datetime import datetime

from evaluation import StrategyEvaluator


def generate_report(backtest_result, output_path='reports/'):
    """生成策略评估Markdown报告

    Args:
        backtest_result: backtest输出的完整结果dict（含strategies列表）
        output_path: 报告输出目录

    Returns:
        tuple: (md_file_path, json_file_path)
    """
    evaluator = StrategyEvaluator()
    strategies = backtest_result.get('strategies', [])
    evaluations = evaluator.evaluate_batch(strategies)
    grade_stats = evaluator.grade_stats(evaluations)

    os.makedirs(output_path, exist_ok=True)
    date_str = datetime.now().strftime('%Y%m%d')
    date_display = datetime.now().strftime('%Y-%m-%d')

    # === Markdown报告 ===
    md = f"# 策略评估报告 {date_display}\n\n"
    md += f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    md += f"> 策略总数：{len(evaluations)}\n\n"

    # 回测信息
    if 'backtest_start' in backtest_result:
        md += f"**回测区间**：{backtest_result.get('backtest_start')} ~ {backtest_result.get('backtest_end')} "
        md += f"({backtest_result.get('backtest_days', 0)}个交易日)\n\n"
    else:
        md += f"**运行类型**：每日模拟交易\n\n"

    # 分级统计
    md += "## 策略分级统计\n\n"
    grade_emoji = {'S': '🏆', 'A': '🥇', 'B': '🥈', 'C': '🥉', 'D': '⚠️'}
    md += "| 等级 | 数量 | 占比 | 说明 |\n"
    md += "|------|------|------|------|\n"
    grade_desc = {
        'S': '优秀（综合分≥80）',
        'A': '良好（65-79）',
        'B': '合格（50-64）',
        'C': '较差（35-49）',
        'D': '淘汰候选（<35）'
    }
    total = len(evaluations) if evaluations else 1
    for grade in ['S', 'A', 'B', 'C', 'D']:
        count = grade_stats.get(grade, 0)
        pct = count / total * 100
        md += f"| {grade_emoji[grade]} {grade} | {count} | {pct:.1f}% | {grade_desc[grade]} |\n"
    md += "\n"

    # 策略排名表
    md += "## 策略综合排名\n\n"
    md += "| 排名 | 策略名 | 类别 | 版本 | 综合分 | 等级 | 收益率 | 夏普 | 最大回撤 | 胜率 | 盈亏比 | 稳定性 |\n"
    md += "|------|--------|------|------|--------|------|--------|------|----------|------|--------|--------|\n"
    for i, e in enumerate(evaluations, 1):
        md += f"| {i} | {e['name']} | {e['category']} | {e['version']} | "
        md += f"**{e['composite_score']}** | {grade_emoji[e['grade']]} {e['grade']} | "
        md += f"{e['total_return']*100:+.2f}% | {e['sharpe_ratio']:.2f} | "
        wr_display = e['win_rate'] * 100 if e['win_rate'] <= 1 else e['win_rate']
        md += f"{e['max_drawdown']*100:.1f}% | {wr_display:.0f}% | "
        md += f"{e['profit_loss_ratio']:.2f} | {e['return_stability']:.2f} |\n"
    md += "\n"

    # Top 5 优秀策略
    md += "## 🏆 Top 5 优秀策略\n\n"
    for i, e in enumerate(evaluations[:5], 1):
        md += f"### {i}. {e['name']} （{e['grade']}级，综合分{e['composite_score']}）\n"
        md += f"- **类别**：{e['category']}\n"
        md += f"- **收益率**：{e['total_return']*100:+.2f}%\n"
        md += f"- **夏普比率**：{e['sharpe_ratio']:.2f}\n"
        md += f"- **最大回撤**：{e['max_drawdown']*100:.1f}%\n"
        wr_display = e['win_rate'] * 100 if e['win_rate'] <= 1 else e['win_rate']
        md += f"- **胜率**：{wr_display:.0f}%\n"
        md += f"- **盈亏比**：{e['profit_loss_ratio']:.2f}\n"
        md += f"- **收益稳定性**：{e['return_stability']:.2f}\n"
        md += f"- **交易次数**：{e['trade_count']}\n\n"

    # 淘汰建议
    d_grade = [e for e in evaluations if e['grade'] == 'D']
    c_grade = [e for e in evaluations if e['grade'] == 'C']
    md += "## ⚠️ 淘汰与观察建议\n\n"
    if d_grade:
        md += "### 建议淘汰（D级）\n\n"
        for e in d_grade:
            md += f"- ❌ **{e['name']}**：综合分{e['composite_score']}，"
            md += f"收益{e['total_return']*100:+.2f}%，夏普{e['sharpe_ratio']:.2f}，"
            md += f"回撤{e['max_drawdown']*100:.1f}%\n"
        md += "\n"
    if c_grade:
        md += "### 观察名单（C级，连续30天C级以下则降级）\n\n"
        for e in c_grade:
            md += f"- ⚠️ **{e['name']}**：综合分{e['composite_score']}，"
            md += f"收益{e['total_return']*100:+.2f}%\n"
        md += "\n"

    # 评估方法说明
    md += "## 📊 评估方法说明\n\n"
    md += "### 综合评分公式（0-100分）\n\n"
    md += "| 维度 | 权重 | 映射区间 |\n"
    md += "|------|------|----------|\n"
    md += "| 夏普比率 | 30% | 0-3 → 0-30 |\n"
    md += "| 总收益率 | 25% | 0-30% → 0-25 |\n"
    md += "| 最大回撤 | 20% | 0-30% → 20-0（越小越高） |\n"
    md += "| 胜率 | 15% | 0-1 → 0-15 |\n"
    md += "| 收益稳定性 | 10% | 0-1 → 0-10 |\n\n"
    md += "### 等级划分\n\n"
    md += "| 等级 | 分数区间 | 含义 |\n"
    md += "|------|----------|------|\n"
    md += "| S | 80-100 | 优秀，可加仓 |\n"
    md += "| A | 65-79 | 良好，保持 |\n"
    md += "| B | 50-64 | 合格，观察 |\n"
    md += "| C | 35-49 | 较差，观察名单 |\n"
    md += "| D | 0-34 | 淘汰候选 |\n\n"

    # 写入Markdown文件
    md_file = os.path.join(output_path, f'strategy_evaluation_{date_str}.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(md)

    # === JSON排名数据 ===
    json_data = {
        'generate_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'backtest_start': backtest_result.get('backtest_start'),
        'backtest_end': backtest_result.get('backtest_end'),
        'strategy_count': len(evaluations),
        'grade_stats': grade_stats,
        'rankings': evaluations
    }
    json_file = os.path.join(output_path, f'strategy_ranking_{date_str}.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2, default=str)

    print(f"报告已生成：")
    print(f"  Markdown: {md_file}")
    print(f"  JSON: {json_file}")
    return md_file, json_file


def generate_from_json(json_file='output/strategy_data.json', output_path='reports/'):
    """从backtest输出的JSON文件生成报告"""
    if not os.path.exists(json_file):
        print(f"错误：找不到 {json_file}")
        return None

    with open(json_file, 'r', encoding='utf-8') as f:
        backtest_result = json.load(f)

    return generate_report(backtest_result, output_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='生成策略评估报告')
    parser.add_argument('--input', type=str, default='output/strategy_data.json',
                        help='输入的回测结果JSON文件')
    parser.add_argument('--output', type=str, default='reports/',
                        help='报告输出目录')
    args = parser.parse_args()

    generate_from_json(args.input, args.output)
