# -*- coding: utf-8 -*-
"""
PIT 回测试点脚本（第一步：数据基础层）
=====================================
目标：验证在 2150 积分（200次/分钟）下，能按 Point-in-Time 拉齐
HS300 成分 + 前复权日线 + 财务（按披露日），为后续 3 个策略回测铺路。

用法：
  python pilot_pit_backtest.py --fetch-test          # 只测数据抓取（小样本）
  python pilot_pit_backtest.py --universe 202406     # 拉某月 HS300 成分
"""
import os, sys, json, time, argparse
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np

from config.tushare_config import get_tushare_pro

WINDOW_START = '20240101'
WINDOW_END = '20241231'
INDEX_CODE = '000300.SH'   # 沪深300
INITIAL_CAPITAL = 30000.0
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pilot_cache')


def ensure_cache():
    os.makedirs(CACHE_DIR, exist_ok=True)


def cache_path(kind, key):
    return os.path.join(CACHE_DIR, f'{kind}_{key}.pkl')


def load_cache(kind, key):
    p = cache_path(kind, key)
    if os.path.exists(p):
        try:
            return pd.read_pickle(p)
        except Exception:
            return None
    return None


def save_cache(kind, key, obj):
    ensure_cache()
    pd.to_pickle(obj, cache_path(kind, key))


_last_call = [0.0]


def throttle():
    # 限流到约 3 次/秒（<200/分钟），避免被 Tushare 断连
    global _last_call
    elapsed = time.time() - _last_call[0]
    if elapsed < 0.35:
        time.sleep(0.35 - elapsed)
    _last_call[0] = time.time()


def safe_call(fn, retries=4):
    # 带重试的 API 调用，应对偶发断连
    for i in range(retries):
        throttle()
        try:
            return fn()
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))
    return None


def month_range(ym):
    d = datetime.strptime(ym + '01', '%Y%m%d')
    nxt = d.replace(day=28) + timedelta(days=4)
    end = (nxt - timedelta(days=nxt.day)).strftime('%Y%m%d')
    return d.strftime('%Y%m%d'), end


def get_monthly_universe(pro, ym):
    """某月的 HS300 成分（PIT）"""
    key = f'hs300_{ym}'
    cached = load_cache('universe', key)
    if cached is not None:
        return cached
    s, e = month_range(ym)
    df = safe_call(lambda: pro.index_weight(index_code=INDEX_CODE, start_date=s, end_date=e))
    if df is None or len(df) == 0:
        return []
    codes = sorted(set(str(c).split('.')[0] for c in df['con_code'] if c))
    save_cache('universe', key, pd.Series(codes))
    return codes


def fetch_daily_qfq(pro, ts_code, start, end):
    """前复权日线（raw * adj_factor / latest_adj_factor）"""
    key = f'{ts_code}_{start}_{end}'
    cached = load_cache('daily', key)
    if cached is not None:
        return cached
    raw = safe_call(lambda: pro.daily(ts_code=ts_code, start_date=start, end_date=end))
    if raw is None or raw.empty:
        return raw
    adj = safe_call(lambda: pro.adj_factor(ts_code=ts_code, start_date=start, end_date=end))
    if adj is None or adj.empty:
        save_cache('daily', key, raw)
        return raw
    latest = float(adj['adj_factor'].iloc[-1])
    m = raw.merge(adj[['trade_date', 'adj_factor']], on='trade_date', how='left')
    m['adj_factor'] = m['adj_factor'].ffill()
    for col in ['open', 'high', 'low', 'close', 'pre_close']:
        m[col] = m[col] * m['adj_factor'] / latest
    out = m.sort_values('trade_date').reset_index(drop=True)
    save_cache('daily', key, out)
    return out


def fetch_financial(pro, ts_code, start, end):
    """财务指标 + 利润表，带 ann_date（披露日），用于 PIT 过滤"""
    key = f'{ts_code}_{start}_{end}'
    cached = load_cache('fina', key)
    if cached is not None:
        return cached
    fina = safe_call(lambda: pro.fina_indicator(ts_code=ts_code, start_date=start, end_date=end))
    inc = safe_call(lambda: pro.income(ts_code=ts_code, start_date=start, end_date=end))
    out = {'fina': fina, 'income': inc}
    save_cache('fina', key, out)
    return out


def fetch_test(pro):
    """小样本抓取测试：1 个月成分 + 3 只票的日线/财务，测限流与积分"""
    ensure_cache()
    ym = '202406'
    t0 = time.time()
    codes = get_monthly_universe(pro, ym)
    print(f"[1] {ym} HS300 成分: {len(codes)} 只, {time.time()-t0:.1f}s")

    sample = codes[:3]
    for c in sample:
        t1 = time.time()
        daily = fetch_daily_qfq(pro, c + '.SH' if c.startswith('6') else c + '.SZ',
                                WINDOW_START, WINDOW_END)
        fina = fetch_financial(pro, c + '.SH' if c.startswith('6') else c + '.SZ',
                               WINDOW_START, WINDOW_END)
        n_daily = len(daily) if daily is not None else 0
        n_fina = len(fina['fina']) if fina.get('fina') is not None else 0
        n_inc = len(fina['income']) if fina.get('income') is not None else 0
        print(f"[2] {c}: 日线 {n_daily} 行, 财务 {n_fina} 行, 利润表 {n_inc} 行, {time.time()-t1:.1f}s")

    # 检查财务的 ann_date（披露日）字段存在
    c0 = sample[0]
    ts0 = c0 + '.SH' if c0.startswith('6') else c0 + '.SZ'
    fina0 = fetch_financial(pro, ts0, WINDOW_START, WINDOW_END)
    if fina0.get('fina') is not None and 'ann_date' in fina0['fina'].columns:
        print(f"[3] fina_indicator 含 ann_date 字段 ✅")
    if fina0.get('income') is not None and 'ann_date' in fina0['income'].columns:
        print(f"[3] income 含 ann_date 字段 ✅")
    print(f"\n总耗时 {time.time()-t0:.1f}s（含缓存写盘）")

# -*- coding: utf-8 -*-
# ============ 回测引擎（月频调仓，简单但正确） ============

def to_ts_code(c):
    return c + ('.SH' if c.startswith('6') else '.SZ')


def fetch_daily_basic(pro, ts_code, start, end):
    key = f'{ts_code}_{start}_{end}'
    cached = load_cache('basic', key)
    if cached is not None:
        return cached
    df = safe_call(lambda: pro.daily_basic(ts_code=ts_code, start_date=start, end_date=end))
    save_cache('basic', key, df)
    return df


def close_series(daily_df):
    """返回 date->close 的 dict（前复权）"""
    if daily_df is None or daily_df.empty:
        return {}
    return dict(zip(daily_df['trade_date'].astype(str), daily_df['close'].astype(float)))


def strategy_momentum(daily_map, universe, date, prev_date, top_n=10):
    """均线多头排列：用 20 日动量近似（close/close_20d - 1）"""
    scored = []
    for c in universe:
        s = daily_map.get(c)
        if not s or date not in s or prev_date not in s:
            continue
        if s[prev_date] <= 0:
            continue
        scored.append((c, s[date] / s[prev_date] - 1.0))
    scored.sort(key=lambda x: -x[1])
    return [c for c, _ in scored[:top_n]]


def strategy_net_profit_growth(income_map, universe, date, top_n=10):
    """净利润增速：ann_date <= date 的最近一期，YoY 净利润同比"""
    scored = []
    for c in universe:
        df = income_map.get(c)
        if df is None or df.empty or 'ann_date' not in df.columns:
            continue
        d = df[df['ann_date'].astype(str) <= date]
        if d.empty:
            continue
        d = d.sort_values('end_date')
        # 取最近两期，算净利润同比
        latest = d.iloc[-1]
        prev = d.iloc[-2] if len(d) >= 2 else None
        n = latest.get('n_income_attr_p') if 'n_income_attr_p' in latest.index else latest.get('n_income')
        if n is None or not isinstance(n, (int, float)):
            continue
        pn = prev.get('n_income_attr_p') if prev is not None and 'n_income_attr_p' in prev.index else (prev.get('n_income') if prev is not None else None)
        if prev is not None and pn is not None and isinstance(pn, (int, float)) and pn != 0:
            g = (n - pn) / abs(pn)
        else:
            g = 0.0
        scored.append((c, g))
    scored.sort(key=lambda x: -x[1])
    return [c for c, _ in scored[:top_n]]


def strategy_low_pe(basic_map, universe, date, top_n=10):
    """低PE：pe_ttm 最低（越低越好，取负数排序）"""
    scored = []
    for c in universe:
        df = basic_map.get(c)
        if df is None or df.empty:
            continue
        row = df[df['trade_date'].astype(str) == date]
        if row.empty:
            continue
        pe = row.iloc[0].get('pe_ttm') or row.iloc[0].get('pe')
        if pe is None or not isinstance(pe, (int, float)) or pe <= 0:
            continue
        scored.append((c, -pe))
    scored.sort(key=lambda x: -x[1])
    return [c for c, _ in scored[:top_n]]


def simulate(daily_map, universe_by_month, trading_dates, pick_fn, top_n=10, rebalance_days=20):
    """跑一个组合：pick_fn(universe, date, prev_date)->持仓列表，返回权益曲线"""
    capital = INITIAL_CAPITAL
    holdings = {}
    equity = []
    for i, d in enumerate(trading_dates):
        universe = list(universe_by_month.get(d[:6], []))
        if i % rebalance_days == 0:
            prev_date = trading_dates[max(0, i - rebalance_days)]
            picked = pick_fn(universe, d, prev_date)
            for c in list(holdings.keys()):
                px = daily_map.get(c, {}).get(d)
                if px is not None and px > 0:
                    capital += holdings[c] * px
                del holdings[c]
            valid = [c for c in picked if daily_map.get(c, {}).get(d, 0) > 0]
            if valid:
                per = capital / len(valid)
                for c in valid:
                    px = daily_map[c][d]
                    holdings[c] = per / px
                    capital -= per + per * 0.0015
        val = capital + sum(holdings[c] * daily_map.get(c, {}).get(d, 0.0) for c in holdings)
        equity.append({'date': d, 'value': val})
    return equity


def fetch_report_rc(pro, ts_code, start, end):
    key = f'{ts_code}_{start}_{end}'
    cached = load_cache('rc', key)
    if cached is not None:
        return cached
    df = safe_call(lambda: pro.report_rc(ts_code=ts_code, start_date=start, end_date=end))
    save_cache('rc', key, df)
    return df


def fetch_all_report_rc(pro, start, end, batch_days=10):
    """按日期批量抓全市场研报（report_rc 限流 1次/分钟），返回合并 DataFrame"""
    import pandas as pd
    from datetime import datetime, timedelta
    d = datetime.strptime(start, '%Y%m%d')
    e = datetime.strptime(end, '%Y%m%d')
    frames = []
    while d <= e:
        d2 = min(d + timedelta(days=batch_days - 1), e)
        key = 'rcall_%s_%s' % (d.strftime('%Y%m%d'), d2.strftime('%Y%m%d'))
        cached = load_cache('rcall', key)
        if cached is None:
            cached = safe_call(lambda: pro.report_rc(start_date=d.strftime('%Y%m%d'), end_date=d2.strftime('%Y%m%d')))
            save_cache('rcall', key, cached)
            time.sleep(60)  # report_rc 1次/分钟
        if cached is not None and len(cached):
            frames.append(cached)
        print(f'  研报批次 {d.strftime("%Y%m%d")}-{d2.strftime("%Y%m%d")}: {len(cached) if cached is not None else 0} 行', flush=True)
        d = d2 + timedelta(days=1)
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def run_pead_surprise(daily_map, income_map, rc_map, trading_dates, top_n=5, hold_days=40, max_positions=10):
    """PEAD：surprise = (实际EPS - 一致预期EPS中位数)/|一致预期|，事件驱动"""
    from bisect import bisect_left
    from collections import defaultdict
    import statistics
    events = []
    for c, df in income_map.items():
        if df is None or df.empty:
            continue
        rc = rc_map.get(c)
        if rc is None or rc.empty:
            continue
        # 过滤个股研报 + 有效EPS
        if 'report_type' in rc.columns:
            rc = rc[rc['report_type'] == '个股']
        if 'eps' in rc.columns:
            rc = rc[rc['eps'].notna()]
        if rc.empty:
            continue
        # 按 quarter 聚合一致预期 EPS 中位数
        cons = {}
        for q, grp in rc.groupby('quarter'):
            eps = [float(x) for x in grp['eps'] if x is not None]
            if len(eps) >= 3:  # 至少3家机构才算一致预期
                cons[q] = statistics.median(eps)
        if not cons:
            continue
        # 逐条实际财报算惊喜
        df = df.sort_values('end_date')
        for cur in df.to_dict('records'):
            end = str(cur.get('end_date', '')).replace('-', '')
            if len(end) != 8:
                continue
            q = end[:4] + 'Q' + str(int(end[4:6]) // 3)
            c0 = cons.get(q)
            if c0 is None or c0 == 0:
                continue
            ae = cur.get('basic_eps')
            if ae is None:
                continue
            try:
                ae = float(ae)
            except (TypeError, ValueError):
                continue
            surprise = (ae - c0) / abs(c0)
            surprise = max(-2.0, min(2.0, surprise))
            ann = str(cur.get('ann_date', '')).replace('-', '')
            j = bisect_left(trading_dates, ann)
            if j < len(trading_dates):
                events.append((trading_dates[j], c, surprise))
    by_date = defaultdict(list)
    for bd, c, g in events:
        by_date[bd].append((c, g))
    capital = INITIAL_CAPITAL
    positions = {}
    equity = []
    date_idx = {d: i for i, d in enumerate(trading_dates)}
    per_pos = INITIAL_CAPITAL / max_positions
    for d in trading_dates:
        for c in list(positions.keys()):
            held = date_idx[d] - date_idx[positions[c]['buy_date']]
            if held >= hold_days:
                px = daily_map.get(c, {}).get(d)
                if px is not None and px > 0:
                    capital += positions[c]['qty'] * px
                del positions[c]
        if len(positions) < max_positions:
            seen_codes = set(positions.keys())
            cands = []
            for c, g in by_date.get(d, []):
                if c not in seen_codes:
                    seen_codes.add(c)
                    cands.append((c, g))
            cands.sort(key=lambda x: -x[1])
            for c, g in cands[:top_n]:
                if len(positions) >= max_positions:
                    break
                px = daily_map.get(c, {}).get(d)
                if px is None or px <= 0:
                    continue
                amt = min(per_pos, capital)
                if amt <= 0:
                    break
                positions[c] = {'qty': amt / px, 'buy_date': d, 'buy_price': px}
                capital -= amt + amt * 0.0015
        val = capital + sum(p['qty'] * daily_map.get(c, {}).get(d, p['buy_price']) for c, p in positions.items())
        equity.append({'date': d, 'value': val})
    return equity, events


def run_pead(daily_map, income_map, trading_dates, top_n=5, hold_days=40, max_positions=10):
    """事件驱动 PEAD：披露日买入增速 top_n，持有 hold_days 天。返回 (equity, events)"""
    from bisect import bisect_left
    from collections import defaultdict
    # 预计算事件 (buy_date, code, growth)
    events = []
    for c, df in income_map.items():
        if df is None or df.empty:
            continue
        df = df.sort_values('end_date')
        rows = df.to_dict('records')
        by_end = {}
        for r in rows:
            e = str(r.get('end_date', '')).replace('-', '')
            if e:
                by_end[e] = r
        for cur in rows:
            cur_end = str(cur.get('end_date', '')).replace('-', '')
            if len(cur_end) != 8:
                continue
            prev_end = str(int(cur_end[:4]) - 1) + cur_end[4:]
            prev = by_end.get(prev_end)
            if prev is None:
                continue
            ann = cur.get('ann_date')
            cn = cur.get('n_income_attr_p') if 'n_income_attr_p' in cur else cur.get('n_income')
            pn = prev.get('n_income_attr_p') if 'n_income_attr_p' in prev else prev.get('n_income')
            if ann is None or cn is None or pn is None:
                continue
            try:
                cn, pn = float(cn), float(pn)
            except (TypeError, ValueError):
                continue
            if pn == 0:
                continue
            g = (cn - pn) / abs(pn)
            if abs(pn) < 1e7:  # 上一期净利润 <1000万，增速无意义，跳过
                continue
            g = max(-2.0, min(2.0, g))  # winsorize 到 ±200%
            a = str(ann).replace('-', '')
            j = bisect_left(trading_dates, a)
            if j < len(trading_dates):
                events.append((trading_dates[j], c, g))
    by_date = defaultdict(list)
    for bd, c, g in events:
        by_date[bd].append((c, g))

    capital = INITIAL_CAPITAL
    positions = {}
    equity = []
    date_idx = {d: i for i, d in enumerate(trading_dates)}
    per_pos = INITIAL_CAPITAL / max_positions
    for d in trading_dates:
        for c in list(positions.keys()):
            held = date_idx[d] - date_idx[positions[c]['buy_date']]
            if held >= hold_days:
                px = daily_map.get(c, {}).get(d)
                if px is not None and px > 0:
                    capital += positions[c]['qty'] * px
                del positions[c]
        if len(positions) < max_positions:
            # 按股票去重（income 有重复报告期行，会导致同一股票重复扣款）
            seen_codes = set(positions.keys())
            cands = []
            for c, g in by_date.get(d, []):
                if c not in seen_codes:
                    seen_codes.add(c)
                    cands.append((c, g))
            cands.sort(key=lambda x: -x[1])
            for c, g in cands[:top_n]:
                if len(positions) >= max_positions:
                    break
                px = daily_map.get(c, {}).get(d)
                if px is None or px <= 0:
                    continue
                amt = min(per_pos, capital)
                if amt <= 0:
                    break
                positions[c] = {'qty': amt / px, 'buy_date': d, 'buy_price': px}
                capital -= amt + amt * 0.0015
        val = capital + sum(p['qty'] * daily_map.get(c, {}).get(d, p['buy_price']) for c, p in positions.items())
        equity.append({'date': d, 'value': val})
    return equity, events


def _close_lag(daily_map, c, date, n):
    s = daily_map.get(c)
    if not s:
        return None
    dates = sorted(s.keys())
    if date not in dates:
        return None
    idx = dates.index(date)
    if idx < n:
        return None
    return s[dates[idx - n]]


def strategy_low_vol(daily_map, universe, date, prev_date, top_n=10):
    """低波动率：近20日日收益率标准差最小"""
    import statistics
    scored = []
    for c in universe:
        s = daily_map.get(c)
        if not s:
            continue
        dates = sorted(s.keys())
        if date not in dates:
            continue
        idx = dates.index(date)
        if idx < 20:
            continue
        window = [s[d] for d in dates[idx-20:idx+1]]
        if any(v <= 0 for v in window):
            continue
        rets = [window[i]/window[i-1] - 1 for i in range(1, len(window))]
        if len(rets) < 10:
            continue
        vol = statistics.stdev(rets)
        scored.append((c, -vol))  # 低波动优先
    scored.sort(key=lambda x: -x[1])
    return [c for c, _ in scored[:top_n]]


def strategy_quality(fina_map, universe, date, top_n=10):
    """质量：最新披露的 ROE 最高"""
    scored = []
    for c in universe:
        df = fina_map.get(c)
        if df is None or df.empty:
            continue
        if 'ann_date' not in df.columns or 'roe' not in df.columns:
            continue
        d = df[df['ann_date'].astype(str) <= date]
        if d.empty:
            continue
        d = d.sort_values('end_date')
        roe = d.iloc[-1].get('roe')
        if roe is None:
            continue
        try:
            roe = float(roe)
        except (TypeError, ValueError):
            continue
        scored.append((c, roe))
    scored.sort(key=lambda x: -x[1])
    return [c for c, _ in scored[:top_n]]


def strategy_reversal(daily_map, universe, date, prev_date, top_n=10):
    """短期反转：近20日收益最低（超跌反弹）"""
    scored = []
    for c in universe:
        p0 = daily_map.get(c, {}).get(date)
        p1 = _close_lag(daily_map, c, date, 20)
        if p0 is None or p1 is None or p1 <= 0:
            continue
        r = p0 / p1 - 1.0
        scored.append((c, -r))  # 越跌越优先
    scored.sort(key=lambda x: -x[1])
    return [c for c, _ in scored[:top_n]]


def run_backtest(pro, start, end, top_n=10, rebalance_days=20):
    """月频调仓回测：3 个策略各自 top_n 等权，含成本，返回各策略权益曲线与指标"""
    import numpy as np
    from core.metrics import compute, RISK_FREE_ANNUAL

    # 1. 交易日历（用 HS300 指数日线）
    idx = safe_call(lambda: pro.index_daily(ts_code=INDEX_CODE, start_date=start, end_date=end))
    if idx is None or idx.empty:
        print('取指数交易日失败')
        return {}
    trading_dates = sorted(idx['trade_date'].astype(str).tolist())

    # 2. 月度股票池（PIT）
    months = sorted(set(d[:6] for d in trading_dates))
    universe_by_month = {}
    for ym in months:
        universe_by_month[ym] = get_monthly_universe(pro, ym)

    # 3. 预取数据（所有出现过的股票）
    all_codes = sorted(set(c for lst in universe_by_month.values() for c in lst))
    print(f'共 {len(all_codes)} 只成分股，预取日线+估值+财务...', flush=True)
    daily_map, basic_map, income_map, fina_map = {}, {}, {}, {}
    for i, c in enumerate(all_codes):
        ts = to_ts_code(c)
        daily_map[c] = close_series(fetch_daily_qfq(pro, ts, start, end))
        basic_map[c] = fetch_daily_basic(pro, ts, start, end)
        fin_start = str(int(start[:4]) - 1) + '0101'  # 往前多拉一年，供净利润同比
        fin = fetch_financial(pro, ts, fin_start, end)
        income_map[c] = fin.get('income') if fin else None
        fina_map[c] = fin.get('fina') if fin else None
        if (i + 1) % 30 == 0:
            print(f'  预取 {i+1}/{len(all_codes)}', flush=True)
            time.sleep(1.0)

    strategies = {
        '低波动率': strategy_low_vol,
        '质量因子': strategy_quality,
        '短期反转': strategy_reversal,
    }

    results = {}
    for name, sig_fn in strategies.items():
        capital = INITIAL_CAPITAL
        holdings = {}  # code -> 持仓数量（股）
        equity = []
        last_rebalance_idx = -1
        for i, d in enumerate(trading_dates):
            ym = d[:6]
            universe = universe_by_month.get(ym, [])
            # 调仓（每 rebalance_days 天或月初）
            if i % rebalance_days == 0:
                prev_idx = max(0, i - rebalance_days)
                prev_date = trading_dates[prev_idx]
                if name == '质量因子':
                    picked = sig_fn(fina_map, universe, d, top_n)
                else:  # 低波动率 / 短期反转
                    picked = sig_fn(daily_map, universe, d, prev_date, top_n)
                # 卖出旧持仓（按当日收盘价，计入现金）
                for c in list(holdings.keys()):
                    px = daily_map.get(c, {}).get(d)
                    if px is not None and px > 0:
                        capital += holdings[c] * px
                    del holdings[c]
                # 买入新持仓（等权全仓 + 单边成本 0.15%）
                valid = [c for c in picked if daily_map.get(c, {}).get(d, 0) > 0]
                if valid:
                    per = capital / len(valid)
                    for c in valid:
                        px = daily_map[c][d]
                        qty = per / px
                        holdings[c] = qty
                        capital -= per + per * 0.0015
            # 日终估值：现金 + 持仓市值
            val = capital + sum(holdings[c] * daily_map.get(c, {}).get(d, 0.0) for c in holdings)
            equity.append({'date': d, 'value': val})

        if equity:
            perf = compute([e['value'] for e in equity], initial_capital=INITIAL_CAPITAL,
                           periods_per_year=252, risk_free_annual=RISK_FREE_ANNUAL)
            results[name] = {
                'equity': equity,
                'total_return': perf.total_return,
                'sharpe': perf.sharpe,
                'max_drawdown': perf.max_drawdown,
                'n_days': perf.n_days,
            }
    # 4. 基准：买入持有 HS300 + 随机选股
    import random
    bh = float(idx['close'].iloc[-1]) / float(idx['close'].iloc[0]) - 1.0
    random.seed(42)
    rand_rets = []
    for _ in range(1000):
        eq = simulate(daily_map, universe_by_month, trading_dates,
                      lambda u, d, pd: random.sample(u, min(top_n, len(u))),
                      top_n=top_n, rebalance_days=rebalance_days)
        if eq:
            rand_rets.append(eq[-1]['value'] / INITIAL_CAPITAL - 1.0)
    rand_rets.sort()
    # 每个策略的置换检验 p 值（随机组合收益 >= 该策略收益的比例）
    for name, r in results.items():
        if name.startswith('_'):
            continue
        tr = r['total_return']
        p = (1 + sum(1 for x in rand_rets if x >= tr)) / (1 + len(rand_rets))
        r['p_value_vs_random'] = p
    results['_基准'] = {
        'buy_hold_hs300': bh,
        'random_median': rand_rets[len(rand_rets)//2] if rand_rets else 0.0,
        'random_p90': rand_rets[int(len(rand_rets)*0.9)] if rand_rets else 0.0,
        'random_p95': rand_rets[int(len(rand_rets)*0.95)] if rand_rets else 0.0,
    }

    return results


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch-test', action='store_true')
    ap.add_argument('--universe', type=str, default=None)
    ap.add_argument('--backtest', action='store_true')
    ap.add_argument('--pead', action='store_true')
    ap.add_argument('--pead-surprise', action='store_true')
    ap.add_argument('--start', type=str, default=WINDOW_START)
    ap.add_argument('--end', type=str, default=WINDOW_END)
    args = ap.parse_args()
    if not os.environ.get('TUSHARE_TOKEN'):
        from dotenv import load_dotenv
        load_dotenv()
    pro = get_tushare_pro()
    if not os.environ.get('TUSHARE_TOKEN'):
        print('请先设置 TUSHARE_TOKEN')
        sys.exit(1)
    if args.universe:
        codes = get_monthly_universe(pro, args.universe)
        print(f'{args.universe} HS300 成分: {len(codes)} 只')
        print(codes[:20])
    elif args.pead_surprise:
        from core.metrics import compute, RISK_FREE_ANNUAL
        idx = safe_call(lambda: pro.index_daily(ts_code=INDEX_CODE, start_date=args.start, end_date=args.end))
        trading_dates = sorted(idx['trade_date'].astype(str).tolist())
        months = sorted(set(d[:6] for d in trading_dates))
        all_codes = sorted(set(c for ym in months for c in get_monthly_universe(pro, ym)))
        print(f'共 {len(all_codes)} 只成分股，加载缓存+抓研报...', flush=True)
        daily_map = {c: close_series(fetch_daily_qfq(pro, to_ts_code(c), args.start, args.end)) for c in all_codes}
        fin_start = str(int(args.start[:4]) - 1) + '0101'
        income_map = {}
        for c in all_codes:
            fin = fetch_financial(pro, to_ts_code(c), fin_start, args.end)
            income_map[c] = fin.get('income') if fin else None
        fina_map[c] = fin.get('fina') if fin else None
        rc_all = fetch_all_report_rc(pro, fin_start, args.end)
        rc_map = {}
        if rc_all is not None:
            for ts, grp in rc_all.groupby('ts_code'):
                rc_map[str(ts).split('.')[0]] = grp
        equity, events = run_pead_surprise(daily_map, income_map, rc_map, trading_dates)
        perf = compute([e['value'] for e in equity], initial_capital=INITIAL_CAPITAL, periods_per_year=252, risk_free_annual=RISK_FREE_ANNUAL)
        print(f'\nPEAD-surprise: 收益 {perf.total_return*100:+.1f}%  夏普 {perf.sharpe:+.2f}  回撤 {perf.max_drawdown*100:.1f}%  事件数 {len(events)}')
        print(f'对比: 买入持有HS300 -1.2% | 随机月频中位 -0.2% | 随机p95 +27.3%')
    elif args.pead:
        from core.metrics import compute, RISK_FREE_ANNUAL
        idx = safe_call(lambda: pro.index_daily(ts_code=INDEX_CODE, start_date=args.start, end_date=args.end))
        trading_dates = sorted(idx['trade_date'].astype(str).tolist())
        months = sorted(set(d[:6] for d in trading_dates))
        all_codes = sorted(set(c for ym in months for c in get_monthly_universe(pro, ym)))
        print(f'共 {len(all_codes)} 只成分股，加载缓存...', flush=True)
        daily_map = {c: close_series(fetch_daily_qfq(pro, to_ts_code(c), args.start, args.end)) for c in all_codes}
        fin_start = str(int(args.start[:4]) - 1) + '0101'
        income_map = {}
        for c in all_codes:
            fin = fetch_financial(pro, to_ts_code(c), fin_start, args.end)
            income_map[c] = fin.get('income') if fin else None
        fina_map[c] = fin.get('fina') if fin else None
        equity, events = run_pead(daily_map, income_map, trading_dates)
        perf = compute([e['value'] for e in equity], initial_capital=INITIAL_CAPITAL, periods_per_year=252, risk_free_annual=RISK_FREE_ANNUAL)
        print(f'\nPEAD 事件驱动: 收益 {perf.total_return*100:+.1f}%  夏普 {perf.sharpe:+.2f}  回撤 {perf.max_drawdown*100:.1f}%  事件数 {len(events)}')
        print(f'对比: 买入持有HS300 -1.2% | 随机月频中位 -0.2% | 随机p95 +27.3%')
    elif args.backtest:
        import json
        res = run_backtest(pro, args.start, args.end)
        bench = res.pop('_基准', None)
        print('\n========== 回测结果 ==========')
        for name, r in res.items():
            pv = r.get('p_value_vs_random')
            pstr = f'  p值={pv:.3f}' if pv is not None else ''
            print(f"{name}: 收益 {r['total_return']*100:+.1f}%  夏普 {r['sharpe']:+.2f}  回撤 {r['max_drawdown']*100:.1f}%  天数 {r['n_days']}{pstr}")
        if bench:
            print(f"\n基准: 买入持有HS300 {bench['buy_hold_hs300']*100:+.1f}% | 随机中位 {bench['random_median']*100:+.1f}% | 随机p90 {bench['random_p90']*100:+.1f}% | 随机p95 {bench['random_p95']*100:+.1f}%")
            res['_基准'] = bench
        # 保存结果
        with open('pilot_results.json', 'w', encoding='utf-8') as f:
            json.dump({k: {kk: vv for kk, vv in v.items() if kk != 'equity'} for k, v in res.items()},
                      f, ensure_ascii=False, indent=2)
        print('\n结果已存 pilot_results.json')
    else:
        fetch_test(pro)