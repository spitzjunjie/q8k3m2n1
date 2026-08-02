# -*- coding: utf-8 -*-
"""
A 股成交可行性约束
====================================================================
现在的回测默认"想买就能买、想卖就能卖、按收盘价成交"。
对 A 股来说这三条都不成立，而且你的策略池里有
「涨停封单」「跌停撬板」「打板接力」「首板回调」这类
**恰恰专挑涨跌停做文章**的策略 —— 不建模涨跌停，
这些策略的回测结果基本没有参考价值。

必须建模的四件事：

  1) 涨停买不进：封死涨停时挂单排不上，实际成交概率很低
  2) 跌停卖不掉：跌停时想止损也走不了，第二天可能继续跌
  3) 停牌：get_history_kline 拿不到当天数据时，
     现在的代码会用**上一个交易日的收盘价**当今天的价，
     等于假装停牌股还能按老价格交易
  4) 新股上市首日 / ST 股：涨跌幅限制不同（20%、5%）

====================================================================
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import pandas as pd


def price_limit_pct(symbol: str, name: str = "") -> float:
    """返回该股票的涨跌幅限制（小数）"""
    name = (name or "").upper()
    if "ST" in name or "*ST" in name:
        return 0.05                      # ST 股 ±5%
    if symbol.startswith(("300", "301")):
        return 0.20                      # 创业板 ±20%
    if symbol.startswith("688"):
        return 0.20                      # 科创板 ±20%
    if symbol.startswith(("8", "4", "920")):
        return 0.30                      # 北交所 ±30%
    return 0.10                          # 主板 ±10%


def round_tick(price: float) -> float:
    """A 股最小报价单位 0.01 元"""
    return round(price + 1e-9, 2)


def limit_prices(prev_close: float, symbol: str, name: str = "") -> Tuple[float, float]:
    """根据前收盘价算出今日涨停价 / 跌停价"""
    pct = price_limit_pct(symbol, name)
    return round_tick(prev_close * (1 + pct)), round_tick(prev_close * (1 - pct))


@dataclass
class ExecutionCheck:
    can_trade: bool
    reason: str
    fill_price: Optional[float] = None


def check_buy(df: pd.DataFrame, symbol: str, name: str = "",
              ref_col: str = "close", target_date: Optional[str] = None) -> ExecutionCheck:
    """能不能在这一天买入

    df : 到 target_date 为止的日线（至少 2 根）
    """
    if df is None or df.empty or len(df) < 2:
        return ExecutionCheck(False, "K线数据不足")

    # --- 停牌检测：最后一根 bar 的日期不是目标日期 ---
    if target_date and "date" in df.columns:
        last = str(df["date"].iloc[-1]).replace("-", "")[:8]
        if last != str(target_date).replace("-", "")[:8]:
            return ExecutionCheck(False, f"停牌或无当日数据(最新bar={last})")

    # --- 零成交量 = 停牌 ---
    if "volume" in df.columns and float(df["volume"].iloc[-1]) <= 0:
        return ExecutionCheck(False, "成交量为0，视为停牌")

    prev_close = float(df[ref_col].iloc[-2])
    close = float(df[ref_col].iloc[-1])
    up, _ = limit_prices(prev_close, symbol, name)

    # --- 涨停买不进 ---
    if close >= up - 0.005:
        return ExecutionCheck(False, f"涨停({close:.2f}≥{up:.2f})，无法买入")

    # --- 一字板：最高=最低，全天无波动，也买不到 ---
    if {"high", "low"}.issubset(df.columns):
        if abs(float(df["high"].iloc[-1]) - float(df["low"].iloc[-1])) < 0.005:
            return ExecutionCheck(False, "一字板，无法成交")

    return ExecutionCheck(True, "", close)


def check_sell(df: pd.DataFrame, symbol: str, name: str = "",
               ref_col: str = "close", target_date: Optional[str] = None) -> ExecutionCheck:
    """能不能在这一天卖出"""
    if df is None or df.empty or len(df) < 2:
        return ExecutionCheck(False, "K线数据不足")

    if target_date and "date" in df.columns:
        last = str(df["date"].iloc[-1]).replace("-", "")[:8]
        if last != str(target_date).replace("-", "")[:8]:
            return ExecutionCheck(False, f"停牌，无法卖出(最新bar={last})")

    if "volume" in df.columns and float(df["volume"].iloc[-1]) <= 0:
        return ExecutionCheck(False, "成交量为0，视为停牌")

    prev_close = float(df[ref_col].iloc[-2])
    close = float(df[ref_col].iloc[-1])
    _, down = limit_prices(prev_close, symbol, name)

    # --- 跌停卖不掉（这条最要命：止损失效）---
    if close <= down + 0.005:
        return ExecutionCheck(False, f"跌停({close:.2f}≤{down:.2f})，无法卖出")

    return ExecutionCheck(True, "", close)


def is_t1_blocked(hold_days: int) -> bool:
    """T+1：买入当天不能卖。hold_days=0 表示今天刚买"""
    return hold_days < 1


# ====================================================================
# 接入方式
# ====================================================================
#
# 在 trading/simulator.py 的 execute_buy 里，拿到 df 之后：
#
#     from core.execution import check_buy
#     chk = check_buy(df, symbol, name, target_date=date)
#     if not chk.can_trade:
#         return None, chk.reason
#     price = chk.fill_price          # 用校验过的价格，不要直接用 close
#
# 在 check_and_sell 里，止损止盈判断**之后**、真正下单**之前**：
#
#     from core.execution import check_sell
#     chk = check_sell(df, symbol, name, target_date=date)
#     if not chk.can_trade:
#         # 卖不掉就得继续持有，把这一天记为"想卖没卖成"
#         holding['blocked_sell_days'] = holding.get('blocked_sell_days', 0) + 1
#         return False, chk.reason
#
# 最后一条特别重要：现在的止损是"一定能在 -10% 止住"，
# 真实情况是跌停板上卖不掉，第二天可能低开继续跌。
# 不建模这个，回测的最大回撤会系统性偏小。
#
# ====================================================================

if __name__ == "__main__":
    print("=" * 58)
    print("涨跌停限制自检")
    print("=" * 58)
    cases = [
        ("600519", "贵州茅台", 1800.00),
        ("300750", "宁德时代", 200.00),
        ("688012", "中微公司", 150.00),
        ("000001", "平安银行", 12.00),
        ("000005", "ST星源", 3.00),
    ]
    for sym, nm, pc in cases:
        up, down = limit_prices(pc, sym, nm)
        print(f"  {sym} {nm:<8} 前收 {pc:>8.2f} → 涨停 {up:>8.2f} / 跌停 {down:>8.2f}"
              f"  (±{price_limit_pct(sym, nm)*100:.0f}%)")
    print()
    print("  当前回测把这些全当成可自由成交 ——")
    print("  「涨停封单」「跌停撬板」「打板接力」三个策略的结果尤其不可信。")
