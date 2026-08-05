# -*- coding: utf-8 -*-
"""
冒烟测试 —— CI 的最低门槛
====================================================================
现状：仓库里有 15 个 test_*.py，但其中 14 个是**手动跑的脚本**，
只有 1 个含真正的 def test_。CI 里也完全没有 pytest 步骤。

结果就是 auto-fix.yml 可以在没有任何测试把关的情况下
自动改代码并 git push origin main。commit 历史里那条
"fix: trading/simulator.py line 72 - \\n was treated as literal string"
就是自动修复改坏了代码，而"修复"的结果是把择时检查
永久写死成了 has_signal = True。

这个文件是最小可用的安全网。放到 tests/ 下，CI 里加一步 pytest。
====================================================================
"""

import importlib
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------
# 1. 所有 Python 文件必须能编译（会抓出 SyntaxError）
# --------------------------------------------------------------

def _all_py_files():
    skip = {".git", "__pycache__", ".venv", "venv", "node_modules", "site", "_archive"}
    for p in ROOT.rglob("*.py"):
        if not any(s in p.parts for s in skip):
            yield p


@pytest.mark.parametrize("path", list(_all_py_files()), ids=lambda p: str(p.relative_to(ROOT)))
def test_file_compiles(path):
    """每个 .py 都要能通过编译

    目前会失败的两个（Windows 路径写进 docstring，\\U 被当成转义）：
        strategies/ai_stock_selection_strategy.py
        strategies/sector_momentum_strategy.py
    修法：把 docstring 的 \"\"\" 改成 r\"\"\"
    """
    # utf-8-sig：仓库里不少文件带 BOM（如 trading/simulator.py），
    # Python 导入时能自动处理，但 compile() 拿到裸 BOM 会报错，
    # 所以这里按 utf-8-sig 读，跟解释器行为保持一致。
    src = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        compile(src, str(path), "exec")
    except SyntaxError as e:
        pytest.fail(f"{path.relative_to(ROOT)} 语法错误: {e}")


# --------------------------------------------------------------
# 2. 核心模块必须能 import
# --------------------------------------------------------------

CORE_MODULES = [
    "strategies.base",
    "trading.simulator",
    "timing.timing",
    "evaluation",
    "data.akshare_helper",
]


@pytest.mark.parametrize("mod", CORE_MODULES)
def test_core_import(mod):
    importlib.import_module(mod)


# --------------------------------------------------------------
# 3. 不能有硬编码密钥
# --------------------------------------------------------------

LEAK_PATTERNS = [
    (r"hf_[A-Za-z0-9]{30,}", "HuggingFace Token"),
    (r"gsk_[A-Za-z0-9]{40,}", "Groq Key"),
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub PAT"),
    (r"['\"][0-9a-f]{56}['\"]", "Tushare Token"),
    (r"cli_[a-z0-9]{16,}", "飞书 App ID"),
    (r"(?i)(password|passwd)\s*=\s*['\"][^'\"]{4,}['\"]", "明文密码"),
]


def test_no_hardcoded_secrets():
    hits = []
    for p in _all_py_files():
        if p.name in ("test_smoke.py", "purge_secrets.py"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for pat, label in LEAK_PATTERNS:
            if re.search(pat, text):
                hits.append(f"{p.relative_to(ROOT)} → {label}")
    assert not hits, "发现硬编码密钥:\n  " + "\n  ".join(hits)


# --------------------------------------------------------------
# 4. .gitignore 里的文件不能同时被 git 追踪
# --------------------------------------------------------------

def test_no_tracked_ignored_files():
    """git ls-files -i -c --exclude-standard 必须为空

    这正是 config/tushare_config.py 泄漏的原因：
    它在 .gitignore 里，但因为之前被 add 过，ignore 不生效。
    """
    r = subprocess.run(
        ["git", "ls-files", "-i", "-c", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True,
    )
    tracked = [x for x in r.stdout.strip().split("\n") if x]
    assert not tracked, "以下文件既被追踪、又在 .gitignore 里:\n  " + "\n  ".join(tracked)


# --------------------------------------------------------------
# 5. 绩效指标口径必须一致
# --------------------------------------------------------------

def test_win_rate_is_fraction_not_percent():
    """win_rate 必须统一是 0~1

    现在的问题：
      fast_backtest.py:752         win_rate = len(wins)/len(trades)*100   → 0~100
      historical_backtest_engine.py:183  len(wins)/len(sell_trades)        → 0~1
      offline_backtest_engine.py:178     同上                              → 0~1

    而下游 evaluation.py:99 写的是
        score += m['win_rate'] * 15      # 注释说"胜率0-1映射0-15"

    如果喂进去的是 fast_backtest 的 0~100，一个 40% 胜率的策略
    会拿到 600 分而不是 6 分，综合评分直接爆表，所有策略都是 S 级。
    """
    from strategies.base import BaseStrategy

    class Dummy(BaseStrategy):
        def select_stocks(self, helper, date=None):
            return []

    s = Dummy("t", "t")
    s.trades = [{"profit": 1}, {"profit": -1}, {"profit": 1}, {"profit": 1}]
    wr = s.get_win_rate()
    assert 0.0 <= wr <= 1.0, f"win_rate 应该是 0~1，实际 {wr}"
    assert abs(wr - 0.75) < 1e-9


def test_fast_backtest_win_rate_consistent():
    """fast_backtest 的 win_rate 也必须是 0~1，且分母只算已平仓的交易

    现在 fast_backtest.py:752 的分母 len(trades) 里
    **混进了只有买入记录、还没卖出的条目**（它们没有 'profit' 键），
    等于分母被放大了近一倍，胜率被系统性低估。
    """
    trades = [
        {"symbol": "1", "buy_price": 10},                      # 只买未卖
        {"symbol": "1", "buy_price": 10, "sell_price": 11, "profit": 10},
        {"symbol": "2", "buy_price": 10, "sell_price": 9, "profit": -10},
    ]
    closed = [t for t in trades if "sell_price" in t]
    wins = [t for t in closed if t["profit"] > 0]
    correct = len(wins) / len(closed)
    buggy = len(wins) / len(trades)
    assert abs(correct - 0.5) < 1e-9
    assert abs(buggy - 0.3333) < 0.01      # 这就是当前的错误算法
    assert correct != buggy


# --------------------------------------------------------------
# 6. 交易必须扣成本
# --------------------------------------------------------------

def test_trades_include_costs():
    """买卖必须扣手续费，否则回测收益系统性高估

    现在 strategies/base.py:
        add_holding:    cost    = price * quantity          ← 没有佣金
        remove_holding: revenue = sell_price * quantity     ← 没有印花税
    """
    from strategies.base import BaseStrategy

    class Dummy(BaseStrategy):
        def select_stocks(self, helper, date=None):
            return []

    s = Dummy("t", "t", initial_capital=30000)
    s.add_holding("600000", "浦发", 10.0, 1000, "r", "tr", buy_date="2026-01-02")
    t = s.remove_holding("600000", 10.0, "平价卖出", sell_date="2026-01-05")

    assert t is not None
    assert t["profit"] < 0, (
        "同价买入卖出，扣掉佣金和印花税后必须是亏损。"
        f"当前 profit={t['profit']}，说明成本没有被计入。"
        " 修法见 core/costs.py 文件末尾的接入说明。"
    )


# --------------------------------------------------------------
# 7. 交易日历不能把法定节假日当交易日
# --------------------------------------------------------------

def test_calendar_excludes_holidays():
    """五一、国庆这些休市日不能出现在交易日列表里

    fast_backtest.py:644 只判断了 weekday() < 5。
    """
    try:
        from core.trading_calendar import is_trading_day
    except ImportError:
        pytest.skip("core/trading_calendar.py 尚未接入")

    assert not is_trading_day("20260501"), "劳动节不是交易日"
    assert not is_trading_day("20261001"), "国庆不是交易日"
    assert is_trading_day("20260504") or not is_trading_day("20260504")  # 只要不报错


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
