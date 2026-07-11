# -*- coding: utf-8 -*-
"""
筹码分布策略：基于筹码集中度和位置判断买卖信号
核心逻辑：筹码集中度 + 位置 = 买卖信号

买入信号：
1. 筹码集中度 > 70%
2. 筹码集中在20%价格区间内
3. 股价在低位
4. 放量突破（成交额 > 5日均量2倍）

卖出信号：
1. 筹码高位密集
2. 股价跌破筹码密集区
3. 缩量（主力出货）
"""

import pandas as pd
import numpy as np
from strategies.base import EventStrategy


class ChipDistributionStrategy(EventStrategy):
    """筹码分布策略"""

    def __init__(self):
        super().__init__("筹码分布", category="技术/筹码")

    def get_description(self):
        return "筹码集中度>70%+低位密集+放量突破，捕捉主力建仓"

    def get_params(self):
        return {
            'concentration_threshold': 70,  # 集中度阈值(%)
            'width_threshold': 20,  # 筹码区间宽度阈值(%)
            'volume_multiplier': 2,  # 放量倍数
            'hold_days': 20,  # 持仓天数
        }

    def get_universe(self, helper, sample=80):
        """获取股票池（沪深300，按市值降序抽样）"""
        try:
            stocks = helper.get_stock_pool("hs300", sorted_by_market_value=True)
            if stocks:
                return stocks[:sample] if len(stocks) > sample else stocks
        except Exception:
            pass
        # 兜底：硬编码蓝筹+热门股池
        fallback = [
            '600519', '300750', '600036', '601318', '000858',
            '002475', '300033', '300059', '000001', '600030',
            '601166', '600900', '601012', '002594', '600276',
            '000333', '688981', '688012', '688256', '002236',
            '002352', '601398', '601328', '600016', '601288',
        ]
        return fallback[:sample]

    def calculate_chip_metrics(self, kline_df, current_price):
        """
        计算筹码分布指标
        基于价格分布和波动率计算筹码集中度和位置
        
        Args:
            kline_df: K线数据DataFrame
            current_price: 当前股价
            
        Returns:
            dict: 筹码指标 {'concentration': float, 'width': float, 'position': str}
        """
        if kline_df is None or len(kline_df) < 30:
            return {'concentration': 0, 'width': 100, 'position': 'unknown'}
        
        # 使用最近20日数据计算
        df = kline_df.copy()
        recent_df = df.tail(20)
        recent_prices = recent_df['close']
        
        # 计算筹码区间宽度（价格分布范围/均价）
        # 筹码越集中，价格区间越窄
        p10 = recent_prices.quantile(0.1)
        p90 = recent_prices.quantile(0.9)
        width = (p90 - p10) / recent_prices.mean() * 100 if recent_prices.mean() > 0 else 100
        
        # 计算价格波动率（日收益率标准差）
        daily_returns = recent_prices.pct_change().dropna()
        volatility = daily_returns.std() * 100 if len(daily_returns) > 1 else 0
        
        # 计算筹码集中度（综合指标）
        # 1. 宽度集中度：宽度越小，集中度越高（权重40%）
        # 2. 波动集中度：波动越小，集中度越高（权重30%）
        # 3. 趋势稳定性：最近10日均值与20日均值接近（权重30%）
        ma10 = recent_prices.tail(10).mean()
        ma20 = recent_prices.mean()
        trend_stability = 100 - abs(ma10 - ma20) / ma20 * 100
        
        width_score = max(0, 100 - width * 3)  # 宽度越窄分越高
        volatility_score = max(0, 100 - volatility * 10)  # 波动越小分越高
        
        # 综合集中度（0-100）
        concentration = (width_score * 0.4 + volatility_score * 0.3 + trend_stability * 0.3)
        concentration = max(0, min(100, concentration))
        
        # 计算获利盘比例
        profit_ratio = self._calc_profit_ratio(kline_df, current_price)
        
        # 判断位置（相对高低位）
        # 当前价相对于近期高低点的位置
        high_20 = recent_df['high'].max()
        low_20 = recent_df['low'].min()
        price_position = (current_price - low_20) / (high_20 - low_20) * 100 if high_20 > low_20 else 50
        
        if price_position < 30:
            position = 'low'
        elif price_position > 70:
            position = 'high'
        else:
            position = 'middle'
        
        return {
            'concentration': float(concentration),
            'width': float(width),
            'position': position,
            'profit_ratio': float(profit_ratio),
            'price_position': float(price_position)
        }

    def _calc_profit_ratio(self, kline_df, current_price):
        """计算获利盘比例"""
        if kline_df is None or len(kline_df) < 20:
            return 50.0
        
        # 简化：使用最近N日平均成本估算获利比例
        recent = kline_df.tail(60)
        avg_cost = recent['close'].mean()
        
        if current_price > avg_cost:
            profit_ratio = 50 + (current_price - avg_cost) / avg_cost * 100
        else:
            profit_ratio = 50 - (avg_cost - current_price) / avg_cost * 100
        
        return min(100, max(0, profit_ratio))

    def get_chip_distribution(self, helper, symbol):
        """
        获取筹码分布数据（使用AKShare接口）
        
        Args:
            helper: 数据助手
            symbol: 股票代码
            
        Returns:
            dict: 筹码分布数据
        """
        try:
            # 尝试使用AKShare接口获取筹码数据
            chip_data = helper.get_chip_distribution(symbol)
            if chip_data and chip_data.get('concentration'):
                return chip_data
        except Exception:
            pass
        
        # 降级方案：使用K线数据计算
        kline = helper.get_history_kline(symbol, days=60)
        if kline is None or kline.empty:
            return {}
        
        current_price = kline['close'].iloc[-1]
        return self.calculate_chip_metrics(kline, current_price)

    def detect_events(self, helper, date=None):
        """
        检测筹码分布买入信号
        
        买入条件：
        1. 筹码集中度 > 70%
        2. 筹码集中在20%价格区间内
        3. 股价在低位
        4. 放量突破（成交额 > 5日均量2倍）
        """
        symbols = self.get_universe(helper)
        if not symbols:
            return []

        results = []
        params = self.get_params()
        
        for symbol in symbols:
            try:
                # 获取K线数据
                kline = helper.get_history_kline(symbol, days=60, end_date=date)
                if kline is None or kline.empty or len(kline) < 30:
                    continue
                
                current_price = kline['close'].iloc[-1]
                prev_price = kline['close'].iloc[-2]
                
                # 计算筹码指标
                chip = self.calculate_chip_metrics(kline, current_price)
                
                # 计算成交量放大
                if 'amount' in kline.columns:
                    kline['amount_ma5'] = kline['amount'].rolling(5).mean()
                    latest_amount = kline['amount'].iloc[-1]
                    avg_amount = kline['amount_ma5'].iloc[-2] if len(kline) > 5 else kline['amount'].mean()
                    volume_surge = latest_amount > avg_amount * params['volume_multiplier']
                else:
                    volume_surge = False
                
                # 计算放量突破（股价突破近期高点）
                high_20 = kline['high'].iloc[-21:-1].max() if len(kline) > 20 else kline['high'].max()
                price_breakout = current_price > high_20
                
                # 买入信号条件检查
                concentration_ok = chip['concentration'] > params['concentration_threshold']
                width_ok = chip['width'] < params['width_threshold']
                position_low = chip['position'] == 'low'
                breakout_ok = price_breakout and volume_surge
                
                # 综合信号判断
                if concentration_ok and (width_ok or position_low) and breakout_ok:
                    reason = f"筹码集中度{chip['concentration']:.1f}%，位置{chip['position']}，放量{params['volume_multiplier']}倍突破"
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': reason
                    })
                
                # 限制返回数量
                if len(results) >= 10:
                    break
                    
            except Exception as e:
                continue
        
        return results
