# -*- coding: utf-8 -*-
"""
回测修复验证测试
验证以下修复是否正确：
1. buy_date/sell_date 使用历史日期而非 datetime.now()
2. T+1 限制：当天买不能当天卖
3. 止盈止损正确触发
4. 已持仓股票不再被重复选入
5. equity_curve 包含日期信息

运行方式: python test_backtest_fixes.py
"""
import sys
from datetime import datetime

def test_buy_date_is_historical():
    """测试1: buy_date 应该是历史日期，而非 datetime.now()"""
    print("\n=== 测试1: buy_date 使用历史日期 ===")
    from trading.simulator import TradingSimulator
    from strategies.base import FactorStrategy
    from timing.timing import TimingEngine
    import pandas as pd

    class TestStrategy(FactorStrategy):
        def calculate_factor(self, helper, date=None):
            return pd.DataFrame()
        def __init__(self):
            super().__init__('测试', '测试', 'test')

    strategy = TestStrategy()
    timing = TimingEngine()
    sim = TradingSimulator(strategy, timing)

    # 用历史日期买入
    hist_date = '2026-06-01'
    result, msg = sim.execute_buy('000001', '测试', 10.0, 'test', date=hist_date)

    if result is None:
        print(f"  ❌ 买入失败: {msg}")
        return False

    buy_date = result['buy_date']
    today = datetime.now().strftime("%Y-%m-%d")

    if buy_date == today:
        print(f"  ❌ FAIL: buy_date={buy_date}, 应该是 {hist_date}, 却是今天 {today}")
        return False
    elif buy_date == hist_date:
        print(f"  ✅ PASS: buy_date={buy_date} (正确使用历史日期)")
        return True
    else:
        print(f"  ❌ FAIL: buy_date={buy_date}, 应该是 {hist_date}")
        return False


def test_t_plus_1_restriction():
    """测试2: T+1 限制 - 当天买不能当天卖"""
    print("\n=== 测试2: T+1 限制 ===")
    from trading.simulator import TradingSimulator
    from strategies.base import FactorStrategy
    from timing.timing import TimingEngine

    class TestStrategy(FactorStrategy):
        def calculate_factor(self, helper, date=None):
            import pandas as pd
            return pd.DataFrame()
        def __init__(self):
            super().__init__('测试', '测试', 'test')

    strategy = TestStrategy()
    timing = TimingEngine()
    sim = TradingSimulator(strategy, timing)

    # 第1天买入
    date1 = '2026-06-01'
    result, msg = sim.execute_buy('000001', '测试', 10.0, 'test', date=date1)

    if result is None:
        print(f"  ❌ 买入失败: {msg}")
        return False

    # 第1天检查卖出（hold_days=0，应该被拒绝）
    should_sell, reason = sim.check_and_sell('000001', 12.0, date=date1)

    if should_sell:
        print(f"  ❌ FAIL: T+1限制失效！当天买当天卖了")
        return False
    else:
        print(f"  ✅ PASS: T+1限制生效，当天买不能当天卖")

    # 第2天检查卖出（hold_days=1，可以卖）
    date2 = '2026-06-02'
    strategy.update_holdings()  # hold_days += 1
    should_sell2, reason2 = sim.check_and_sell('000001', 12.0, date=date2)

    if not should_sell2:
        print(f"  ❌ FAIL: 第2天仍然不能卖（hold_days应该=1）")
        return False
    else:
        print(f"  ✅ PASS: 第2天可以卖出: {reason2}")

    return True


def test_stop_loss_profit_trigger():
    """测试3: 止盈止损正确触发"""
    print("\n=== 测试3: 止盈止损触发 ===")
    from trading.simulator import TradingSimulator
    from strategies.base import FactorStrategy
    from timing.timing import TimingEngine

    class TestStrategy(FactorStrategy):
        def calculate_factor(self, helper, date=None):
            import pandas as pd
            return pd.DataFrame()
        def __init__(self):
            super().__init__('测试', '测试', 'test')

    strategy = TestStrategy()
    timing = TimingEngine()
    sim = TradingSimulator(strategy, timing)

    # 买入价10元
    date1 = '2026-06-01'
    result, msg = sim.execute_buy('000001', '测试', 10.0, 'test', date=date1)

    if result is None:
        print(f"  ❌ 买入失败: {msg}")
        return False

    # 第2天，涨到11.5元（+15%，应触发止盈）
    date2 = '2026-06-02'
    strategy.update_holdings()
    should_sell, reason = sim.check_and_sell('000001', 11.5, date=date2)

    if '止盈' in str(reason):
        print(f"  ✅ PASS: 止盈触发 ({reason})")
    else:
        print(f"  ❌ FAIL: 应触发止盈，实际: {reason}")
        return False

    # 测试止损
    strategy2 = TestStrategy()
    sim2 = TradingSimulator(strategy2, timing)
    sim2.execute_buy('000002', '测试', 10.0, 'test', date=date1)

    date3 = '2026-06-02'
    strategy2.update_holdings()
    should_sell2, reason2 = sim2.check_and_sell('000002', 8.9, date=date3)  # -11%

    if '止损' in str(reason2):
        print(f"  ✅ PASS: 止损触发 ({reason2})")
    else:
        print(f"  ❌ FAIL: 应触发止损，实际: {reason2}")
        return False

    return True


def test_no_duplicate_buy():
    """测试4: 已持仓股票不再被重复选入"""
    print("\n=== 测试4: 已持仓股票不再重复买入 ===")
    from trading.simulator import TradingSimulator
    from strategies.base import FactorStrategy
    from timing.timing import TimingEngine

    class TestStrategy(FactorStrategy):
        def calculate_factor(self, helper, date=None):
            import pandas as pd
            return pd.DataFrame()
        def __init__(self):
            super().__init__('测试', '测试', 'test')

    strategy = TestStrategy()
    timing = TimingEngine()
    sim = TradingSimulator(strategy, timing)

    # 第1天买入000001
    date1 = '2026-06-01'
    result1, msg1 = sim.execute_buy('000001', '测试', 10.0, 'test', date=date1)
    print(f"  第1次买入: {msg1}")

    if result1 is None:
        print(f"  ❌ 第1次买入失败: {msg1}")
        return False

    # 第2天尝试再次买入000001（应该在can_buy检查中被拒绝）
    date2 = '2026-06-02'
    strategy.update_holdings()
    result2, msg2 = sim.execute_buy('000001', '测试', 11.0, 'test', date=date2)

    if result2 is None and '持仓中' in str(msg2):
        print(f"  ✅ PASS: 已持仓股票被正确拒绝 ({msg2})")
        return True
    elif result2 is not None:
        print(f"  ❌ FAIL: 已持仓股票被重复买入！")
        return False
    else:
        print(f"  ⚠️  可能通过其他原因被拒绝: {msg2}")
        return False


def test_equity_curve_has_date():
    """测试5: equity_curve 包含日期信息"""
    print("\n=== 测试5: equity_curve 包含日期信息 ===")
    from backtest_history import run_strategy_on_date
    from data.akshare_helper import AKShareHelper
    from timing.timing import TimingEngine
    from backtest import get_all_strategies

    strategies = get_all_strategies()
    if not strategies:
        print("  ❌ 没有策略可测试")
        return False

    # 找一个简单的策略
    strategy = strategies[0]
    helper = AKShareHelper()
    timing = TimingEngine()

    # 运行一天回测
    test_date = '2026-06-01'
    result = run_strategy_on_date(strategy, helper, timing, test_date)

    if result is None:
        print(f"  ❌ 回测运行失败")
        return False

    equity = strategy.equity_curve[-1]
    if isinstance(equity, dict) and 'date' in equity:
        print(f"  ✅ PASS: equity_curve 包含日期: {equity}")
        return True
    else:
        print(f"  ❌ FAIL: equity_curve 格式不正确: {equity}")
        return False


def test_sell_date_is_correct():
    """测试6: 卖出日期应该是实际卖出日期"""
    print("\n=== 测试6: 卖出日期正确 ===")
    from trading.simulator import TradingSimulator
    from strategies.base import FactorStrategy
    from timing.timing import TimingEngine

    class TestStrategy(FactorStrategy):
        def calculate_factor(self, helper, date=None):
            import pandas as pd
            return pd.DataFrame()
        def __init__(self):
            super().__init__('测试', '测试', 'test')

    strategy = TestStrategy()
    timing = TimingEngine()
    sim = TradingSimulator(strategy, timing)

    # 第1天买入
    date1 = '2026-06-01'
    sim.execute_buy('000001', '测试', 10.0, 'test', date=date1)

    # 第2天卖出
    date2 = '2026-06-02'
    strategy.update_holdings()
    should_sell, reason = sim.check_and_sell('000001', 12.0, date=date2)

    if should_sell:
        trade = sim.execute_sell('000001', 12.0, '止盈', sell_date=date2)
        if trade:
            print(f"  买入日期: {trade['buy_date']}")
            print(f"  卖出日期: {trade['sell_date']}")
            print(f"  持有天数: {trade['hold_days']}")

            if trade['sell_date'] == date2:
                print(f"  ✅ PASS: 卖出日期正确 = {date2}")
                return True
            else:
                print(f"  ❌ FAIL: 卖出日期应该是 {date2}，实际是 {trade['sell_date']}")
                return False
        else:
            print(f"  ❌ FAIL: 卖出失败")
            return False
    else:
        print(f"  ❌ FAIL: 检查卖出失败: {reason}")
        return False


def main():
    print("=" * 60)
    print("回测修复验证测试")
    print("=" * 60)

    results = []
    results.append(("测试1: buy_date历史日期", test_buy_date_is_historical()))
    results.append(("测试2: T+1限制", test_t_plus_1_restriction()))
    results.append(("测试3: 止盈止损触发", test_stop_loss_profit_trigger()))
    results.append(("测试4: 不重复买入", test_no_duplicate_buy()))
    results.append(("测试6: 卖出日期正确", test_sell_date_is_correct()))
    results.append(("测试5: equity_curve带日期", test_equity_curve_has_date()))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = 0
    failed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("\n🎉 所有测试通过！可以运行正式回测。")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请先修复。")
        return 1


if __name__ == '__main__':
    sys.exit(main())
