# -*- coding: utf-8 -*-
"""
极速历史回测引擎 v2.0
25个策略全覆盖 - AKShare数据源（无速率限制）
"""

import json
import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

BENCHMARK_START = datetime(2026, 5, 26)
INITIAL_CAPITAL = 30000
MAX_HOLDINGS = 3


# === 信号函数 ===
def _safe(k):
    """安全获取DataFrame数据"""
    if not isinstance(k, pd.DataFrame) or k.empty:
        return None, None
    if 'close' not in k.columns:
        return None, None
    try:
        c = k['close'].values
        v = k['volume'].values if 'volume' in k.columns else None
        return c, v
    except:
        return None, None


def _price_percentile(c, n=20):
    """计算价格在n天内的百分位"""
    if c is None or len(c) < n: return 50
    low = c[-n:].min()
    high = c[-n:].max()
    if high == low: return 50
    return (c[-1] - low) / (high - low) * 100


def _ma(c, period):
    """计算移动平均"""
    if c is None or len(c) < period: return None
    return c[-period:].mean()


def _ret(c, days):
    """计算n日收益率"""
    if c is None or len(c) <= days: return 0
    return (c[-1] / c[-days-1] - 1) * 100


# === 信号定义 ===
def _auction_signal(k):
    """集合竞价控盘（机构控盘特征：量能萎缩+价格稳定）"""
    c, v = _safe(k)
    if c is None or v is None or len(v) < 20: return False, ""
    # 缩量整理（控盘特征）
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    # 价格稳定（波动小）
    price_vol = c[-5:].std() / c[-5:].mean()
    # 趋势向上
    trend = c[-1] > _ma(c, 5)
    if vol_ratio < 0.8 and price_vol < 0.02 and trend:
        return True, f"竞价控盘缩量{vol_ratio:.1f}倍"
    return False, ""


def _after_hours_signal(k):
    """尾盘动量"""
    c, _ = _safe(k)
    if c is None or len(c) < 10: return False, ""
    if c[-1] > _ma(c, 10):
        ret5 = _ret(c, 5)
        if ret5 > 2: return True, f"尾盘强势+{ret5:.1f}%"
    return False, ""


def _davis_signal(k):
    """戴维斯双击（低估+成长：价格低位+稳健增长）"""
    c, v = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    # 价格低位(<40%) 且 增长适中(0-15%)
    if pct < 40 and 0 < ret10 < 15:
        return True, f"戴维斯低位{pct:.0f}%增长{ret10:.1f}%"
    return False, ""


def _turnaround_signal(k):
    """困境反转（超跌后企稳）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    ret10 = _ret(c, 10)
    if c[-1] > _ma(c, 20) and -10 < ret10 < -3:
        return True, f"超跌反弹{ret10:.1f}%"
    return False, ""


def _shareholder_signal(k):
    """股东户数减少（缩量+控盘）"""
    _, v = _safe(k)
    if v is None or len(v) < 20: return False, ""
    ratio = v[-5:].mean() / v[-20:].mean()
    if ratio < 0.75: return True, f"量能萎缩{ratio:.1f}倍"
    return False, ""


def _limit_up_signal(k):
    """涨停封单强"""
    c, _ = _safe(k)
    if c is None or len(c) < 2: return False, ""
    ret = _ret(c, 1)
    if ret >= 9.8: return True, f"涨停+{ret:.1f}%"
    return False, ""


def _limit_down_signal(k):
    """跌停撬板（强势撬板：低开后快速反弹收红）"""
    c, _ = _safe(k)
    if c is None or len(c) < 5: return False, ""
    ret1 = _ret(c, 1)
    ret3 = _ret(c, 3)
    # 今日小跌(-2%~0%) + 近3日有反弹
    if -2 < ret1 < 0 and ret3 > 0 and c[-1] > _ma(c, 5):
        return True, f"撬板反弹{ret3:.1f}%"
    return False, ""


def _lockup_signal(k):
    """限售解禁超卖"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    if c[-1] < _ma(c, 20) * 0.88: return True, "解禁超卖"
    return False, ""


def _hot_money_signal(k):
    """游资席位（大幅放量）"""
    _, v = _safe(k)
    if v is None or len(v) < 5: return False, ""
    ratio = v[-1] / v[-5:].mean()
    if ratio > 2.5: return True, f"游资大幅放量{ratio:.1f}倍"
    return False, ""


def _hurst_signal(k):
    """Hurst择时动量（简化版：两均线多头）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    # 两均线多头排列（简化）
    if c[-1] > _ma(c, 5) > _ma(c, 20):
        ret10 = _ret(c, 10)
        if ret10 > 3: return True, f"Hurst多头+{ret10:.1f}%"
    return False, ""


def _pairs_signal(k):
    """协整配对交易"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    if _ma(c, 10) < _ma(c, 20) * 0.95: return True, "配对收敛"
    return False, ""


def _moat_signal(k):
    """护城河选股（低位+缩量+稳健）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    if pct < 30 and vol_ratio < 0.85 and c[-1] > _ma(c, 5):
        return True, f"护城河低位{pct:.0f}%"
    return False, ""


def _piotroski_signal(k):
    """Piotroski质量因子（简化）"""
    c, v = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    vol_ratio = v[-5:].mean() / v[-20:].mean() if v is not None else 1
    trend = 1 if c[-1] > c[-10:] else 0
    score = 0
    if pct < 40: score += 1
    if vol_ratio < 0.9: score += 1
    if trend: score += 1
    if score >= 2: return True, f"Piotroski质量{score}分"
    return False, ""


def _garp_signal(k):
    """GARP成长（低估+稳健增长：价格适中+温和增长）"""
    c, v = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    vol_ratio = v[-5:].mean() / v[-20:].mean() if v is not None else 1
    # 价格中低位(<45%) + 稳定增长(5-20%) + 缩量整理
    if pct < 45 and 5 < ret10 < 20 and vol_ratio < 0.95 and c[-1] > _ma(c, 5):
        return True, f"GARP增长{ret10:.1f}%"
    return False, ""


def _high_growth_signal(k):
    """高成长股（强势股缩量回调买入）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    ret10 = _ret(c, 10)
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    # 强势(>10%) + 缩量整理(<0.85) + 趋势向上
    if 10 < ret10 < 25 and vol_ratio < 0.85 and c[-1] > _ma(c, 5) > _ma(c, 10):
        return True, f"高成长强势{ret10:.1f}%"
    return False, ""


def _cycle_signal(k):
    """周期股择时（超跌反弹：价格低位+企稳信号）"""
    c, v = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    vol_ratio = v[-5:].mean() / v[-20:].mean() if v is not None else 1
    # 价格低位(<40%) + 超跌(-20%) + 缩量整理 + 企稳
    if pct < 40 and -20 < ret10 < 0 and vol_ratio < 0.9 and c[-1] > _ma(c, 5):
        return True, f"周期低位反弹{pct:.0f}%"
    return False, ""


def _repurchase_signal(k):
    """回购信号（低位+缩量）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    if pct < 30 and vol_ratio < 0.8:
        return True, f"回购信号低位{pct:.0f}%"
    return False, ""


def _equity_incentive_signal(k):
    """股权激励（稳健增长）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    if pct < 40 and 2 < ret10 < 15:
        return True, f"股权激励{ret10:.1f}%"
    return False, ""


def _dragon_tiger_signal(k):
    """龙虎榜跟风（放量+动量）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 5: return False, ""
    vol_ratio = v[-1] / v[-5:].mean()
    ret = _ret(c, 1)
    if vol_ratio > 2 and 0 < ret < 5:
        return True, f"龙虎跟风放量{vol_ratio:.1f}倍"
    return False, ""


def _limit_up_relay_signal(k):
    """打板接力（连续强势）"""
    c, v = _safe(k)
    if c is None or len(c) < 5: return False, ""
    ret = _ret(c, 1)
    vol_ratio = v[-1] / v[-5:].mean() if v is not None else 1
    if ret >= 5 and vol_ratio > 1.5 and c[-1] > _ma(c, 5):
        return True, f"打板接力+{ret:.1f}%"
    return False, ""


def _new_stock_signal(k):
    """次新股（量能活跃+趋势）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 15: return False, ""
    vol_ratio = v[-3:].mean() / v[-10:].mean()
    ret5 = _ret(c, 5)
    if 1.2 < vol_ratio < 3 and 0 < ret5 < 15 and c[-1] > _ma(c, 5):
        return True, f"次新股活跃+{ret5:.1f}%"
    return False, ""


def _grid_signal(k):
    """网格交易（震荡市场）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    vol = c[-5:].std() / c[-5:].mean()  # 波动率
    if 30 < pct < 70 and vol > 0.01:  # 中位震荡
        return True, f"网格震荡{pct:.0f}%"
    return False, ""


def _etf_premium_signal(k):
    """ETF折溢价（接近净值）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    if 35 < pct < 65: return True, f"ETF折溢价中性{pct:.0f}%"
    return False, ""


def _double_low_signal(k):
    """可转债双低（低价+低溢价）- 用价格低位模拟"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    if pct < 25: return True, f"双低低价{pct:.0f}%"
    return False, ""


def _downward_amend_signal(k):
    """可转债下修博弈"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    if pct < 20 and -5 < ret10 < 5:
        return True, f"下修博弈低位{pct:.0f}%"
    return False, ""


def _momentum_break_signal(k):
    """动量突破（强势突破整理区间）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    vol_ratio = v[-1] / v[-10:].mean()
    ret = _ret(c, 1)
    # 放量(>1.5倍) + 上涨(>2%) + 在近期高位附近
    if vol_ratio > 1.5 and ret > 2 and c[-1] > c[-10:].max() * 0.95:
        return True, f"动量突破+{ret:.1f}%"
    return False, ""


def _mean_reversion_signal(k):
    """均值回归（超跌反弹）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    if pct < 20 and c[-1] > _ma(c, 5):
        return True, f"均值回归低位{pct:.0f}%"
    return False, ""


# === 策略池 ===
STRATEGIES = {
    # 已有11个
    '集合竞价': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _auction_signal, 'category': '短线技术'},
    '尾盘抢筹': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _after_hours_signal, 'category': '短线技术'},
    '戴维斯双击': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _davis_signal, 'category': '价值'},
    '困境反转': {'pool': ['000001', '600016', '601166', '600036', '601328'], 'signal': _turnaround_signal, 'category': '逆向'},
    '股东户数变化': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _shareholder_signal, 'category': '事件'},
    '涨停封单': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _limit_up_signal, 'category': '短线事件'},
    '跌停撬板': {'pool': ['000001', '600016', '601166', '600036', '601328'], 'signal': _limit_down_signal, 'category': '短线事件'},
    '限售解禁博弈': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _lockup_signal, 'category': '事件'},
    '游资席位跟踪': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _hot_money_signal, 'category': '资金面'},
    'Hurst择时动量': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _hurst_signal, 'category': '技术面'},
    '协整配对交易': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _pairs_signal, 'category': '统计套利'},
    # v1.9优化策略（8个）
    '护城河选股': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _moat_signal, 'category': '基本面'},
    '质量因子选股': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _piotroski_signal, 'category': '基本面'},
    'GARP成长': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _garp_signal, 'category': '基本面'},
    '高成长股': {'pool': ['300750', '688012', '300059', '002475', '300014'], 'signal': _high_growth_signal, 'category': '成长'},
    '周期股择时': {'pool': ['601899', '000725', '600111', '601600', '000060'], 'signal': _cycle_signal, 'category': '周期'},
    '回购信号': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _repurchase_signal, 'category': '事件'},
    '股权激励': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _equity_incentive_signal, 'category': '事件'},
    '龙虎榜跟风': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _dragon_tiger_signal, 'category': '资金面'},
    '打板接力': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _limit_up_relay_signal, 'category': '短线事件'},
    '次新股': {'pool': ['301601', '301606', '301608', '301610', '301612'], 'signal': _new_stock_signal, 'category': '事件'},
    # v2.0新增策略（9个）
    '网格交易': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _grid_signal, 'category': '套利'},
    'ETF折溢价': {'pool': ['510300', '510500', '159915', '512880', '512000'], 'signal': _etf_premium_signal, 'category': '套利'},
    '可转债双低': {'pool': ['113050', '110033', '127005', '128005', '132003'], 'signal': _double_low_signal, 'category': '可转债'},
    '可转债下修博弈': {'pool': ['113050', '110033', '127005', '128005', '132003'], 'signal': _downward_amend_signal, 'category': '可转债'},
    '动量突破': {'pool': ['600036', '000858', '601318', '600519', '000333'], 'signal': _momentum_break_signal, 'category': '技术面'},
    '均值回归': {'pool': ['000001', '600016', '601166', '600036', '601328'], 'signal': _mean_reversion_signal, 'category': '逆向'},
}


def get_trading_dates(n=40):
    dates = []
    current = BENCHMARK_START
    end = datetime.now()
    while len(dates) < n and current <= end:
        if current.weekday() < 5:
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)
    return dates


def run_backtest(strategy_name, config, helper, trading_dates):
    pool = config['pool']
    signal_fn = config['signal']
    holdings = []
    trades = []
    equity_curve = []
    capital = INITIAL_CAPITAL
    buy_date_idx = {}

    for i, date in enumerate(trading_dates):
        prices = {}
        for h in holdings:
            try:
                df = helper.get_history_kline(h['symbol'], days=5, end_date=date)
                if isinstance(df, pd.DataFrame) and not df.empty and 'close' in df.columns:
                    prices[h['symbol']] = float(df['close'].iloc[-1])
            except:
                pass

        # 卖出
        for h in list(holdings):
            idx = buy_date_idx.get(h['symbol'], 0)
            if idx <= i - 5:
                sp = prices.get(h['symbol'])
                if sp:
                    pnl = (sp - h['price']) / h['price'] * 100
                    trades.append({
                        'buy_date': h['date'], 'sell_date': date,
                        'symbol': h['symbol'], 'name': h['name'],
                        'buy_price': h['price'], 'sell_price': sp,
                        'profit': pnl, 'reason': h['reason']
                    })
                    capital += h['qty'] * sp
                    holdings.remove(h)
                    buy_date_idx.pop(h['symbol'], None)

        # 选股买入
        if len(holdings) < MAX_HOLDINGS:
            candidates = []
            for sym in pool:
                try:
                    df = helper.get_history_kline(sym, days=30, end_date=date)
                    if not isinstance(df, pd.DataFrame) or df.empty or 'close' not in df.columns:
                        continue
                    triggered, reason = signal_fn(df)
                    if triggered:
                        price = prices.get(sym)
                        if price is None:
                            try:
                                price = float(df['close'].iloc[-1])
                            except:
                                price = None
                        if price and price > 0:
                            available = capital / max(MAX_HOLDINGS - len(holdings), 1)
                            qty = int(available / price / 100) * 100
                            if qty >= 100:
                                candidates.append({
                                    'symbol': sym, 'name': sym, 'price': price,
                                    'qty': qty, 'reason': reason, 'date': date
                                })
                except:
                    pass

            for c in candidates[:MAX_HOLDINGS - len(holdings)]:
                cost = c['qty'] * c['price']
                if cost <= capital * 0.5:
                    trades.append({
                        'buy_date': c['date'], 'symbol': c['symbol'],
                        'name': c['name'], 'buy_price': c['price'],
                        'quantity': c['qty'], 'reason': c['reason'],
                        'buy_date_idx': i
                    })
                    holdings.append(c)
                    buy_date_idx[c['symbol']] = i
                    capital -= cost

        val = capital + sum(prices.get(h['symbol'], h['price']) * h['qty'] for h in holdings)
        equity_curve.append({'date': date, 'value': val})

    final_val = equity_curve[-1]['value'] if equity_curve else INITIAL_CAPITAL
    ret = (final_val - INITIAL_CAPITAL) / INITIAL_CAPITAL
    wins = [t for t in trades if isinstance(t.get('profit'), (int, float)) and t['profit'] > 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    return {
        'name': strategy_name,
        'category': config['category'],
        'initial_capital': INITIAL_CAPITAL,
        'current_capital': capital,
        'total_value': final_val,
        'total_return': ret,
        'trades': [t for t in trades if 'sell_price' in t],
        'holdings': holdings,
        'equity_curve': equity_curve,
        'win_rate': win_rate,
        'backtest_start': trading_dates[0],
        'backtest_end': trading_dates[-1],
        'backtest_days': len(trading_dates),
    }


def main():
    from data.akshare_helper import AKShareHelper

    print("=" * 60)
    print(f"极速历史回测 v2.0 - {len(STRATEGIES)}个策略")
    print(f"基准: {BENCHMARK_START.strftime('%Y-%m-%d')}")
    print("=" * 60)

    helper = AKShareHelper(cache_dir="data/cache")
    trading_dates = get_trading_dates(40)

    print(f"回测区间: {trading_dates[0]} ~ {trading_dates[-1]}")
    print(f"策略数: {len(STRATEGIES)}")
    print(f"数据源: AKShare（无速率限制）")
    print()

    results = {}
    start = time.time()

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(run_backtest, name, cfg, helper, trading_dates): name
            for name, cfg in STRATEGIES.items()
        }
        for f in as_completed(futures):
            name = futures[f]
            try:
                r = f.result()
                results[name] = r
                t = r['total_return'] * 100
                n = len(r['trades'])
                wr = r['win_rate']
                status = "OK" if r['total_return'] != 0 or n > 0 else "0信号"
                print(f"  [{status}] {name}: {t:+.2f}% | {n}笔 | 胜率{wr:.0f}%")
            except Exception as e:
                import traceback
                print(f"  [ERROR] {name}: {e}")
                traceback.print_exc()

    elapsed = time.time() - start
    print(f"\n回测完成，耗时 {elapsed:.1f}秒")

    # 分类统计
    cats = {}
    for name, r in results.items():
        cat = r.get('category', '其他')
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(r)

    print(f"\n分类表现:")
    for cat, strats in sorted(cats.items(), key=lambda x: sum(s['total_return'] for s in x[1]) / len(x[1]), reverse=True):
        avg_ret = sum(s['total_return'] for s in strats) / len(strats) * 100
        count = len(strats)
        print(f"  {cat}({count}个): {avg_ret:+.2f}% 均收益")

    # 排名
    print(f"\n收益排名 TOP10:")
    for name, r in sorted(results.items(), key=lambda x: x[1]['total_return'], reverse=True)[:10]:
        print(f"  {name}: {r['total_return']*100:+.2f}%")

    # 保存
    output = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'backtest_type': 'historical_fast_v2',
        'backtest_start': trading_dates[0],
        'backtest_end': trading_dates[-1],
        'backtest_days': len(trading_dates),
        'strategy_count': len(results),
        'strategies': list(results.values()),
    }
    os.makedirs('output', exist_ok=True)
    with open('output/new_strategy_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n已保存到 output/new_strategy_results.json")


if __name__ == '__main__':
    main()
