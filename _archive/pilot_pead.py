# -*- coding: utf-8 -*-
#!/usr/bin/env python3
'''
有界 PEAD 事件研究（业绩快报 express 的 yoy_net_profit 作惊喜代理）
=====================================================================
固定规则，不调参。样本内 2023-2024，样本外冻结 2022 只验一次。
  · 股票池：HS300 PIT 成分（index_weight as_of 逐年）
  · 事件：express 业绩快报发布日（ann_date），yoy_net_profit 为惊喜代理
  · 持有：20 个交易日，成本 0.15% 单边
  · 检验：top 五分位多头的均值 vs 随机置换分布（1000 次）
用法：
  python pilot_pead.py
  python pilot_pead.py --oos 2021      # 冻结另一年样本外
  python pilot_pead.py --no-cache
'''
import os, sys, json, argparse, time
from datetime import datetime, date, timedelta
sys.stdout.reconfigure(encoding='utf-8')
try:
    from dotenv import load_dotenv
    load_dotenv('.env')
except Exception:
    pass
import numpy as np
import pandas as pd
from config.tushare_config import get_tushare_pro
from data.tushare_helper import TushareHelper

IS_YEARS = (2023, 2024)
OOS_YEAR = 2022
HOLD_DAYS = 20
TOP = 0.2
N_PERM = 1000
COST = 0.0015
PRICE_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'pead_price_cache.json')


def full_code(c):
    c = str(c).strip().split('.')[0]
    if c.startswith(('5', '6', '9')):
        return c + '.SH'
    return c + '.SZ'


def get_members(helper, year):
    try:
        return set(helper.get_stock_pool(pool_type='hs300', as_of=f'{year}0101'))
    except Exception as e:
        print(f'  ! 拉取 HS300({year}) 失败: {e}')
        return set()


def fetch_express(pro, periods):
    frames = []
    for p in periods:
        try:
            df = pro.express(period=p)
        except Exception as e:
            print(f'  ! express({p}) 失败: {str(e)[:100]}')
            continue
        if df is None or len(df) == 0:
            continue
        cols = [c for c in ['ts_code', 'ann_date', 'end_date', 'yoy_net_profit', 'n_income'] if c in df.columns]
        frames.append(df[cols].copy())
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out['ann_date'] = out['ann_date'].astype(str)
    return out


def load_prices(ts, codes, start, end, use_cache=True):
    """拉取事件股 qfq 日线，返回 {code6: {YYYYMMDD: close}}。"""
    cache = {}
    if use_cache and os.path.exists(PRICE_CACHE):
        try:
            cache = json.load(open(PRICE_CACHE, encoding='utf-8'))
        except Exception:
            cache = {}
    out = {}
    for c in sorted(codes):
        if c in cache and cache[c]:
            out[c] = cache[c]
            continue
        try:
            df = ts.pro_bar(ts_code=full_code(c), adj='qfq', start_date=start, end_date=end)
            if df is not None and len(df) > 0:
                out[c] = {r['trade_date']: float(r['close']) for _, r in df.iterrows()}
            else:
                out[c] = {}
        except Exception as e:
            print(f'  ! 价格拉取 {c} 失败: {str(e)[:100]}')
            out[c] = {}
        time.sleep(0.05)  # 节流
    if use_cache and out:
        cache.update(out)
        os.makedirs(os.path.dirname(PRICE_CACHE), exist_ok=True)
        json.dump(cache, open(PRICE_CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    return out


def forward_returns(events, prices):
    """每个事件的 20 交易日 qfq 前瞻收益（扣成本）。"""
    rows = []
    for _, e in events.iterrows():
        pmap = prices.get(str(e['ts_code']).split('.')[0])
        if not pmap:
            continue
        dates = sorted(pmap.keys())
        if not dates:
            continue
        # 首个 >= ann_date 的交易日
        t0 = None
        for d in dates:
            if d >= e['ann_date']:
                t0 = d
                break
        if t0 is None:
            continue
        i0 = dates.index(t0)
        i1 = i0 + HOLD_DAYS
        if i1 >= len(dates):
            continue
        ret = pmap[dates[i1]] / pmap[dates[i0]] - 1 - COST * 2
        rows.append({'ts_code': str(e['ts_code']), 'ann_date': e['ann_date'],
                     'yoy': float(e['yoy']), 'fwd_ret': ret})
    return pd.DataFrame(rows)


def perm_test(df, seed=1):
    """top 五分位多头的均值 vs 随机置换 1000 次。返回 (mean_top, p)。"""
    y = df['yoy'].astype(float)
    r = df['fwd_ret'].astype(float)
    n = len(df)
    k = max(1, int(round(n * TOP)))
    thresh = y.quantile(1 - TOP)
    top_mask = y >= thresh
    obs = r[top_mask].mean()
    rng = np.random.default_rng(seed)
    perm = np.empty(N_PERM)
    yv = y.values; rv = r.values
    for i in range(N_PERM):
        sy = yv[rng.permutation(n)]
        mask = sy >= np.quantile(sy, 1 - TOP)
        perm[i] = rv[mask].mean()
    p = float((perm >= obs).mean())
    return obs, p, perm


def run(year, pro, helper, ts, use_cache, cache_ok=True):
    """跑某一年的事件研究，返回结果 dict。"""
    members = get_members(helper, year)
    if not members:
        print(f'  {year}: HS300 成分拉取为空，跳过')
        return None
    # express 报告期：该年公布的年报/一季报/中报/三季报
    periods = [
        f'{year-1}1231',  # 上一年年报（本年 1-4 月披露）
        f'{year}0331',
        f'{year}0630',
        f'{year}0930',
    ]
    ev = fetch_express(pro, periods)
    if ev.empty:
        print(f'  {year}: express 无数据，跳过')
        return None
    ev = ev[ev['ann_date'].astype(str).str.startswith(str(year))]
    ev = ev[ev['ts_code'].str.split('.').str[0].isin(members)]
    if ev.empty:
        print(f'  {year}: 过滤后无事件（HS300 内，{year} 披露，有 yoy）')
        return None
    # 惊喜代理用增长率而非绝对金额（yoy_net_profit 单位是元，直接用会偏大盘）
    ev = ev[ev['yoy_net_profit'].notna() & ev['n_income'].notna()]
    prior = ev['n_income'] - ev['yoy_net_profit']
    ev = ev[prior > 0].copy()
    if ev.empty:
        print(f'  {year}: 无正基数净利润事件')
        return None
    ev['yoy'] = (ev['yoy_net_profit'] / prior).astype(float)
    ev = ev[ev['yoy'].between(-2, 20)]
    if ev.empty:
        print(f'  {year}: 增长率过滤后无事件')
        return None
    prices = load_prices(ts, ev['ts_code'].str.split('.').str[0].tolist(),
                         f'{year-1}1101', f'{year}1231', use_cache)
    fr = forward_returns(ev, prices)
    if len(fr) < 20:
        print(f'  {year}: 有效事件过少（{len(fr)}），跳过')
        return None
    mean_top, p, perm = perm_test(fr)
    return {
        'year': year, 'n_events': len(fr),
        'mean_top_ret': float(mean_top),
        'p_value': float(p),
        'top_threshold_yoy': float(fr['yoy'].quantile(1 - TOP)),
    }


def main():
    ap = argparse.ArgumentParser(description='有界 PEAD 事件研究（express yoy 代理）')
    ap.add_argument('--oos', type=int, default=OOS_YEAR, help='样本外年份')
    ap.add_argument('--no-cache', action='store_true')
    args = ap.parse_args()
    pro = get_tushare_pro()
    helper = TushareHelper()
    import tushare as ts
    ts.set_token(os.environ.get('TUSHARE_TOKEN', ''))
    results = []
    for y in IS_YEARS:
        r = run(y, pro, helper, ts, not args.no_cache)
        if r:
            results.append(r)
    print('\n=== 样本内 PEAD 事件研究（top 20% 多头，20日，扣成本）===')
    for r in results:
        print(f"  {r['year']}: n={r['n_events']} 平均前瞻收益={r['mean_top_ret']*100:+.2f}%  "
              f"置换p={r['p_value']:.3f} (阈值yoy={r['top_threshold_yoy']:.1f})")
    if results:
        avg = np.mean([r['mean_top_ret'] for r in results])
        print(f"  样本内平均: {avg*100:+.2f}%")
    # 样本外冻结
    oos = run(args.oos, pro, helper, ts, not args.no_cache)
    print('\n=== 样本外冻结（只验一次）===')
    if oos:
        print(f"  {oos['year']}: n={oos['n_events']} 平均前瞻收益={oos['mean_top_ret']*100:+.2f}%"
              f" (阈值yoy={oos['top_threshold_yoy']:.1f})")
    else:
        print(f'  {args.oos}: 无有效结果')
    out = {'is': results, 'oos': oos, 'params': {'hold_days': HOLD_DAYS, 'top': TOP, 'cost': COST}}
    os.makedirs('output', exist_ok=True)
    json.dump(out, open('output/pead_results.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('\n结果已保存 -> output/pead_results.json')


if __name__ == '__main__':
    main()
