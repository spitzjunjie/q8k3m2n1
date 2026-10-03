# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
红利低波卫星 · 前向模拟盘（预注册第 5 节规定的下一步）
============================================================================
预注册：docs/knowledge/10-预注册-红利低波卫星.md（2014–2018 主检验已通过）。
前向检验：从 START（预注册与回测结果都已提交之后）起，用真实 ETF 复权价格逐日对照
  S = 510310 40% + 512890 20% + 511360 40%
  B = 510310 60% + 511360 40%（主线静态 60/40，按 IPS 建议工具）
两者 1/7 月首个交易日再平衡、单边 10bp，与回测同口径。

无状态：每次运行都从 START 起用全部已实现价格重算，不存在漏记或状态漂移；
没有任何信号，起始日收盘建仓不构成前视。≥ 6 个月（约 120 个交易日）后才可按 IPS 第 8 节评估。

用法：python satellite_paper_trade.py
结果：output/satellite_paper.json
"""
import os
import sys
import json
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

from asset_allocation_backtest import get_tushare_pro, run_portfolio, summarize, BOND_ANNUAL
from etf_selection_research import fetch_adj_close, cash_factors

START = '20261008'          # 2026 国庆休市后首个交易日；预注册与回测结果均已在此前提交
MIN_DAYS = 120              # 约 6 个月，达到前不做任何评估
COST = 0.001
OUT_FILE = os.path.join('output', 'satellite_paper.json')
W_S = {'510310.SH': 0.4, '512890.SH': 0.2, 'bond': 0.4}
W_B = {'510310.SH': 0.6, 'bond': 0.4}


def compute(hs, dv, cash):
    """给定三条复权价格，返回 (日期列表, S 净值, B 净值)；只用三者共同交易日。"""
    dates = sorted(set(hs) & set(dv) & set(cash))
    if len(dates) < 1:
        return [], [], []
    px = {'510310.SH': {d: hs[d] for d in dates}, '512890.SH': {d: dv[d] for d in dates}}
    f = cash_factors(cash, dates)
    eq_s, _ = run_portfolio(px, W_S, BOND_ANNUAL, dd_control=False, bond_factors=f, cost_rate=COST)
    eq_b, _ = run_portfolio({'510310.SH': px['510310.SH']}, W_B, BOND_ANNUAL, dd_control=False,
                            bond_factors=f, cost_rate=COST)
    return dates, eq_s, eq_b


def main():
    pro = get_tushare_pro()
    end = datetime.now().strftime('%Y%m%d')
    if end < START:
        print(f'前向检验起始日 {START} 尚未到达，跳过')
        return
    hs, _ = fetch_adj_close(pro, '510310.SH', START, end)
    dv, _ = fetch_adj_close(pro, '512890.SH', START, end)
    cash, _ = fetch_adj_close(pro, '511360.SH', START, end)
    if not (hs and dv and cash):
        print('数据缺失或尚无交易日，跳过')
        return
    dates, eq_s, eq_b = compute(hs, dv, cash)
    if len(dates) < 2:
        print(f'仅 {len(dates)} 个交易日，等待更多数据')
        return
    s, b = summarize('S', eq_s), summarize('B', eq_b)
    out = {'start': START, 'last': dates[-1], 'n_days': len(dates),
           'evaluable': len(dates) >= MIN_DAYS,
           'S': {'equity': eq_s[-1], 'total_return': s['total_return'], 'max_drawdown': s['max_drawdown']},
           'B': {'equity': eq_b[-1], 'total_return': b['total_return'], 'max_drawdown': b['max_drawdown']},
           'history': [{'date': d, 'S': round(x, 4), 'B': round(y, 4)}
                       for d, x, y in zip(dates, eq_s, eq_b, strict=True)]}
    os.makedirs('output', exist_ok=True)
    json.dump(out, open(OUT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'[红利低波卫星前向] {START} ~ {dates[-1]}，{len(dates)} 个交易日'
          f'（{"已满" if out["evaluable"] else "未满"} {MIN_DAYS} 日评估门槛）')
    print(f"S 40/20/40: 累计 {s['total_return'] * 100:+.2f}%  最大回撤 {s['max_drawdown'] * 100:.2f}%")
    print(f"B 60/40   : 累计 {b['total_return'] * 100:+.2f}%  最大回撤 {b['max_drawdown'] * 100:.2f}%")


if __name__ == '__main__':
    main()
