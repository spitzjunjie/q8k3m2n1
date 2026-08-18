# -*- coding: utf-8 -*-
"""状态续接：backtest.py 水合 + proper_merge.py 合并逻辑"""


def _sample_strategy_data():
    return {
        'name': '测试策略',
        'initial_capital': 30000,
        'current_capital': 6852.0,
        'realized_pnl': 123.0,
        'realized_pnl_pct': 0.41,
        'total_fees': 50.0,
        'holdings': [
            {
                'symbol': '688035', 'name': '德邦科技',
                'buy_price': 92.36, 'quantity': 100, 'buy_date': '2026-07-02',
                'cost': 9236.0, 'hold_days': 4,
                'stock_reason': 'x', 'timing_reason': 'y',
            }
        ],
        'trades': [
            {
                'symbol': '688553', 'name': '汇宇制药',
                'buy_date': '2026-07-06', 'sell_date': '2026-07-07',
                'profit': 0.0,
            }
        ],
        'all_trades': [],
        'equity_curve': [
            {'date': '2026-07-03', 'value': 35095.0},
            {'date': '2026-07-07', 'value': 35532.0},
        ],
    }


class _FakeStrategy:
    """最小策略桩：只承载状态字段"""

    def __init__(self):
        self.name = '测试策略'
        self.initial_capital = 30000
        self.current_capital = 30000
        self.holdings = []
        self.trades = []
        self.all_trades = []
        self.realized_pnl = 0.0
        self.realized_pnl_pct = 0.0
        self.total_fees = 0.0
        self.equity_curve = []


def test_hydrate_restores_holdings_trades_and_capital():
    from backtest import hydrate_strategy

    s = _FakeStrategy()
    hydrate_strategy(s, _sample_strategy_data())

    assert len(s.holdings) == 1
    assert s.holdings[0]['symbol'] == '688035'
    assert s.holdings[0]['cost'] == 9236.0
    # all_trades 为空时回退 trades
    assert len(s.all_trades) == 1
    assert s.all_trades[0]['sell_date'] == '2026-07-07'
    assert s.trades == s.all_trades
    assert s.current_capital == 6852.0
    assert s.initial_capital == 30000
    assert s.realized_pnl == 123.0
    assert s.total_fees == 50.0
    assert s.equity_curve[0] == {'date': '2026-07-03', 'value': 35095.0}


def test_hydrate_prefers_all_trades_and_handles_numeric_curve():
    from backtest import hydrate_strategy

    data = _sample_strategy_data()
    data['all_trades'] = [
        {'symbol': 'A', 'buy_date': '2026-06-01', 'sell_date': '2026-06-05'},
        {'symbol': 'B', 'buy_date': '2026-06-02', 'sell_date': '2026-06-06'},
    ]
    data['equity_curve'] = [100.0, 101.5]

    s = _FakeStrategy()
    hydrate_strategy(s, data)

    assert len(s.all_trades) == 2  # all_trades 优先
    assert s.all_trades[0]['symbol'] == 'A'
    assert s.equity_curve == [100.0, 101.5]  # 裸数值兼容


def test_hydrate_empty_data_is_noop():
    from backtest import hydrate_strategy

    s = _FakeStrategy()
    hydrate_strategy(s, None)
    hydrate_strategy(s, {})
    assert s.holdings == []
    assert s.trades == []
    assert s.current_capital == s.initial_capital


def test_merge_preserves_history_and_overlays_state():
    from proper_merge import merge_strategy_state

    old_s = _sample_strategy_data()
    # 新版本：历史 + 今日卖出 + 新持仓 + 新资金
    new_s = _sample_strategy_data()
    new_s['all_trades'] = [
        {'symbol': '688553', 'name': '汇宇制药', 'buy_date': '2026-07-06', 'sell_date': '2026-07-07', 'profit': 0.0},
        {'symbol': '600519', 'name': '贵州茅台', 'buy_date': '2026-07-28', 'sell_date': '2026-08-06', 'profit': 88.0},
    ]
    new_s['trades'] = list(new_s['all_trades'])
    new_s['holdings'] = [
        {'symbol': '000001', 'name': '平安银行', 'buy_price': 10.0, 'quantity': 500,
         'buy_date': '2026-08-06', 'cost': 5000.0, 'hold_days': 0},
    ]
    new_s['current_capital'] = 20000.0
    new_s['total_value'] = 25000.0
    new_s['total_return'] = -0.16

    merged = merge_strategy_state(old_s, new_s)

    # 历史 + 新增交易，且不重复
    assert len(merged['all_trades']) == 2
    keys = {(t['symbol'], t['buy_date'], t['sell_date']) for t in merged['all_trades']}
    assert ('688553', '2026-07-06', '2026-07-07') in keys
    assert ('600519', '2026-07-28', '2026-08-06') in keys
    # 最新状态覆盖
    assert merged['holdings'][0]['symbol'] == '000001'
    assert merged['current_capital'] == 20000.0
    assert merged['total_value'] == 25000.0
    assert merged['total_return'] == -0.16
    # 截断展示字段
    assert merged['trades'] == merged['all_trades']


def test_merge_dedups_same_trade():
    from proper_merge import merge_strategy_state

    old_s = _sample_strategy_data()  # trades 里已有一条 688553 交易
    new_s = _sample_strategy_data()
    new_s['all_trades'] = [
        {'symbol': '688553', 'name': '汇宇制药', 'buy_date': '2026-07-06', 'sell_date': '2026-07-07', 'profit': 0.0},
        {'symbol': '688553', 'name': '汇宇制药', 'buy_date': '2026-07-06', 'sell_date': '2026-07-07', 'profit': 0.0},
    ]
    new_s['trades'] = new_s['all_trades']

    merged = merge_strategy_state(old_s, new_s)
    assert len(merged['all_trades']) == 1  # 完全重复只保留一条
