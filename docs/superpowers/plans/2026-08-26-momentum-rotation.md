# 三指数动量轮动 · 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现《三指数动量轮动策略设计文档》的回测脚本：300/500/红利低波月频双动量轮动，研发期选参、冻结期一次性验证。

**Architecture:** 新脚本 `momentum_rotation_backtest.py`，复用 `asset_allocation_backtest.py` 的数据层与绩效汇总（该脚本有 `__main__` 保护可直接 import）。核心是纯函数：`select_assets`（月末信号）→ `backtest_with_holdings`（开盘价执行+成本）→ 置换检验复用同一引擎只换持仓来源。数据用 open+close 双价（信号用收盘、执行用开盘）。

**Tech Stack:** Python 3.11+，stdlib（random/json/argparse）+ tushare + pandas（仅数据加载），pytest。无新依赖。

**设计文档:** `docs/superpowers/specs/2026-08-26-momentum-rotation-design.md`（预注册协议，实现不得偏离）

## Global Constraints

- 动量回看期候选 `{3, 6, 12}` 月；研发期 2006-2016 选**夏普最高**者（平手取回撤小），冻结期 2017-2024 只跑一次
- 冻结期模式 `--frozen` 必须显式传 `--lookback`（无默认值），防止在冻结期上挑参数
- 成本：单边 0.1%（`COST_RATE = 0.001`）；资产→资产切换买卖两腿各计一次；资产→现金只计卖；现金→资产只计买
- 执行时点：月末收盘算信号，**次月首个交易日按开盘价**调仓；月内不动作
- 现金收益：SHIBOR 1w 日因子（`build_bond_factors`），缺失日回退固定年化 3.5%（`BOND_DAILY_FACTOR`）
- 置换检验：1000 次，`random.Random(20260826)` 固定种子；p 值加一校正 `(ge+1)/(n+1)`
- 历史不足 N 个月的月末信号一律持现金
- 所有文件 UTF-8 头 + `sys.stdout.reconfigure(encoding='utf-8')`（Windows GBK 控制台兼容，仓库既有约定）
- 测试命令统一 `python -m pytest tests/test_momentum_rotation.py -q --basetemp="$TEMP/pytest-fresh"`（本机旧 pytest 临时目录权限损坏，必须带 basetemp）

**Interfaces（跨任务契约）:**

```python
# 日期一律 YYYYMMDD 字符串；prices/ohlc 结构：
# prices: {code: {YYYYMMDD: close_float}}
# ohlc:   {code: {'open': {YYYYMMDD: float}, 'close': {YYYYMMDD: float}}}
RISK_ASSETS = ['000300.SH', '000905.SH', 'H30269.CSI']

def month_end_indices(dates: list[str]) -> list[int]                 # Task 1
def cash_index_series(dates: list[str], cash_factors: dict|None) -> list[float]  # Task 1
def select_assets(close: dict, dates: list[str], lookback_months: int,
                  cash_idx: list[float]) -> list[str]                # Task 1，len==月末数
def backtest_with_holdings(ohlc: dict, dates: list[str], cash_factors: dict|None,
                           holdings: list[str], initial: float = 100.0,
                           cost_rate: float = 0.001) -> list[float]  # Task 2，与 dates 等长
def load_rotation_prices(pro, codes: list[str], start: str, end: str,
                         use_cache: bool = True) -> dict             # Task 3
def run_equal_weight(ohlc: dict, dates: list[str], initial: float = 100.0,
                     cost_rate: float = 0.001) -> list[float]        # Task 4
def random_holdings(strategy_holdings: list[str], mode: str, rng) -> list[str]  # Task 4，mode in {'n1','n2'}
def permutation_test(ohlc, dates, cash_factors, strategy_holdings, mode: str,
                     n: int = 1000, seed: int = 20260826) -> float   # Task 4，返回 p 值
```

---

### Task 1: 日历与信号纯函数

**Files:**
- Create: `momentum_rotation_backtest.py`
- Test: `tests/test_momentum_rotation.py`

**Interfaces:**
- Consumes: `asset_allocation_backtest.BOND_ANNUAL`、`BOND_DAILY_FACTOR`（已存在，float）
- Produces: 上节 `month_end_indices` / `cash_index_series` / `select_assets` 三个函数

- [ ] **Step 1: 写失败测试**

创建 `tests/test_momentum_rotation.py`：

```python
# -*- coding: utf-8 -*-
"""三指数动量轮动 · 单元测试（离线，合成数据）。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from momentum_rotation_backtest import (
    RISK_ASSETS, month_end_indices, cash_index_series, select_assets,
)


def make_dates(months):
    """生成连续工作日的 YYYYMMDD 字符串列表。months: [(年, 月, 天数), ...]"""
    from datetime import date, timedelta
    out = []
    for y, m, ndays in months:
        d = date(y, m, 1)
        while d.month == m and len([x for x in out if x[:6] == f'{y}{m:02d}']) < ndays:
            if d.weekday() < 5:
                out.append(d.strftime('%Y%m%d'))
            d += timedelta(days=1)
    return out


def make_close(dates, spec):
    """spec: {code: 起始价}，每天 +1 线性上行；或 {code: (起始价, 日涨幅)}"""
    out = {}
    for code, cfg in spec.items():
        px, daily = cfg if isinstance(cfg, tuple) else (cfg, 0.0)
        series, p = {}, px
        for d in dates:
            series[d] = round(p, 4)
            p *= (1 + daily)
        out[code] = series
    return out


class TestMonthEnd:
    def test_last_trading_day_of_each_month(self):
        dates = make_dates([(2026, 1, 20), (2026, 2, 15)])
        me = month_end_indices(dates)
        assert len(me) == 2
        assert dates[me[0]][:6] == '202601' and dates[me[1]][:6] == '202602'
        # 是该月最后一个交易日
        assert me[1] == len(dates) - 1 or dates[me[1] + 1][:6] == '202603'


class TestCashIndex:
    def test_grows_by_factor(self):
        dates = ['20260105', '20260106', '20260107']
        factors = {'20260106': 1.01, '20260107': 1.02}
        idx = cash_index_series(dates, factors)
        assert idx[0] == 1.0
        assert abs(idx[1] - 1.01) < 1e-9
        assert abs(idx[2] - 1.01 * 1.02) < 1e-9

    def test_missing_date_falls_back_to_bond_daily(self):
        from asset_allocation_backtest import BOND_DAILY_FACTOR
        dates = ['20260105', '20060106']   # 2006 无 SHIBOR → 回退
        idx = cash_index_series(dates, {})
        assert abs(idx[1] - BOND_DAILY_FACTOR) < 1e-9

    def test_none_factors_all_fallback(self):
        from asset_allocation_backtest import BOND_DAILY_FACTOR
        dates = ['20260105', '20260106']
        idx = cash_index_series(dates, None)
        assert abs(idx[1] - BOND_DAILY_FACTOR) < 1e-9


class TestSelectAssets:
    def test_picks_strongest_relative(self):
        # 12 个整月，B 上行最快 → 每个有效月末都选 B
        dates = make_dates([(2025, m, 20) for m in range(1, 13)])
        close = make_close(dates, {
            '000300.SH': (100, 0.0), '000905.SH': (100, 0.01), 'H30269.CSI': (100, 0.0),
        })
        cash_idx = cash_index_series(dates, None)
        h = select_assets(close, dates, 3, cash_idx)
        # 前 3 个月历史不足 → cash；之后全选 000905.SH（日涨 1% 远超现金）
        assert h[:3] == ['cash'] * 3
        assert set(h[3:]) == {'000905.SH'}

    def test_absolute_momentum_goes_cash(self):
        # 全部资产下跌、现金正收益 → 全现金
        dates = make_dates([(2025, m, 20) for m in range(1, 13)])
        close = make_close(dates, {
            '000300.SH': (100, -0.005), '000905.SH': (100, -0.001), 'H30269.CSI': (100, -0.002),
        })
        cash_idx = cash_index_series(dates, None)   # 回退 3.5% 年化 > 资产收益
        h = select_assets(close, dates, 3, cash_idx)
        assert set(h[3:]) == {'cash'}

    def test_insufficient_history_is_cash(self):
        dates = make_dates([(2025, 1, 20), (2025, 2, 20)])
        close = make_close(dates, {'000300.SH': 100, '000905.SH': 100, 'H30269.CSI': 100})
        h = select_assets(close, dates, 3, cash_index_series(dates, None))
        assert set(h) == {'cash'}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_momentum_rotation.py -q --basetemp="$TEMP/pytest-fresh"`
Expected: FAIL，`ModuleNotFoundError: No module named 'momentum_rotation_backtest'`

- [ ] **Step 3: 写最小实现**

创建 `momentum_rotation_backtest.py`：

```python
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
'''三指数动量轮动（沪深300/中证500/红利低波 + 双动量现金保护）· 回测
============================================================================
设计文档: docs/superpowers/specs/2026-08-26-momentum-rotation-design.md（预注册协议）

用法:
    python momentum_rotation_backtest.py --dev                     # 研发期 2006-2016，三参数对比选 N
    python momentum_rotation_backtest.py --frozen --lookback 6     # 冻结期 2017-2024（只跑一次）
    python momentum_rotation_backtest.py --frozen --lookback 6 --permutation   # 冻结期 + 置换检验
'''
import os
import sys
import json
import argparse
import random

sys.stdout.reconfigure(encoding='utf-8')

from asset_allocation_backtest import (
    BOND_ANNUAL, BOND_DAILY_FACTOR,
    build_bond_factors, slice_prices, summarize, print_table, fmt_pct,
    run_buyhold, run_portfolio,
)

RISK_ASSETS = ['000300.SH', '000905.SH', 'H30269.CSI']
ASSET_NAMES = {'000300.SH': '沪深300', '000905.SH': '中证500', 'H30269.CSI': '红利低波'}
LOOKBACKS = [3, 6, 12]           # 候选动量回看期（月），研发期三选一
COST_RATE = 0.001                # 单边成本 0.1%
INITIAL = 100.0
FETCH_START = '20050101'         # 12 个月 lookback 的预热 + MA200 参照的 200 日预热
DEV_END, FROZEN_END = '20161231', '20241231'
DEV_REPORT, FROZEN_REPORT = '20060101', '20170101'
PERM_N = 1000
PERM_SEED = 20260826
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_FILE = os.path.join(_MODULE_DIR, 'output', 'momentum_rotation_results.json')


def month_end_indices(dates):
    '''每个月最后一个交易日在 dates（升序 YYYYMMDD 字符串）里的下标。'''
    out = []
    for i, d in enumerate(dates):
        if i == len(dates) - 1 or d[:6] != dates[i + 1][:6]:
            out.append(i)
    return out


def cash_index_series(dates, cash_factors):
    '''现金净值序列（首日=1.0），逐日乘 SHIBOR 因子；缺失日回退固定 3.5% 年化。'''
    out = [1.0]
    for i in range(1, len(dates)):
        f = cash_factors.get(dates[i], BOND_DAILY_FACTOR) if cash_factors else BOND_DAILY_FACTOR
        out.append(out[-1] * f)
    return out


def select_assets(close, dates, lookback_months, cash_idx):
    '''每个月末收盘算 N 个月动量，选出下月持仓（'code'|'cash'），与月末列表对齐。

    相对动量：三资产当月月末收盘 / N 个自然月前月末收盘 - 1，最高者胜。
    绝对动量：胜者收益 <= 现金同期收益 → 现金。
    '''
    me = month_end_indices(dates)
    holdings = []
    for k, idx in enumerate(me):
        d_cur = dates[idx]
        y, m = int(d_cur[:4]), int(d_cur[4:6])
        tm, ty = m - lookback_months, y
        while tm <= 0:
            tm += 12
            ty -= 1
        prefix = f'{ty:04d}{tm:02d}'
        past = [i for i in me[:k] if dates[i][:6] == prefix]
        if not past:
            holdings.append('cash')          # 历史不足 N 个月
            continue
        i0 = past[-1]
        best = 'cash'
        best_ret = cash_idx[idx] / cash_idx[i0] - 1   # 现金同期收益 = 绝对动量门槛
        for code in RISK_ASSETS:
            r = close[code][d_cur] / close[code][dates[i0]] - 1
            if r > best_ret:
                best, best_ret = code, r
        holdings.append(best)
    return holdings
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_momentum_rotation.py -q --basetemp="$TEMP/pytest-fresh"`
Expected: PASS（8 个测试）

- [ ] **Step 5: Commit**

```bash
git add momentum_rotation_backtest.py tests/test_momentum_rotation.py
git commit -m "feat: 动量轮动信号纯函数（月末历/现金指数/双动量选择）"
```

---

### Task 2: 回测引擎（开盘执行 + 成本）

**Files:**
- Modify: `momentum_rotation_backtest.py`（文件末尾追加）
- Test: `tests/test_momentum_rotation.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `month_end_indices` / `cash_index_series`
- Produces: `backtest_with_holdings(ohlc, dates, cash_factors, holdings, initial=100.0, cost_rate=0.001) -> list[float]`

- [ ] **Step 1: 写失败测试**（追加到 `tests/test_momentum_rotation.py`）

```python
class TestBacktest:
    def _ohlc(self, dates, close_spec, open_premium=0.0):
        close = make_close(dates, close_spec)
        return {c: {'open': {d: v * (1 + open_premium) for d, v in s.items()},
                    'close': s} for c, s in close.items()}

    def test_cash_path_equals_cash_index(self):
        from momentum_rotation_backtest import backtest_with_holdings
        dates = make_dates([(2025, m, 20) for m in range(1, 13)])
        ohlc = self._ohlc(dates, {'000300.SH': 100, '000905.SH': 100, 'H30269.CSI': 100})
        factors = {d: 1.0 for d in dates}     # 固定现金零收益，断言才可精确
        holdings = ['cash'] * len(month_end_indices(dates))   # 与月末数等长
        eq = backtest_with_holdings(ohlc, dates, factors, holdings)
        cash_idx = cash_index_series(dates, factors)
        assert all(abs(e - 100.0 * ci) < 1e-6 for e, ci in zip(eq, cash_idx))

    def test_switch_executes_at_next_day_open(self):
        from momentum_rotation_backtest import backtest_with_holdings
        dates = make_dates([(2025, 1, 20), (2025, 2, 20), (2025, 3, 5)])
        # 全资产收盘恒 100；open 溢价 10%（只有切换日的成交价受影响）
        ohlc = self._ohlc(dates, {'000300.SH': (100, 0.0), '000905.SH': (100, 0.0),
                                  'H30269.CSI': (100, 0.0)}, open_premium=0.10)
        factors = {d: 1.0 for d in dates}
        holdings = ['000300.SH'] * len(month_end_indices(dates))
        eq = backtest_with_holdings(ohlc, dates, factors, holdings, cost_rate=0.0)
        # 1 月末信号 → 2 月首个交易日按 open=110 买入：units = 100/110，
        # 之后每天净值 = units × 收盘 100
        first_feb = month_end_indices(dates)[0] + 1
        units = 100.0 / 110.0
        assert abs(eq[first_feb] - units * 100.0) < 1e-6
        assert abs(eq[-1] - units * 100.0) < 1e-6

    def test_asset_to_asset_costs_two_legs(self):
        from momentum_rotation_backtest import backtest_with_holdings
        dates = make_dates([(2025, 1, 20), (2025, 2, 20), (2025, 3, 5)])
        ohlc = self._ohlc(dates, {'000300.SH': 100, '000905.SH': 100, 'H30269.CSI': 100})
        factors = {d: 1.0 for d in dates}
        # 两组持仓共用同一入场（2 月首日现金→B，一腿买）；唯一差别是 3 月首日
        # h_switch 多做一次 B→A 切换。价格不变时该切换恰为卖+买两腿 → 比值 (1-c)^2。
        h_stay = ['000905.SH'] * len(month_end_indices(dates))
        h_switch = ['000905.SH', '000905.SH', '000300.SH']
        eq_stay = backtest_with_holdings(ohlc, dates, factors, h_stay, cost_rate=0.001)
        eq_switch = backtest_with_holdings(ohlc, dates, factors, h_switch, cost_rate=0.001)
        assert abs(eq_stay[0] - 100.0) < 1e-6          # 首日尚未调仓
        ratio = eq_switch[-1] / eq_stay[-1]
        assert abs(ratio - (1 - 0.001) ** 2) < 1e-9

    def test_going_to_cash_costs_one_extra_leg(self):
        from momentum_rotation_backtest import backtest_with_holdings
        dates = make_dates([(2025, 1, 20), (2025, 2, 20), (2025, 3, 5)])
        ohlc = self._ohlc(dates, {'000300.SH': 100, '000905.SH': 100, 'H30269.CSI': 100})
        factors = {d: 1.0 for d in dates}
        # 与一直持有 B 相比，「3 月转现金」只多做一次卖出 → 差一腿 (1-c)
        h_stay = ['000905.SH', '000905.SH', '000905.SH']
        h_tocash = ['000905.SH', '000905.SH', 'cash']
        eq_stay = backtest_with_holdings(ohlc, dates, factors, h_stay, cost_rate=0.001)
        eq_tocash = backtest_with_holdings(ohlc, dates, factors, h_tocash, cost_rate=0.001)
        assert abs(eq_tocash[-1] / eq_stay[-1] - (1 - 0.001)) < 1e-9
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_momentum_rotation.py -q --basetemp="$TEMP/pytest-fresh"`
Expected: FAIL，`ImportError: cannot import name 'backtest_with_holdings'`

- [ ] **Step 3: 写最小实现**（追加到 `momentum_rotation_backtest.py`）

```python
def backtest_with_holdings(ohlc, dates, cash_factors, holdings,
                           initial=INITIAL, cost_rate=COST_RATE):
    '''按给定月末持仓序列回测：信号月末收盘出、次月首个交易日开盘价调仓。

    ohlc: {code: {'open': {d: px}, 'close': {d: px}}}；holdings 与月末列表对齐。
    返回与 dates 等长的权益序列（首日 = initial）。
    '''
    me = month_end_indices(dates)
    if len(holdings) != len(me):
        raise ValueError(f'holdings {len(holdings)} != 月末数 {len(me)}')
    cash_idx = cash_index_series(dates, cash_factors)
    switch = {}
    for k, idx in enumerate(me):
        if idx + 1 < len(dates):
            switch[idx + 1] = holdings[k]
    cur, units, cash = 'cash', 0.0, initial
    equity = []
    for i, d in enumerate(dates):
        if i > 0:
            cash *= cash_idx[i] / cash_idx[i - 1]      # 隔夜现金增值
        if i in switch:
            tgt = switch[i]
            if tgt != cur:
                if cur != 'cash':                       # 卖出腿
                    cash += units * ohlc[cur]['open'][d] * (1 - cost_rate)
                    units = 0.0
                if tgt != 'cash':                       # 买入腿
                    units = cash * (1 - cost_rate) / ohlc[tgt]['open'][d]
                    cash = 0.0
                cur = tgt
        equity.append(units * ohlc[cur]['close'][d] + cash)
    return equity
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_momentum_rotation.py -q --basetemp="$TEMP/pytest-fresh"`
Expected: PASS（12 个测试）

- [ ] **Step 5: Commit**

```bash
git add momentum_rotation_backtest.py tests/test_momentum_rotation.py
git commit -m "feat: 动量轮动回测引擎（次月开盘执行+单边成本）"
```

---

### Task 3: 数据加载（open+close 缓存）

**Files:**
- Modify: `momentum_rotation_backtest.py`（追加）
- Test: `tests/test_momentum_rotation.py`（追加）

**Interfaces:**
- Consumes: `asset_allocation_backtest.CACHE_FILE`（`output/index_cache.json`，缓存写到 `rotation-*` 键下，不碰既有键）
- Produces: `load_rotation_prices(pro, codes, start, end, use_cache=True) -> ohlc`

- [ ] **Step 1: 写失败测试**（追加；用 stub pro，离线）

```python
class TestLoadRotationPrices:
    def _stub_pro(self, df_rows):
        import pandas as pd
        class StubPro:
            def index_daily(self, ts_code, start_date, end_date):
                df = pd.DataFrame(df_rows)
                return df
        return StubPro()

    def test_extracts_open_and_close_and_caches(self, tmp_path, monkeypatch):
        import momentum_rotation_backtest as m
        rows = []
        for d in ['20250106', '20250107']:
            rows.append({'trade_date': d, 'open': 10.0, 'close': 11.0})
        stub = self._stub_pro(rows)
        cache_file = tmp_path / 'index_cache.json'
        monkeypatch.setattr(m, 'CACHE_FILE', str(cache_file))
        out = m.load_rotation_prices(stub, ['000300.SH'], '20250101', '20250201')
        assert out['000300.SH']['close']['20250106'] == 11.0
        assert out['000300.SH']['open']['20250107'] == 10.0
        # 第二次走缓存（stub 换成会抛错的也能过 → 证明没再请求）
        class BoomPro:
            def index_daily(self, **kw):
                raise AssertionError('不应再次请求')
        out2 = m.load_rotation_prices(BoomPro(), ['000300.SH'], '20250101', '20250201')
        assert out2['000300.SH']['close']['20250106'] == 11.0
```

注意：`momentum_rotation_backtest.py` 需要自己的 `CACHE_FILE` 模块常量（指向 `asset_allocation_backtest.CACHE_FILE` 同一路径），monkeypatch 才有目标。实现里加：

```python
from asset_allocation_backtest import CACHE_FILE   # 与资产配置脚本共用一个缓存文件
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_momentum_rotation.py -q --basetemp="$TEMP/pytest-fresh"`
Expected: FAIL，`ImportError: cannot import name 'CACHE_FILE'`（或 `load_rotation_prices` 不存在）

- [ ] **Step 3: 写最小实现**（追加）

```python
def load_rotation_prices(pro, codes, start, end, use_cache=True):
    '''拉指数 open+close，返回 {code: {'open': {...}, 'close': {...}}}。

    缓存到 index_cache.json 的 'rotation-{start}-{end}' 键（与资产配置脚本的
    收盘价缓存互不干扰）。三个标的都是指数，统一走 index_daily。
    '''
    key = f'rotation-{start}-{end}'
    cache = {}
    if use_cache and os.path.exists(CACHE_FILE):
        try:
            cache = json.load(open(CACHE_FILE, encoding='utf-8'))
        except Exception:
            cache = {}
    result = {}
    for code in codes:
        hit = cache.get(key, {}).get(code)
        if hit:
            result[code] = hit
            print(f'  缓存命中 {code}: {len(hit["close"])} 行')
            continue
        print(f'  拉取 {code} ...')
        df = pro.index_daily(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            raise RuntimeError(f'{code} 无数据（{start}~{end}）')
        df = df.sort_values('trade_date')
        result[code] = {
            'open': {r['trade_date']: float(r['open']) for _, r in df.iterrows()},
            'close': {r['trade_date']: float(r['close']) for _, r in df.iterrows()},
        }
        print(f'    {code}: {len(result[code]["close"])} 行')
    if use_cache:
        cache.setdefault(key, {}).update(result)
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        json.dump(cache, open(CACHE_FILE, 'w', encoding='utf-8'), ensure_ascii=False)
    return result
```

同时把文件头部的 import 改为：

```python
from asset_allocation_backtest import (
    BOND_ANNUAL, BOND_DAILY_FACTOR, CACHE_FILE,
    build_bond_factors, slice_prices, summarize, print_table, fmt_pct,
    run_buyhold, run_portfolio,
)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_momentum_rotation.py -q --basetemp="$TEMP/pytest-fresh"`
Expected: PASS（13 个测试）

- [ ] **Step 5: Commit**

```bash
git add momentum_rotation_backtest.py tests/test_momentum_rotation.py
git commit -m "feat: 轮动数据加载（open+close，rotation-* 缓存键）"
```

---

### Task 4: 基准、置换检验与 CLI

**Files:**
- Modify: `momentum_rotation_backtest.py`（追加）
- Test: `tests/test_momentum_rotation.py`（追加）

**Interfaces:**
- Consumes: Task 1–3 全部；`asset_allocation_backtest` 的 `slice_prices` / `run_buyhold` / `run_portfolio(report_start=)` / `summarize` / `print_table` / `build_bond_factors` / `BOND_ANNUAL`
- Produces: `run_equal_weight`、`random_holdings`、`permutation_test`、`rebase`、`slice_ohlc`、`main()`（CLI 完整可用）

- [ ] **Step 1: 写失败测试**（追加）

```python
class TestBenchmarksAndPermutation:
    def _setup(self):
        # 14 个整月（跨年，date() 不接受月份 >12）
        months = [(2025, m, 20) for m in range(1, 13)] + [(2026, m, 20) for m in (1, 2)]
        dates = make_dates(months)
        ohlc = {c: {'open': {d: v * 1.001 for d, v in s.items()}, 'close': s}
                for c, s in make_close(dates, {
                    '000300.SH': (100, 0.002), '000905.SH': (100, 0.003),
                    'H30269.CSI': (100, 0.001)}).items()}
        return dates, ohlc

    def test_equal_weight_sanity(self):
        from momentum_rotation_backtest import run_equal_weight
        dates, ohlc = self._setup()
        eq = run_equal_weight(ohlc, dates)
        assert len(eq) == len(dates)
        assert all(e > 0 for e in eq)
        assert eq[-1] != eq[0]      # 三资产日涨不同 → 组合净值必然变动

    def test_equal_weight_flat_prices_stay_at_initial(self):
        from momentum_rotation_backtest import run_equal_weight
        dates, _ = self._setup()
        # 零成本、价格恒定时，任意再平衡都不该改变净值
        flat = {c: {'open': {d: 100.0 for d in dates}, 'close': {d: 100.0 for d in dates}}
                for c in RISK_ASSETS}
        eq = run_equal_weight(flat, dates, cost_rate=0.0)
        assert all(abs(e - 100.0) < 1e-6 for e in eq)

    def test_random_holdings_n2_preserves_cash(self):
        from momentum_rotation_backtest import random_holdings
        import random
        rng = random.Random(1)
        strat = ['000300.SH', 'cash', '000905.SH', 'cash']
        h = random_holdings(strat, 'n2', rng)
        assert h[1] == 'cash' and h[3] == 'cash'
        assert h[0] in RISK_ASSETS and h[2] in RISK_ASSETS

    def test_random_holdings_n1_always_invested(self):
        from momentum_rotation_backtest import random_holdings
        import random
        rng = random.Random(1)
        h = random_holdings(['cash', '000300.SH'], 'n1', rng)
        assert all(x in RISK_ASSETS for x in h)

    def test_rebase_normalizes_to_100(self):
        from momentum_rotation_backtest import rebase
        eq = [90.0, 95.0, 100.0, 110.0]
        out = rebase(eq, ['20240101', '20240102', '20240103', '20240104'], '20240103')
        assert out[0][0] == 100.0 and abs(out[0][-1] - 110.0) < 1e-9
        assert out[1] == ['20240103', '20240104']

    def test_permutation_p_in_range(self):
        from momentum_rotation_backtest import (
            permutation_test, select_assets, cash_index_series, backtest_with_holdings,
        )
        dates, ohlc = self._setup()
        close = {c: ohlc[c]['close'] for c in RISK_ASSETS}
        cash_idx = cash_index_series(dates, None)
        holdings = select_assets(close, dates, 3, cash_idx)
        p = permutation_test(ohlc, dates, {}, holdings, 'n2', n=30, seed=7)
        assert 0.0 < p <= 1.0

    def test_frozen_requires_lookback(self, capsys):
        from momentum_rotation_backtest import main
        try:
            main(['--frozen'])
            assert False, '应当退出'
        except SystemExit:
            pass   # argparse 缺必填参数 → exit 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_momentum_rotation.py -q --basetemp="$TEMP/pytest-fresh"`
Expected: FAIL，`ImportError`（`run_equal_weight`/`random_holdings`/`rebase`/`permutation_test`/`main` 不存在）

- [ ] **Step 3: 写实现**（追加到 `momentum_rotation_backtest.py`）

```python
def common_dates(ohlc):
    '''三资产 open/close 都齐的交易日（升序 YYYYMMDD 字符串）。'''
    days = set.intersection(*[set(ohlc[c]['close']) for c in RISK_ASSETS])
    for c in RISK_ASSETS:
        days &= set(ohlc[c]['open'])
    return sorted(days)


def slice_ohlc(ohlc, start, end):
    '''按 YYYYMMDD 区间切片。'''
    return {c: {'open': {d: v for d, v in ohlc[c]['open'].items() if start <= d <= end},
                'close': {d: v for d, v in ohlc[c]['close'].items() if start <= d <= end}}
            for c in ohlc}


def rebase(eq, dates, start):
    '''把权益曲线从首个 >= start 的日起重新归一到 100（冻结期窗口统计用）。'''
    keep = [(d, e) for d, e in zip(dates, eq) if d >= start]
    if not keep:
        return [], []
    e0 = keep[0][1]
    return [e / e0 * 100.0 for _, e in keep], [d for d, _ in keep]


def run_equal_weight(ohlc, dates, initial=INITIAL, cost_rate=COST_RATE):
    '''等权买入持有三资产，每月首个交易日开盘按「只交易漂移部分」再平衡（计成本）。'''
    me = month_end_indices(dates)
    rb_days = {idx + 1 for idx in me if idx + 1 < len(dates)}
    units = {c: 0.0 for c in RISK_ASSETS}
    cash = initial
    equity = []
    for i, d in enumerate(dates):
        if i == 0 or i in rb_days:
            vals = {c: units[c] * ohlc[c]['open'][d] for c in RISK_ASSETS}
            total = cash + sum(vals.values())
            target = total / 3.0
            # 先卖（富余腿），后买（欠缺腿）
            for c in RISK_ASSETS:
                diff = target - vals[c]
                if diff < -1e-9:
                    units[c] += diff / ohlc[c]['open'][d]
                    cash += -diff * (1 - cost_rate)
            for c in RISK_ASSETS:
                diff = target - vals[c]
                if diff > 1e-9:
                    need = diff / (1 - cost_rate)
                    spend = min(need, cash)
                    cash -= spend
                    units[c] += spend / ohlc[c]['open'][d]
        equity.append(sum(units[c] * ohlc[c]['close'][d] for c in RISK_ASSETS) + cash)
    return equity


def random_holdings(strategy_holdings, mode, rng):
    '''随机对照持仓。n2: 策略现金月也现金（风险匹配）；n1: 永远满仓三选一。'''
    out = []
    for h in strategy_holdings:
        if mode == 'n2' and h == 'cash':
            out.append('cash')
        else:
            out.append(rng.choice(RISK_ASSETS))
    return out


def permutation_test(ohlc, dates, cash_factors, strategy_holdings, mode,
                     n=PERM_N, seed=PERM_SEED):
    '''置换检验：p = P(随机组收益 >= 策略收益)，加一校正。'''
    rng = random.Random(seed)
    strat = backtest_with_holdings(ohlc, dates, cash_factors, strategy_holdings)
    strat_ret = strat[-1] / INITIAL - 1
    ge = 0
    for _ in range(n):
        h = random_holdings(strategy_holdings, mode, rng)
        eq = backtest_with_holdings(ohlc, dates, cash_factors, h)
        if eq[-1] / INITIAL - 1 >= strat_ret:
            ge += 1
    return (ge + 1) / (n + 1)


def _phase_prices(pro, end, use_cache=True):
    '''拉全窗口数据并返回（ohlc, cash_factors）。'''
    ohlc = load_rotation_prices(pro, RISK_ASSETS, FETCH_START, end, use_cache)
    cash_factors = build_bond_factors(pro, FETCH_START, end)
    return ohlc, cash_factors


def run_dev(pro, use_cache=True):
    '''研发期：三个 lookback 各跑一遍，选夏普最高（平手取回撤小）。'''
    ohlc, cash_factors = _phase_prices(pro, DEV_END, use_cache)
    dates = common_dates(ohlc)
    dev_ohlc = slice_ohlc(ohlc, FETCH_START, DEV_END)
    dev_dates = [d for d in dates if d <= DEV_END]
    cash_idx = cash_index_series(dev_dates, cash_factors)
    close = {c: dev_ohlc[c]['close'] for c in RISK_ASSETS}
    rows = []
    for lb in LOOKBACKS:
        holdings = select_assets(close, dev_dates, lb, cash_idx)
        eq = backtest_with_holdings(dev_ohlc, dev_dates, cash_factors, holdings)
        eq_r, dates_r = rebase(eq, dev_dates, DEV_REPORT)
        rows.append(summarize(f'动量{lb}个月', eq_r))
    print_table(rows)
    # 预注册准则：夏普最高；平手取最大回撤小者。
    # max_drawdown 为正值（core/metrics.py: max((peak-arr)/peak)），故取负后 max 即回撤小者
    best = max(rows, key=lambda r: (r['sharpe'], -r['max_drawdown']))
    print(f'\n>>> 研发期选定 N = {best["variant"]} （夏普最高，平手回撤小，预注册准则）')
    return rows, int(best['variant'].replace('动量', '').replace('个月', ''))


def run_frozen(pro, lookback, do_permutation, use_cache=True):
    '''冻结期：策略 + 4 组基准 +（可选）置换检验。只跑一次，不再改参数。'''
    ohlc, cash_factors = _phase_prices(pro, FROZEN_END, use_cache)
    dates = common_dates(ohlc)
    frozen_ohlc = slice_ohlc(ohlc, FETCH_START, FROZEN_END)
    frozen_dates = [d for d in dates if d <= FROZEN_END]
    cash_idx = cash_index_series(frozen_dates, cash_factors)
    close = {c: frozen_ohlc[c]['close'] for c in RISK_ASSETS}

    # 策略（全窗口跑，冻结窗口 rebase 出报告区间）
    holdings = select_assets(close, frozen_dates, lookback, cash_idx)
    eq = backtest_with_holdings(frozen_ohlc, frozen_dates, cash_factors, holdings)
    eq_r, dates_r = rebase(eq, frozen_dates, FROZEN_REPORT)
    rows = [summarize(f'动量轮动(N={lookback})', eq_r)]

    # 基准1：等权月度再平衡
    eq_ew = run_equal_weight(frozen_ohlc, frozen_dates)
    eq_ew_r, _ = rebase(eq_ew, frozen_dates, FROZEN_REPORT)
    rows.append(summarize('等权买入持有(月再平衡)', eq_ew_r))
    # 基准2：单资产买入持有（不计成本，slice 到冻结窗口）
    close_only = {c: frozen_ohlc[c]['close'] for c in RISK_ASSETS}
    for code in RISK_ASSETS:
        sub = slice_prices(close_only, [code], FROZEN_REPORT, FROZEN_END)
        eq_b, _ = run_buyhold(sub, code)
        rows.append(summarize(f'买入持有{ASSET_NAMES[code]}', eq_b))
    # 基准3：60/40 + MA200（2016 年起预热 200 日，报告从 2017 起）
    sub300 = slice_prices(close_only, ['000300.SH'], '20160101', FROZEN_END)
    eq_ma, _ = run_portfolio(sub300, {'000300.SH': 0.6, 'bond': 0.4}, BOND_ANNUAL,
                             dd_control=False, trend_ma=200, trend_floor=0.0,
                             bond_factors=cash_factors, report_start=FROZEN_REPORT)
    rows.append(summarize('60/40+MA200', eq_ma))
    print_table(rows)

    result = {'mode': 'frozen', 'lookback': lookback, 'rows': rows}

    if do_permutation:
        p_n2 = permutation_test(frozen_ohlc, frozen_dates, cash_factors, holdings, 'n2')
        p_n1 = permutation_test(frozen_ohlc, frozen_dates, cash_factors, holdings, 'n1')
        result['p_n2_risk_matched'], result['p_n1_full_random'] = p_n2, p_n1
        print(f'\n置换检验({PERM_N}次, seed={PERM_SEED}): N2风险匹配 p={p_n2:.3f}  N1满仓随机 p={p_n1:.3f}')

    # 三条件判定（预注册及格线）
    strat = rows[0]
    ew = next(r for r in rows if '等权' in r['variant'])
    c1 = strat['total_return'] >= ew['total_return']
    c2 = strat['max_drawdown'] <= ew['max_drawdown'] * (2 / 3)
    c3 = result.get('p_n2_risk_matched', 1.0) < 0.05
    result['pass'] = {'收益不低于等权': c1, '回撤<=等权2/3': c2, 'N2置换p<0.05': c3}
    print(f'\n三条件判定: 收益≥等权 {c1} | 回撤≤2/3 {c2} | p<0.05 {c3}'
          f'  → {"✅ 通过" if all(result["pass"].values()) else "❌ 不通过（0 是合法结论）"}')

    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
    json.dump(result, open(RESULT_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'结果已保存 -> {RESULT_FILE}')
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description='三指数动量轮动回测（预注册协议）')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--dev', action='store_true', help='研发期 2006-2016 三参数对比选 N')
    g.add_argument('--frozen', action='store_true', help='冻结期 2017-2024（只跑一次）')
    ap.add_argument('--lookback', type=int, default=None,
                    help='动量回看期月数（--frozen 必填，写死后不得更改）')
    ap.add_argument('--permutation', action='store_true', help='冻结期附置换检验（1000次）')
    ap.add_argument('--no-cache', action='store_true', help='不用本地缓存')
    args = ap.parse_args(argv)

    if args.frozen and args.lookback not in LOOKBACKS:
        ap.error(f'--frozen 必须显式给 --lookback，且只能是 {LOOKBACKS}（防在冻结期挑参数）')

    # 与 asset_allocation_backtest 同一模式：本地走 config 模块（读 .env），
    # CI 等无 config 环境走 TUSHARE_TOKEN 环境变量。
    try:
        from config.tushare_config import get_tushare_pro
    except Exception:
        def get_tushare_pro():
            import tushare as ts
            ts.set_token(os.environ.get('TUSHARE_TOKEN', ''))
            return ts.pro_api()
    pro = get_tushare_pro()

    if args.dev:
        run_dev(pro, use_cache=not args.no_cache)
    else:
        run_frozen(pro, args.lookback, args.permutation, use_cache=not args.no_cache)


if __name__ == '__main__':
    main()
```

注意：`momentum_rotation_backtest.py` 顶部 Task 1 版本没有 `CACHE_FILE` 导入，Task 3 已补；`main` 里 `import tushare` 延迟到运行时，保证测试导入模块不发网络请求。

- [ ] **Step 4: 跑全部测试确认通过**

Run: `python -m pytest tests/test_momentum_rotation.py -q --basetemp="$TEMP/pytest-fresh"`
Expected: PASS（19 个测试）

- [ ] **Step 5: 冒烟门禁（全仓库测试不受影响）**

Run: `python -m pytest tests/ -q -m "not network" --basetemp="$TEMP/pytest-fresh"`
Expected: 全部 PASS（232+ 新增）

- [ ] **Step 6: Commit**

```bash
git add momentum_rotation_backtest.py tests/test_momentum_rotation.py
git commit -m "feat: 轮动基准/置换检验/CLI（--dev 选参、--frozen 强制显式 lookback）"
```

---

### Task 5: 实跑研发期与冻结期，结论入档

**Files:**
- Modify: `量化系统文档/资产配置方案.md`（研究线状态，仓库外：`C:\Users\xrs08\Desktop\量化交易系统\量化系统文档\`）
- Modify: `C:\Users\xrs08\Desktop\量化交易系统\进度文档.md`
- 产出: `output/momentum_rotation_results.json`（冻结期运行自动写）

**Interfaces:**
- Consumes: Task 4 的完整 CLI；环境变量 `TUSHARE_TOKEN`（本地 `.env` 已有）
- Produces: 研发期选定 N 的记录 + 冻结期最终数字 + 三条件判定结论

- [ ] **Step 1: 实跑研发期（选 N）**

以下命令都在 submodule 根目录执行（`C:\Users\xrs08\Desktop\量化交易系统\stock_intelligence\multi_strategy_trading`，token 从本地 config 模块/.env 读）。

Run: `python momentum_rotation_backtest.py --dev`
Expected: 打印三行对比表（动量3/6/12个月）+ `>>> 研发期选定 N = 动量X个月`。
首次运行会拉 3 个指数 2005–2016 数据（约 1 分钟，之后走缓存）。
**记录**：把三参数对比表和选定的 N 记到进度文档。

- [ ] **Step 2: 冻结期一次性实跑（含置换检验）**

Run: `python momentum_rotation_backtest.py --frozen --lookback <Step1选的N> --permutation`
Expected: 打印 6 行对比表（策略+5 基准）、置换检验 p 值、三条件判定、结果落盘 `output/momentum_rotation_results.json`。
**纪律**：无论结果如何，本命令只跑这一次；不看结果不换参数。

- [ ] **Step 3: 结论入档**

按判定结果二选一写入文档（两份都改）：

- 若通过：`量化系统文档/资产配置方案.md` 研究线状态加一段「动量轮动已通过冻结期验证（数字引用 results.json）」，并注明红利低波 2019 年前为指数代理。
- 若不通过：写明「动量轮动研究线已关闭（冻结期三条件未过，引用具体数字），按预注册协议不加参数重跑」。

`进度文档.md` 本次会话一节补：研发期选定 N、冻结期数字、三条件判定、下一步（通过→按 MA200 模式立项模拟盘；不通过→关闭）。两处文档都必须写明**多重检验披露**：研发期 {3,6,12} 三选一属 3 次检验（spec 第三节要求）。

- [ ] **Step 4: 提交**

```bash
git add output/momentum_rotation_results.json
git commit -m "feat: 动量轮动研发期选N + 冻结期一次性验证（结论见提交信息）"
git push origin main
```

提交信息正文写清：选定的 N、冻结期收益/回撤/夏普、p 值、三条件判定结果。
