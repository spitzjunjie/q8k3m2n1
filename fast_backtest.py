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
    """困境反转（放宽版：超跌反弹）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    ret10 = _ret(c, 10)
    # 超跌后开始反弹（ret10<-5%，且近5日上涨）
    ret5 = _ret(c, 5)
    if ret10 < -5 and ret5 > 0:
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
    """涨停封单（严格版：回调买入+趋势确认）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    ret = _ret(c, 1)
    vol_ratio = v[-1] / v[-5:].mean()
    pct = _price_percentile(c, 20)
    # 严格条件：涨幅温和(2-5%) + 明显放量(>1.5倍) + 价格低位(<45%) + 均线支撑
    if 2 <= ret <= 5 and vol_ratio > 1.5 and pct < 45 and c[-1] > _ma(c, 5):
        return True, f"涨停回调买入+{ret:.1f}%"
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
    """游资席位（严格版：回调买入+趋势确认）"""
    c, v = _safe(k)
    if c is None or v is None or len(v) < 20: return False, ""
    ratio = v[-1] / v[-5:].mean()
    ret = _ret(c, 1)
    pct = _price_percentile(c, 20)
    # 严格条件：放量上涨 + 价格低位(<45%) + 均线支撑 + 涨幅温和(<2.5%)
    if 1.3 < ratio < 3 and ret > 0 and pct < 45 and c[-1] > _ma(c, 5) and 0 < ret < 2.5:
        return True, f"游资回调{ratio:.1f}倍+{ret:.1f}%"
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
    """Piotroski质量因子（放宽版）"""
    c, v = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    vol_ratio = v[-5:].mean() / v[-20:].mean() if v is not None else 1
    trend = 1 if c[-1] > c[-10:] else 0
    score = 0
    if pct < 50: score += 1  # 放宽到50%
    if vol_ratio < 1.0: score += 1  # 允许放量
    if trend: score += 1
    if score >= 1: return True, f"Piotroski质量{score}分"  # 放宽到1分即可
    return False, ""


def _garp_signal(k):
    """GARP成长（稳健版：严格趋势+合理估值）"""
    c, v = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    # 价格合理(<55%) + 温和增长(0到25%) + 趋势向上
    if pct < 55 and 0 < ret10 < 25 and c[-1] > _ma(c, 5) > _ma(c, 10):
        return True, f"GARP增长{ret10:.1f}%"
    return False, ""


def _high_growth_signal(k):
    """高成长股（稳健版：主板成长+严格趋势）"""
    c, v = _safe(k)
    if c is None or len(c) < 20: return False, ""
    ret10 = _ret(c, 10)
    # 严格趋势：MA5>MA10>MA20 + 温和涨幅
    ma5 = _ma(c, 5)
    ma10 = _ma(c, 10)
    ma20 = _ma(c, 20)
    if ma5 > ma10 > ma20 and 2 < ret10 < 25 and c[-1] > c[-1]:  # 多头排列
        return True, f"高成长多头{ret10:.1f}%"
    return False, ""


def _cycle_signal(k):
    """金融周期择时（稳健银行股+严格止损）"""
    c, v = _safe(k)
    if c is None or len(c) < 20: return False, ""
    ret20 = _ret(c, 20)
    pct = _price_percentile(c, 20)
    vol_ratio = v[-5:].mean() / v[-20:].mean() if v is not None else 1
    # 严格止损：近20日下跌超15%不买入（避免接飞刀）
    if ret20 < -15:
        return False, ""
    # 价格中低位(<50%) + 缩量整理 + 趋势向上
    if pct < 50 and vol_ratio < 0.9 and c[-1] > _ma(c, 5) > _ma(c, 10):
        return True, f"金融周期稳健{pct:.0f}%"
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
    """股权激励（放宽版）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    # 只要价格不太高，趋势向上即可
    if pct < 55 and c[-1] > _ma(c, 5):
        return True, f"股权激励偏好{ret10:.1f}%"
    return False, ""


def _dragon_tiger_signal(k):
    """龙虎榜跟风（严格版：趋势确认+回调买入）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    vol_ratio = v[-1] / v[-5:].mean()
    ret = _ret(c, 1)
    pct = _price_percentile(c, 20)
    # 严格条件：放量上涨 + 价格低位(<50%) + 均线支撑 + 涨幅温和(<3%)
    if vol_ratio > 1.5 and ret > 0 and pct < 50 and c[-1] > _ma(c, 5) and 0 < ret < 3:
        return True, f"龙虎回调买入{ret:.1f}%"
    return False, ""


def _limit_up_relay_signal(k):
    """打板接力（严格版：趋势确认+回调买入）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    ret = _ret(c, 1)
    ret5 = _ret(c, 5)
    vol_ratio = v[-1] / v[-5:].mean()
    pct = _price_percentile(c, 20)
    # 严格条件：回调后反弹（ret<3%）+ 放量（>1.3倍）+ 价格低位(<50%) + 均线支撑
    if 0 < ret < 3 and vol_ratio > 1.3 and pct < 50 and c[-1] > _ma(c, 5) > _ma(c, 10):
        return True, f"回调买入+{ret:.1f}%"
    return False, ""


def _new_stock_signal(k):
    """次新股（严格版：趋势确认+回调买入）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    vol_ratio = v[-3:].mean() / v[-10:].mean()
    ret5 = _ret(c, 5)
    ret10 = _ret(c, 10)
    pct = _price_percentile(c, 20)
    # 严格条件：回调后反弹(ret5>0) + 温和放量 + 价格低位(<45%) + 均线支撑
    if ret5 > 0 and 0.9 < vol_ratio < 2.0 and pct < 45 and c[-1] > _ma(c, 5) and ret10 < 20:
        return True, f"次新回调买入+{ret5:.1f}%"
    return False, ""


def _grid_signal(k):
    """网格交易（严格版：低位震荡+趋势支撑）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    vol = c[-5:].std() / c[-5:].mean()  # 波动率
    # 严格条件：低位震荡(35-55%) + 有波动 + 均线支撑
    if 35 < pct < 55 and vol > 0.005 and c[-1] > _ma(c, 20):
        return True, f"网格低位震荡{pct:.0f}%"
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


# 新增信号函数（必须在策略池之前定义）
def _north_money_signal(k):
    """北向资金（严格版：趋势确认+回调买入）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    ret10 = _ret(c, 10)
    ret5 = _ret(c, 5)
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    pct = _price_percentile(c, 20)
    # 严格条件：温和上涨 + 回调后反弹(ret5>0) + 放量 + 价格低位(<50%) + 均线多头
    if 0 < ret10 < 15 and ret5 > 0 and vol_ratio > 1.0 and pct < 50 and c[-1] > _ma(c, 5) > _ma(c, 10):
        return True, f"北向回调+{ret10:.1f}%"
    return False, ""

def _institutional_signal(k):
    """机构调研（稳健版：温和放量+趋势）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    ret10 = _ret(c, 10)
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    # 温和上涨+温和放量+趋势向上
    if 0 < ret10 < 25 and vol_ratio > 1.0 and c[-1] > _ma(c, 5):
        return True, f"机构偏好+{ret10:.1f}%"
    return False, ""

def _定向增发_signal(k):
    """定增破发（低位反弹）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    if pct < 30 and ret10 > 0 and c[-1] > _ma(c, 5):
        return True, f"定增破发反弹{ret10:.1f}%"
    return False, ""

# === 新增高质量信号函数 ===
def _macd底背离_signal(k):
    """MACD底背离（超跌反弹）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 34: return False, ""
    # 简化：价格创新低但未大幅下跌 + 缩量
    ret20 = _ret(c, 20)
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    # 超跌后缩量整理
    if ret20 < -10 and vol_ratio < 0.8:
        return True, f"MACD背离{ret20:.1f}%"
    return False, ""

def _布林带收口_signal(k):
    """布林带收口（波动率降低后突破）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    vol = v[-5:].std() / v[-20:].std() if len(v) >= 20 else 1
    # 价格低位 + 波动率收窄 + 趋势向上
    if pct < 30 and vol < 0.9 and c[-1] > _ma(c, 5):
        return True, f"布林收口{pct:.0f}%"
    return False, ""

def _成交量缩量_signal(k):
    """成交量缩量整理（地量见底）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    ret10 = _ret(c, 10)
    # 缩量整理 + 价格稳定 + 趋势向上
    if vol_ratio < 0.7 and -5 < ret10 < 10 and c[-1] > _ma(c, 5):
        return True, f"地量整理{ret10:.1f}%"
    return False, ""

def _趋势线突破_signal(k):
    """趋势线突破（上升通道）"""
    c, _ = _safe(k)
    if c is None or len(c) < 30: return False, ""
    ret20 = _ret(c, 20)
    pct = _price_percentile(c, 20)
    # 长期上涨趋势中回调后反弹
    if 5 < ret20 < 30 and pct < 50 and c[-1] > _ma(c, 5):
        return True, f"趋势突破{ret20:.1f}%"
    return False, ""

def _kdj低位金叉_signal(k):
    """KDJ低位金叉（严格版：超卖+放量+趋势确认）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    ret10 = _ret(c, 10)
    ret5 = _ret(c, 5)
    vol_ratio = v[-3:].mean() / v[-10:].mean()
    pct = _price_percentile(c, 20)
    # 严格条件：超跌(<-10%) + 近5日反弹 + 明显放量(>1.5倍) + 价格低位(<40%)
    if ret10 < -10 and ret5 > 0 and vol_ratio > 1.5 and pct < 40 and c[-1] > _ma(c, 5):
        return True, f"KDJ低位反弹{ret10:.1f}%"
    return False, ""

def _机构重仓_signal(k):
    """机构重仓（价值投资）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    # 价格合理 + 温和上涨 + 温和放量
    if pct < 45 and 0 < ret10 < 20 and 0.9 < vol_ratio < 1.4:
        return True, f"机构重仓+{ret10:.1f}%"
    return False, ""

def _社保重仓_signal(k):
    """社保重仓（稳健价值）"""
    c, _ = _safe(k)
    if c is None or len(c) < 20: return False, ""
    pct = _price_percentile(c, 20)
    ret10 = _ret(c, 10)
    # 价格低位 + 稳定上涨
    if pct < 40 and 0 < ret10 < 15 and c[-1] > _ma(c, 10):
        return True, f"社保偏好+{ret10:.1f}%"
    return False, ""

def _外资持续买入_signal(k):
    """外资持续买入（北向追踪）"""
    c, v = _safe(k)
    if c is None or v is None or len(c) < 20: return False, ""
    ret10 = _ret(c, 10)
    vol_ratio = v[-5:].mean() / v[-20:].mean()
    # 持续上涨 + 温和放量
    if 2 < ret10 < 25 and 1.0 < vol_ratio < 1.5 and c[-1] > c[-5]:
        return True, f"外资买入+{ret10:.1f}%"
    return False, ""


# === 策略池 ===
STRATEGIES = {
    # 短线技术策略 - 活跃中小盘股
    '集合竞价': {'pool': ['002594', '300750', '300059', '002475', '300014'], 'signal': _auction_signal, 'category': '短线技术'},
    '尾盘抢筹': {'pool': ['002475', '300750', '002594', '300059', '688012'], 'signal': _after_hours_signal, 'category': '短线技术'},
    '动量突破': {'pool': ['300750', '688012', '300059', '002475', '002594'], 'signal': _momentum_break_signal, 'category': '技术面'},

    # 价值/基本面策略 - 蓝筹白马
    '戴维斯双击': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _davis_signal, 'category': '价值'},
    '护城河选股': {'pool': ['600519', '601318', '600036', '000858', '601166'], 'signal': _moat_signal, 'category': '基本面'},
    '质量因子选股': {'pool': ['601318', '600036', '600519', '000858', '601166'], 'signal': _piotroski_signal, 'category': '基本面'},
    'GARP成长': {'pool': ['600036', '000858', '601318', '600519', '601012'], 'signal': _garp_signal, 'category': '基本面'},

    # 逆向策略 - 金融股（稳健）
    '困境反转': {'pool': ['000001', '600016', '601166', '600036', '601328'], 'signal': _turnaround_signal, 'category': '逆向'},
    '均值回归': {'pool': ['601328', '601818', '601398', '601939', '601288'], 'signal': _mean_reversion_signal, 'category': '逆向'},
    '周期股择时': {'pool': ['600036', '000001', '601166', '600016', '601818'], 'signal': _cycle_signal, 'category': '金融周期'},

    # 事件策略 - 各板块活跃股
    '股东户数变化': {'pool': ['300750', '002594', '300059', '002475', '688012'], 'signal': _shareholder_signal, 'category': '事件'},
    '回购信号': {'pool': ['600036', '000858', '601318', '600519', '601012'], 'signal': _repurchase_signal, 'category': '事件'},
    '股权激励': {'pool': ['300750', '688012', '300059', '002475', '002594'], 'signal': _equity_incentive_signal, 'category': '事件'},
    '限售解禁博弈': {'pool': ['002594', '300750', '300059', '002475', '688012'], 'signal': _lockup_signal, 'category': '事件'},

    # 短线事件策略 - 主板大盘股（稳定）
    '涨停封单': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _limit_up_signal, 'category': '短线事件'},
    '跌停撬板': {'pool': ['000001', '600016', '601166', '600036', '601328'], 'signal': _limit_down_signal, 'category': '短线事件'},
    '打板接力': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _limit_up_relay_signal, 'category': '短线事件'},

    # 资金面策略 - 主板大盘股（稳定）
    '游资席位跟踪': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _hot_money_signal, 'category': '资金面'},
    '龙虎榜跟风': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _dragon_tiger_signal, 'category': '资金面'},

    # 技术面策略 - 趋势明显的股票
    'Hurst择时动量': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _hurst_signal, 'category': '技术面'},
    '协整配对交易': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _pairs_signal, 'category': '统计套利'},

    # 成长策略 - 主板大盘成长股（稳定）
    '高成长股': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _high_growth_signal, 'category': '成长'},

    # 套利策略 - 大盘蓝筹（稳定）
    '网格交易': {'pool': ['600036', '601318', '600519', '000858', '601166'], 'signal': _grid_signal, 'category': '套利'},

    # 次新股策略 - 主板大盘股（稳定）
    '次新股': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _new_stock_signal, 'category': '事件'},

    # 新增策略 - 资金面/事件驱动（主板大盘股）
    '北向资金': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _north_money_signal, 'category': '资金面'},
    '机构调研': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _institutional_signal, 'category': '事件'},
    '定增破发': {'pool': ['600036', '000858', '601318', '600519', '601012'], 'signal': _定向增发_signal, 'category': '事件'},

    # === 新增高价值策略 ===
    # 技术面策略 - 稳健趋势
    'MACD底背离': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _macd底背离_signal, 'category': '技术面'},
    '布林带收口': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _布林带收口_signal, 'category': '技术面'},
    '成交量缩量': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _成交量缩量_signal, 'category': '技术面'},
    '趋势线突破': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _趋势线突破_signal, 'category': '技术面'},
    'KDJ低位金叉': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _kdj低位金叉_signal, 'category': '技术面'},

    # 资金面策略 - 机构追踪
    '机构重仓': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _机构重仓_signal, 'category': '资金面'},
    '社保重仓': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _社保重仓_signal, 'category': '资金面'},
    '外资持续买入': {'pool': ['600519', '601318', '600036', '000858', '601012'], 'signal': _外资持续买入_signal, 'category': '资金面'},
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

    # 计算夏普比率和最大回撤
    sharpe_ratio = 0
    max_drawdown = 0
    if len(equity_curve) > 1:
        values = [e['value'] for e in equity_curve]
        peak = values[0]
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_drawdown:
                max_drawdown = dd
        # 简化夏普：日收益率/日波动率 * sqrt(252)
        daily_returns = []
        for i in range(1, len(values)):
            if values[i-1] > 0:
                daily_returns.append((values[i] - values[i-1]) / values[i-1])
        if daily_returns:
            import numpy as np
            mean_ret = np.mean(daily_returns)
            std_ret = np.std(daily_returns)
            if std_ret > 0:
                sharpe_ratio = mean_ret / std_ret * np.sqrt(252)

    return {
        'name': strategy_name,
        'category': config['category'],
        'initial_capital': INITIAL_CAPITAL,
        'current_capital': capital,
        'total_value': final_val,
        'total_return': ret,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
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
