# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
配对交易前提检验：协整检验（Engle-Granger）
============================================
现有 strategies/cointegration_pairs_strategy.py 把 β 硬编码=1，且从未做协整检验。
本脚本回答两个问题：
  1. 这 5 个"同行业龙头对"到底协不协整？（Engle-Granger 检验，p<0.05 才成立）
  2. β 真实是多少？硬编码 β=1 的误差有多大？

方法：前复权日线 3 年 → log 价格 → OLS 得 β → 残差 ADF 检验（statsmodels coint）
"""

import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
from statsmodels.tsa.stattools import coint

try:
    from dotenv import load_dotenv
    load_dotenv('.env')
except Exception:
    pass

try:
    from config.tushare_config import get_tushare_pro
except Exception:
    import tushare as ts
    def get_tushare_pro():
        ts.set_token(os.environ.get('TUSHARE_TOKEN', ''))
        return ts.pro_api()

PAIRS = [
    ('600519.SH', '贵州茅台', '000858.SZ', '五粮液', '白酒'),
    ('600036.SH', '招商银行', '000001.SZ', '平安银行', '银行'),
    ('000333.SZ', '美的集团', '600690.SH', '海尔智家', '家电'),
    ('600276.SH', '恒瑞医药', '603259.SH', '药明康德', '医药'),
    ('601012.SH', '隆基绿能', '002129.SZ', 'TCL中环', '光伏'),
]

START, END = '20210101', '20241231'
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'pairs_cache.json')


def fetch(pro, ts_code):
    df = pro.daily(ts_code=ts_code, start_date=START, end_date=END, adj='qfq')
    if df is None or df.empty:
        return {'dates': [], 'close': []}
    df = df.sort_values('trade_date')
    return {'dates': df['trade_date'].tolist(), 'close': df['close'].astype(float).tolist()}


def align(a, b):
    da = dict(zip(a['dates'], a['close']))
    db = dict(zip(b['dates'], b['close']))
    common = sorted(set(da) & set(db))
    return [da[d] for d in common], [db[d] for d in common]


def half_life(spread):
    """AR(1) 半衰期：价差偏离均值后回补一半所需交易日数。"""
    s = spread - spread.mean()
    x, y = s[:-1], s[1:]
    lam = float(np.dot(x, y) / np.dot(x, x))
    if lam <= 0 or lam >= 1:
        return float('inf')
    return -np.log(2) / np.log(lam)


def main():
    pro = get_tushare_pro()
    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}
    print('=' * 86)
    print(f'协整检验窗口：{START} ~ {END}（前复权日线，Engle-Granger，p<0.05 判为协整）')
    print('=' * 86)

    rows = []
    for a, na, b, nb, ind in PAIRS:
        for code in (a, b):
            if code not in cache:
                print(f'拉取 {code} ...')
                cache[code] = fetch(pro, code)
        pa, pb = align(cache[a], cache[b])
        n = len(pa)
        if n < 300:
            print(f'{na}-{nb}: 数据不足（{n} 行）')
            continue
        la = np.log(np.array(pa))
        lb = np.log(np.array(pb))
        beta = float(np.polyfit(lb, la, 1)[0])
        spread = la - beta * lb
        t, p, crit = coint(la, lb)
        corr = float(np.corrcoef(np.diff(la), np.diff(lb))[0, 1])
        hl = half_life(spread)
        verdict = '协整 ✓' if p < 0.05 else '不协整 ✗'
        rows.append({'pair': f'{na}-{nb}', 'industry': ind, 'beta': beta,
                     'corr': corr, 'p': float(p), 'half_life': hl})
        hl_s = '∞' if hl == float('inf') else f'{hl:.0f}天'
        print(f'  {na}-{nb} [{ind}]  样本={n}  收益相关={corr:+.2f}  '
              f'β={beta:+.3f}  EG-p值={p:.3f}  半衰期={hl_s}  → {verdict}')

    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print()
    print('β 偏离 1 的程度（原策略硬编码 β=1 的误差）：')
    for r in rows:
        bias = abs(r['beta'] - 1)
        print(f"  {r['pair']:<14} β={r['beta']:+.3f}  偏离1 = {bias * 100:.0f}%  "
              f"{'⚠️ 不可忽略' if bias > 0.2 else ''}")

    co_ok = [r for r in rows if r['p'] < 0.05]
    print(f"\n结论：{len(co_ok)}/{len(rows)} 对通过协整检验。"
          f"{'这 5 对的统计套利前提成立' if len(co_ok) >= 3 else '多数对不协整，原策略前提存疑'}。")


if __name__ == '__main__':
    main()
