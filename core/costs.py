# -*- coding: utf-8 -*-
"""
A 股交易成本模型
====================================================================
当前系统在 strategies/base.py 的 add_holding / remove_holding 里
直接用 price * quantity 计算成本与收入，完全没有交易成本。
对于持仓 3-5 天、年换手 80+ 次的短线策略，这会系统性高估收益。

本模块提供一个可直接接入的成本模型。用法见文件末尾。
====================================================================
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    """A 股交易成本参数（2026 年现行规则，可按自己券商调整）

    commission_rate : 佣金费率，双边收取。券商万 2.5 = 0.00025
    min_commission  : 单笔最低佣金，通常 5 元
    stamp_duty      : 印花税，**仅卖出**收取。2023-08-28 起由 0.1% 降至 0.05%
    transfer_fee    : 过户费，双边，沪深两市现均为 0.001%
    slippage_bps    : 滑点（单边，基点）。以收盘价成交的日频回测建议 >= 10bp；
                      小盘股 / 涨跌停附近应更高
    """

    commission_rate: float = 0.00025
    min_commission: float = 5.0
    stamp_duty: float = 0.0005
    transfer_fee: float = 0.00001
    slippage_bps: float = 10.0

    # ---------- 单边成本 ----------

    def buy_cost(self, price: float, quantity: int) -> float:
        """买入总成本（不含股票本身价款）"""
        amount = price * quantity
        commission = max(amount * self.commission_rate, self.min_commission)
        return commission + amount * self.transfer_fee

    def sell_cost(self, price: float, quantity: int) -> float:
        """卖出总成本（不含股票价款）"""
        amount = price * quantity
        commission = max(amount * self.commission_rate, self.min_commission)
        return commission + amount * (self.stamp_duty + self.transfer_fee)

    # ---------- 含滑点的成交价 ----------

    def fill_price_buy(self, ref_price: float) -> float:
        """买入实际成交价（向不利方向偏移滑点）"""
        return ref_price * (1 + self.slippage_bps / 10000.0)

    def fill_price_sell(self, ref_price: float) -> float:
        """卖出实际成交价"""
        return ref_price * (1 - self.slippage_bps / 10000.0)

    # ---------- 便捷方法 ----------

    def round_trip_cost_pct(self, price: float, quantity: int) -> float:
        """一次完整买卖的成本占本金比例（%），用于快速估算成本拖累"""
        amount = price * quantity
        if amount <= 0:
            return 0.0
        total = self.buy_cost(price, quantity) + self.sell_cost(price, quantity)
        total += amount * 2 * self.slippage_bps / 10000.0
        return total / amount * 100

    def annual_drag_pct(self, round_trips_per_year: float,
                        avg_position_value: float,
                        total_capital: float,
                        avg_price: float = 20.0) -> float:
        """给定年换手次数，估算每年的成本拖累（占**总本金** %）

        注意分母是总本金，不是单个仓位。单笔往返成本是相对仓位算的，
        换算到本金要乘以 仓位/本金 的比例。
        """
        qty = max(int(avg_position_value / avg_price / 100) * 100, 100)
        pos_value = qty * avg_price
        cost_per_trip = self.round_trip_cost_pct(avg_price, qty) / 100 * pos_value
        return cost_per_trip * round_trips_per_year / total_capital * 100


DEFAULT_COSTS = CostModel()


# ====================================================================
# 接入方式：修改 strategies/base.py
# ====================================================================
#
# 1) BaseStrategy.__init__ 增加参数：
#
#        def __init__(self, name, category, initial_capital=30000,
#                     costs=None):
#            ...
#            from core.costs import DEFAULT_COSTS
#            self.costs = costs or DEFAULT_COSTS
#            self.total_fees = 0.0          # 累计手续费，用于归因
#
# 2) add_holding 改为：
#
#        fill = self.costs.fill_price_buy(price)
#        gross = fill * quantity
#        fee   = self.costs.buy_cost(fill, quantity)
#        cost  = gross + fee                 # <= 真实占用资金
#        self.current_capital -= cost
#        self.total_fees += fee
#        holding['buy_price'] = fill         # 记录含滑点的成交价
#        holding['cost'] = cost              # 含费用，profit 才算得对
#        holding['entry_fee'] = fee
#
# 3) remove_holding 改为：
#
#        fill    = self.costs.fill_price_sell(sell_price)
#        gross   = fill * holding['quantity']
#        fee     = self.costs.sell_cost(fill, holding['quantity'])
#        revenue = gross - fee
#        profit  = revenue - holding['cost']
#        self.current_capital += revenue
#        self.total_fees += fee
#
# 4) to_dict 增加 'total_fees': round(self.total_fees, 2)，
#    这样仪表盘能显示"手续费吃掉了多少收益"。
#
# ====================================================================

if __name__ == '__main__':
    m = DEFAULT_COSTS
    print("A 股成本模型自检")
    print("=" * 56)
    for price, value in [(10.0, 10000), (35.6, 7120), (100.0, 10000), (1800.0, 18000)]:
        qty = max(int(value / price / 100) * 100, 100)
        print(f"  价格 {price:>7.2f}  {qty:>5}股  单次往返成本 "
              f"{m.round_trip_cost_pct(price, qty):.3f}%")
    print("-" * 56)
    print("年度成本拖累（3 万本金，单仓 1 万，均价 20 元）：")
    for rt in (20, 50, 84, 150):
        drag = m.annual_drag_pct(rt, avg_position_value=10000,
                                 total_capital=30000, avg_price=20.0)
        print(f"  年往返 {rt:>3} 次 → 约 {drag:>5.2f}% / 年")
    print("=" * 56)
    print("对照：当前 23 个有成交策略，30 天内每个都做了 10 笔往返，")
    print("      年化约 84 次换手。账面 30 日平均收益 +3.72%，")
    print("      而光成本一年就要吃掉 4~10 个百分点。")
    print("      现在的回测里这部分是 0 —— 所有收益数字都偏高。")
