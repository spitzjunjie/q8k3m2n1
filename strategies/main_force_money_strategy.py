# -*- coding: utf-8 -*-
"""
主力资金流入策略
跟踪主力资金（大单）连续净流入的股票
"""

import pandas as pd
import numpy as np
from strategies.base import EventStrategy


class MainForceMoneyStrategy(EventStrategy):
    """主力资金流入策略"""

    def __init__(self, name="主力资金流入", category="资金流向"):
        super().__init__(name, category)
        self.min_net_inflow_rate = 5.0  # 主力资金净流入率阈值（%）
        self.min_volume_ratio = 1.3  # 成交量放大倍数
        self.continuous_days = 3  # 连续净流入天数

    def get_universe(self, helper, sample=100):
        """获取股票池（成交量活跃的股票）"""
        stocks = helper.get_stock_pool("hs300", sorted_by_market_value=True)
        return stocks[:sample] if len(stocks) > sample else stocks

    def get_description(self):
        return f"主力资金连续净流入率>{self.min_net_inflow_rate}%，成交量放大，捕捉大资金动向"

    def detect_events(self, helper, date=None):
        """检测主力资金连续净流入信号"""
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        sample_symbols = symbols[:80]

        for symbol in sample_symbols:
            try:
                # 获取日线数据（用于计算成交量）
                df = helper.get_history_kline(symbol, days=30)
                if df is None or len(df) < 20:
                    continue

                # 获取资金流向数据（需要helper支持）
                money_flow = helper.get_money_flow(symbol, days=30)
                
                if money_flow is None or len(money_flow) < self.continuous_days:
                    continue

                # 计算资金净流入情况
                net_inflow_rates = []
                for i in range(min(self.continuous_days, len(money_flow))):
                    row = money_flow.iloc[-(i+1)]
                    # 主力净流入率 = 主力净流入 / 成交额 * 100
                    main_net = row.get('main_net_inflow', 0)
                    total_amount = row.get('total_amount', 1)
                    if total_amount > 0:
                        net_rate = (main_net / total_amount) * 100
                        net_inflow_rates.append(net_rate)

                if len(net_inflow_rates) < self.continuous_days:
                    continue

                # 判断连续净流入
                continuous_positive = all(rate > self.min_net_inflow_rate for rate in net_inflow_rates)
                
                # 计算当前成交量是否放大
                vol_ma5 = df['volume'].rolling(5).mean().iloc[-1]
                current_vol = df['volume'].iloc[-1]
                volume_ratio = current_vol / vol_ma5 if vol_ma5 > 0 else 0
                volume_surge = volume_ratio > self.min_volume_ratio

                if continuous_positive and volume_surge:
                    avg_rate = sum(net_inflow_rates) / len(net_inflow_rates)
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"主力连续净流入{self.continuous_days}日，平均净流入率{avg_rate:.1f}%，量比{volume_ratio:.2f}"
                    })

                if len(results) >= 10:
                    break

            except Exception as e:
                continue

        return results


class MainForceAccumulationStrategy(MainForceMoneyStrategy):
    """主力吸筹策略 - 温和放量+持续净流入"""

    def __init__(self):
        super().__init__(name="主力吸筹", category="资金流向")
        self.min_net_inflow_rate = 3.0  # 降低阈值
        self.min_volume_ratio = 1.2  # 温和放量

    def get_description(self):
        return "主力温和吸筹，持续净流入+温和放量，潜伏主力建仓"

    def detect_events(self, helper, date=None):
        """检测主力吸筹信号"""
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        sample_symbols = symbols[:80]

        for symbol in sample_symbols:
            try:
                df = helper.get_history_kline(symbol, days=30)
                if df is None or len(df) < 20:
                    continue

                money_flow = helper.get_money_flow(symbol, days=30)
                if money_flow is None or len(money_flow) < 5:
                    continue

                # 计算5日累计净流入
                total_net = 0
                for i in range(min(5, len(money_flow))):
                    row = money_flow.iloc[-(i+1)]
                    main_net = row.get('main_net_inflow', 0)
                    total_amount = row.get('total_amount', 1)
                    if total_amount > 0:
                        net_rate = (main_net / total_amount) * 100
                        total_net += net_rate

                # 判断温和放量（量比1.2-2.0）
                vol_ma10 = df['volume'].rolling(10).mean().iloc[-1]
                current_vol = df['volume'].iloc[-1]
                volume_ratio = current_vol / vol_ma10 if vol_ma10 > 0 else 0
                gentle_surge = 1.2 < volume_ratio < 2.5

                # 5日累计净流入率 > 10%
                if total_net > 10 and gentle_surge:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"主力吸筹，5日累计净流入{total_net:.1f}%，量比{volume_ratio:.2f}"
                    })

                if len(results) >= 10:
                    break

            except Exception as e:
                continue

        return results
