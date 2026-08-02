# -*- coding: utf-8 -*-
"""
真实 A 股交易日历
====================================================================
问题：fast_backtest.py 的 get_trading_dates() 只做了 weekday() < 5 判断：

    while len(dates) < n and current <= end:
        if current.weekday() < 5:
            dates.append(...)

这会把春节、清明、五一、端午、国庆等法定休市日当成交易日。后果：

  1. 休市日调 get_history_kline(end_date=休市日) 会拿到上一个交易日的 K 线，
     于是同一根 bar 被重复处理，等于凭空多出若干"零收益日"。
  2. 零收益日拉低了日收益标准差 → 夏普被系统性高估。
     （这是当前 62 个策略夏普高达 2~9 的原因之一。）
  3. hold_days 是按"工作日"数的，不是交易日，止盈止损的时间窗口是错的。

本模块给出两种方案：优先走数据源真实日历，拿不到时退回内置节假日表。
====================================================================
"""

from datetime import datetime, timedelta
from functools import lru_cache

# --------------------------------------------------------------
# 内置法定休市日（沪深两市）。每年 11-12 月国务院公布次年安排后需更新一次。
# 只列出落在周一~周五的休市日；周末不必列。
# --------------------------------------------------------------
CN_MARKET_HOLIDAYS = {
    # 2024
    "20240101",
    "20240212", "20240213", "20240214", "20240215", "20240216",
    "20240404", "20240405",
    "20240501", "20240502", "20240503",
    "20240610",
    "20240916", "20240917",
    "20241001", "20241002", "20241003", "20241004", "20241007",
    # 2025
    "20250101",
    "20250128", "20250129", "20250130", "20250131", "20250203", "20250204",
    "20250404",
    "20250501", "20250502", "20250505",
    "20250602",
    "20251001", "20251002", "20251003", "20251006", "20251007", "20251008",
    # 2026（按已公布安排，若有调整请更新）
    "20260101", "20260102",
    "20260216", "20260217", "20260218", "20260219", "20260220",
    "20260406",
    "20260501",
    "20260619",
    "20260925",
    "20261001", "20261002", "20261005", "20261006", "20261007", "20261008",
}

# 周末调休上班但**股市仍然休市** —— A 股不会因调休而开市，
# 所以调休上班的周六周日一律不是交易日，weekday 判断已覆盖。


def is_trading_day(d) -> bool:
    """判断某天是否为 A 股交易日"""
    if isinstance(d, str):
        d = datetime.strptime(d.replace("-", ""), "%Y%m%d")
    if d.weekday() >= 5:
        return False
    return d.strftime("%Y%m%d") not in CN_MARKET_HOLIDAYS


@lru_cache(maxsize=8)
def _calendar_from_source(start: str, end: str):
    """优先从数据源取真实交易日历（最可靠）。失败返回 None。"""
    # 方案 1：Tushare（需要 token，最准）
    try:
        from config.tushare_config import get_tushare_pro
        pro = get_tushare_pro()
        df = pro.trade_cal(exchange="SSE", start_date=start, end_date=end,
                           is_open="1", fields="cal_date")
        if df is not None and not df.empty:
            return tuple(df["cal_date"].astype(str).tolist())
    except Exception:
        pass

    # 方案 2：AKShare
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if df is not None and not df.empty:
            col = df.columns[0]
            s = df[col].astype(str).str.replace("-", "", regex=False)
            s = s[(s >= start) & (s <= end)]
            if len(s):
                return tuple(s.tolist())
    except Exception:
        pass

    # 方案 3：Baostock
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_trade_dates(
            start_date=f"{start[:4]}-{start[4:6]}-{start[6:]}",
            end_date=f"{end[:4]}-{end[4:6]}-{end[6:]}")
        out = []
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            if row[1] == "1":
                out.append(row[0].replace("-", ""))
        bs.logout()
        if out:
            return tuple(out)
    except Exception:
        pass

    return None


def get_trading_dates(start, end=None, n=None):
    """获取 [start, end] 区间内的真实交易日列表（YYYYMMDD 字符串）

    start / end : datetime 或 'YYYYMMDD' / 'YYYY-MM-DD' 字符串
    n           : 若指定，只返回前 n 个交易日

    与原实现的差异：真正剔除法定休市日，且优先使用数据源日历。
    """
    def _norm(x):
        if isinstance(x, datetime):
            return x.strftime("%Y%m%d")
        return str(x).replace("-", "")

    start = _norm(start)
    end = _norm(end or datetime.now())

    dates = _calendar_from_source(start, end)
    if dates is None:
        # 退回内置表
        dates = []
        cur = datetime.strptime(start, "%Y%m%d")
        stop = datetime.strptime(end, "%Y%m%d")
        while cur <= stop:
            if is_trading_day(cur):
                dates.append(cur.strftime("%Y%m%d"))
            cur += timedelta(days=1)
        dates = tuple(dates)

    dates = list(dates)
    return dates[:n] if n else dates


def trading_days_between(d1, d2) -> int:
    """两个日期之间的交易日数量（用于正确计算 hold_days）"""
    return max(len(get_trading_dates(d1, d2)) - 1, 0)


if __name__ == "__main__":
    print("交易日历自检")
    print("=" * 56)
    # 用内置表验证（不联网）
    naive, real = [], []
    cur = datetime(2026, 4, 27)
    while cur <= datetime(2026, 5, 8):
        tag = cur.strftime("%Y-%m-%d %a")
        if cur.weekday() < 5:
            naive.append(tag)
            if is_trading_day(cur):
                real.append(tag)
        cur += timedelta(days=1)
    print(f"  原实现（只看 weekday）判定为交易日：{len(naive)} 天")
    print(f"  真实交易日：                      {len(real)} 天")
    print(f"  被误判的休市日：{sorted(set(naive) - set(real))}")
    print()
    print("  每误判 1 天，就多出 1 个人造的 0 收益日，")
    print("  日收益标准差被压低 → 夏普虚高。")
