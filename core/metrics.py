# -*- coding: utf-8 -*-
"""
统一的绩效指标
====================================================================
现在系统里夏普比率至少算了 4 遍，口径各不相同：

  fast_backtest.py:776        np.mean/np.std * sqrt(252)     ← std 用 ddof=0
  strategies/base.py:203      pd.Series.std() * sqrt(252)    ← std 用 ddof=1
  historical_backtest_engine.py:174   np.mean/np.std * sqrt(252)
  offline_backtest_engine.py:172      np.mean/np.std * sqrt(252)

同一份数据，不同引擎算出来的夏普不一样，策略之间没法比。
而且四处都**没有减无风险利率**。

更要命的三个问题：

  1) 权益曲线长度不一致。output/strategy_data.json 里 62 个策略，
     equity_curve 长度分别是 9 / 11 / 30 / 41 —— 同一次回测，
     有的策略只有 10 个日收益，有的有 40 个，都乘 sqrt(252) 年化，
     结果完全不可比。

  2) 取不到价格时回退成买入价：
         prices.get(h['symbol'], h['buy_price'])
     缺数据的那天浮盈直接变 0，权益曲线被人为抹平，
     **日收益标准差被压低 → 夏普虚高**。
     这就是当前 62 个策略夏普高达 2~9 的主因之一。

  3) 同时测了 62 个策略，却按单个策略的 p 值判断有效性。
     纯随机情况下也会冒出 3 个 "p<0.05 显著" 的假阳性。
     实测：**0 个策略能通过 Bonferroni 校正。**

本模块把口径统一，并加上多重检验校正和 Deflated Sharpe。
====================================================================
"""

import math
from dataclasses import dataclass, asdict
from typing import List, Optional, Sequence

import numpy as np

TRADING_DAYS = 252
# 无风险利率：用 1 年期国债/存款基准的近似值，按需调整
RISK_FREE_ANNUAL = 0.015


# --------------------------------------------------------------
# 工具
# --------------------------------------------------------------

def equity_to_returns(curve: Sequence) -> np.ndarray:
    """从权益曲线提取日收益率。curve 可以是 [float] 或 [{'date':..,'value':..}]"""
    vals = []
    for item in curve:
        v = item.get("value") if isinstance(item, dict) else item
        if isinstance(v, (int, float)) and v is not None:
            vals.append(float(v))
    if len(vals) < 2:
        return np.array([])
    a = np.asarray(vals, dtype=float)
    prev = a[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(prev > 0, (a[1:] - prev) / prev, 0.0)
    return r


# --------------------------------------------------------------
# 指标
# --------------------------------------------------------------

@dataclass
class Performance:
    n_days: int
    n_trades: int
    total_return: float          # 累计收益率
    annual_return: float         # 年化收益率（几何）
    annual_vol: float            # 年化波动率
    sharpe: float                # 已扣无风险利率
    sortino: float
    max_drawdown: float
    calmar: float                # 年化收益 / 最大回撤（口径修正）
    win_rate: float              # ★ 统一为 0~1
    profit_factor: float
    avg_trade_pct: float
    t_stat: float                # 单笔收益的 t 统计量
    p_value: float               # 单边 p
    p_value_adjusted: float      # 多重检验校正后
    deflated_sharpe: float       # 考虑"试了多少个策略"后的夏普可信度 0~1
    is_significant: bool

    def to_dict(self):
        return asdict(self)


def _t_cdf(t: float, df: int) -> float:
    """t 分布 CDF。有 scipy 用 scipy，没有就用正态近似。"""
    try:
        from scipy import stats
        return float(stats.t.cdf(t, df))
    except Exception:
        return 0.5 * (1 + math.erf(t / math.sqrt(2)))


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def compute(equity_curve: Sequence,
            trade_returns_pct: Optional[List[float]] = None,
            n_strategies_tested: int = 1,
            periods_per_year: int = TRADING_DAYS,
            risk_free_annual: float = RISK_FREE_ANNUAL,
            initial_capital: float = 30000.0) -> Performance:
    """计算一个策略的全部绩效指标

    equity_curve        : 权益曲线
    trade_returns_pct   : 每笔交易的收益率（%）。**必须传完整列表**，
                          不要传 base.py 里 trades[-10:] 那个截断版本。
    n_strategies_tested : 这一轮总共回测了多少个策略。
                          用于多重检验校正 —— 试得越多，
                          单个策略"看起来好"的门槛就该越高。
    """
    r = equity_to_returns(equity_curve)
    n = len(r)
    trades = list(trade_returns_pct or [])

    if n == 0:
        return Performance(0, len(trades), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, False)

    # ---- 收益 ----
    total_return = float(np.prod(1 + r) - 1)
    years = n / periods_per_year
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else 0.0

    # ---- 波动 / 夏普（ddof=1，样本标准差）----
    vol_d = float(np.std(r, ddof=1)) if n > 1 else 0.0
    annual_vol = vol_d * math.sqrt(periods_per_year)
    rf_daily = (1 + risk_free_annual) ** (1 / periods_per_year) - 1
    excess = r - rf_daily
    sharpe = (float(np.mean(excess)) / vol_d * math.sqrt(periods_per_year)) if vol_d > 0 else 0.0

    # ---- Sortino（只惩罚下行波动）----
    downside = excess[excess < 0]
    dstd = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    sortino = (float(np.mean(excess)) / dstd * math.sqrt(periods_per_year)) if dstd > 0 else 0.0

    # ---- 最大回撤 ----
    vals = [initial_capital]
    for x in r:
        vals.append(vals[-1] * (1 + x))
    arr = np.asarray(vals)
    peak = np.maximum.accumulate(arr)
    max_drawdown = float(np.max((peak - arr) / peak)) if len(arr) else 0.0

    # ---- Calmar：用年化收益，不是累计收益 ----
    calmar = annual_return / max_drawdown if max_drawdown > 1e-9 else 0.0

    # ---- 交易层面 ----
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t < 0]
    win_rate = len(wins) / len(trades) if trades else 0.0       # ★ 0~1
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_win / gross_loss if gross_loss > 1e-9 else 0.0
    avg_trade = float(np.mean(trades)) if trades else 0.0

    # ---- 统计显著性 ----
    t_stat = p_value = 0.0
    if len(trades) > 1:
        sd = float(np.std(trades, ddof=1))
        if sd > 0:
            t_stat = avg_trade / (sd / math.sqrt(len(trades)))
            p_value = 1 - _t_cdf(t_stat, len(trades) - 1)
        else:
            p_value = 1.0
    else:
        p_value = 1.0

    # Bonferroni：试了 N 个策略，门槛就要严 N 倍
    p_adj = min(1.0, p_value * max(n_strategies_tested, 1))

    # ---- Deflated Sharpe Ratio (Bailey & López de Prado, 2014) ----
    # 回答的问题不是"夏普高不高"，而是
    # "在试了 N 个策略之后，这个夏普还有多大概率不是运气"
    dsr = 0.0
    if n > 2 and sharpe != 0:
        N = max(n_strategies_tested, 1)
        if N > 1:
            euler = 0.5772156649
            # 纯随机下 N 次试验的期望最大夏普
            e_max = ((1 - euler) * _inv_norm(1 - 1.0 / N)
                     + euler * _inv_norm(1 - 1.0 / (N * math.e)))
            sr0 = e_max / math.sqrt(periods_per_year)   # 换算到日频
        else:
            sr0 = 0.0
        sr_d = sharpe / math.sqrt(periods_per_year)
        g3 = float(_skew(r))
        g4 = float(_kurt(r))
        denom = math.sqrt(max(1 - g3 * sr_d + (g4 - 1) / 4 * sr_d ** 2, 1e-9))
        dsr = _norm_cdf((sr_d - sr0) * math.sqrt(n - 1) / denom)

    return Performance(
        n_days=n, n_trades=len(trades),
        total_return=total_return, annual_return=annual_return,
        annual_vol=annual_vol, sharpe=sharpe, sortino=sortino,
        max_drawdown=max_drawdown, calmar=calmar,
        win_rate=win_rate, profit_factor=profit_factor,
        avg_trade_pct=avg_trade,
        t_stat=t_stat, p_value=p_value, p_value_adjusted=p_adj,
        deflated_sharpe=dsr,
        is_significant=(p_adj < 0.05 and dsr > 0.95),
    )


def _inv_norm(p: float) -> float:
    """标准正态分位数（Acklam 近似，够用）"""
    if p <= 0:
        return -8.0
    if p >= 1:
        return 8.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r2 = q * q
    return (((((a[0]*r2+a[1])*r2+a[2])*r2+a[3])*r2+a[4])*r2+a[5])*q / \
           (((((b[0]*r2+b[1])*r2+b[2])*r2+b[3])*r2+b[4])*r2+1)


def _skew(x: np.ndarray) -> float:
    if len(x) < 3:
        return 0.0
    m = np.mean(x); s = np.std(x, ddof=1)
    return float(np.mean(((x - m) / s) ** 3)) if s > 0 else 0.0


def _kurt(x: np.ndarray) -> float:
    if len(x) < 4:
        return 3.0
    m = np.mean(x); s = np.std(x, ddof=1)
    return float(np.mean(((x - m) / s) ** 4)) if s > 0 else 3.0


# --------------------------------------------------------------
# 批量：加上横截面的多重检验校正
# --------------------------------------------------------------

def compute_batch(strategy_results: List[dict]) -> List[dict]:
    """对一整批策略统一算指标，自动带入 n_strategies_tested"""
    n = len(strategy_results)
    out = []
    for s in strategy_results:
        trades = s.get("all_trades") or s.get("trades") or []
        tr = [t.get("profit_pct") for t in trades
              if isinstance(t, dict) and isinstance(t.get("profit_pct"), (int, float))]
        perf = compute(
            s.get("equity_curve", []),
            trade_returns_pct=tr,
            n_strategies_tested=n,
            initial_capital=s.get("initial_capital", 30000.0),
        )
        d = dict(s)
        d["performance"] = perf.to_dict()
        out.append(d)
    return out


def benjamini_hochberg(p_values: List[float], alpha: float = 0.05) -> List[bool]:
    """BH 法控制 FDR。比 Bonferroni 宽松，做策略筛选时更实用。"""
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    keep = [False] * n
    for rank, idx in enumerate(order, 1):
        if p_values[idx] <= alpha * rank / n:
            for j in order[:rank]:
                keep[j] = True
    return keep


if __name__ == "__main__":
    print("=" * 60)
    print("统一指标模块自检")
    print("=" * 60)
    rng = np.random.default_rng(42)

    # 造一个"看起来不错但其实是随机"的策略
    r = rng.normal(0.002, 0.02, 30)
    curve = [{"date": f"d{i}", "value": v} for i, v in
             enumerate(30000 * np.cumprod(1 + np.concatenate([[0], r])))]
    trades = list(rng.normal(3.0, 8.0, 10))

    for n_tested in (1, 62):
        p = compute(curve, trades, n_strategies_tested=n_tested)
        print(f"\n  假设总共测了 {n_tested} 个策略：")
        print(f"    年化收益 {p.annual_return*100:>7.2f}%   夏普 {p.sharpe:>5.2f}   最大回撤 {p.max_drawdown*100:>5.2f}%")
        print(f"    单笔均值 {p.avg_trade_pct:>7.2f}%   t={p.t_stat:.2f}")
        print(f"    原始 p={p.p_value:.4f}  →  校正后 p={p.p_value_adjusted:.4f}")
        print(f"    Deflated Sharpe = {p.deflated_sharpe:.3f}")
        print(f"    判定：{'✅ 显著' if p.is_significant else '❌ 无法区别于随机'}")
    print("\n  注意同一份数据，只因为'你试了 62 个策略'，结论就从显著变成不显著。")
    print("  这不是保守，这是正确 —— 试得多，撞上好看结果的概率本来就高。")
