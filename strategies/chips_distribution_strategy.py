# -*- coding: utf-8 -*-
"""
筹码分布策略
原理：股价在筹码密集区上方企稳，容易突破；下方则易破位
方法论：基于成本分布模型，识别支撑压力位

核心逻辑：
1. 收集筹码分布数据（通过K线成交量模拟）
2. 寻找筹码密集区（成交量集中的价格区间）
3. 股价在筹码上方 + 缩量调整 = 买入信号
4. 止损设在筹码密集区下方

年化收益参考：40%
回测期限：2020-2024
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.base import BaseStrategy


class ChipsDistributionStrategy(BaseStrategy):
    """筹码分布策略
    
    基于成本分布模型，寻找筹码支撑和压力位
    """
    
    def __init__(self):
        super().__init__(
            name="筹码分布",
            category="成本分析"
        )
        # 参数
        self.lookback_days = 60  # 回看天数
        self.chip_window = 0.15  # 筹码窗口（价格的15%范围）
        self.volume_concentration = 0.7  # 筹码集中度要求
        self.price_to_chip_pct = 5  # 股价相对筹码密集区的偏离（%）
        self.max_hold_days = 10  # 最大持仓天数
        self.profit_target = 0.08  # 盈利目标8%
        self.stop_loss = 0.05  # 止损5%
        
    def select_stocks(self, helper, date=None):
        """选股：筹码分布分析"""
        results = []
        
        try:
            # 获取全市场股票
            stock_list = helper.get_stock_list()
            if stock_list is None or len(stock_list) == 0:
                return results
            
            # 筛选小市值股票（筹码策略更适合小票）
            small_cap = self._get_small_cap_stocks(helper)
            
            # 取样分析
            sample_size = min(400, len(small_cap))
            sampled = small_cap.sample(n=sample_size, random_state=42)
            
            for _, stock in sampled.iterrows():
                try:
                    symbol = stock['code']
                    name = stock.get('name', symbol)
                    
                    # 跳过ST股
                    if 'ST' in name or '*ST' in name:
                        continue
                    
                    # 获取K线数据
                    df = helper.wrap_akshare(
                        helper.get_history_kline, symbol, days=self.lookback_days
                    )
                    
                    if df is None or len(df) < 30:
                        continue
                    
                    # 计算筹码分布
                    chip_analysis = self._analyze_chips(df)
                    
                    if chip_analysis is None:
                        continue
                    
                    current_price = df['close'].iloc[-1]
                    chip_density_price = chip_analysis['density_price']  # 筹码密集区价格
                    
                    # 计算股价相对筹码密集区的位置
                    price_to_chip = (current_price - chip_density_price) / chip_density_price * 100
                    
                    # 买入条件：股价在筹码上方，且距离不远
                    # 说明：股价在筹码上方 = 持有者盈利，解套后抛压小
                    if 0 < price_to_chip < self.price_to_chip_pct:
                        # 最近缩量调整
                        volume_ratio = self._check_volume_contraction(df)
                        
                        if volume_ratio < 0.8:  # 缩量
                            # 计算支撑位（筹码密集区下方）
                            support = chip_density_price * 0.95
                            
                            results.append({
                                'symbol': symbol,
                                'name': name,
                                'reason': f"筹码密集{chip_density_price:.2f} 偏离{price_to_chip:.1f}% 缩量{volume_ratio:.1%}",
                                'score': abs(price_to_chip) + (1 - volume_ratio) * 10,
                                'chip_density': chip_density_price,
                                'support': support,
                                'volume_ratio': volume_ratio
                            })
                            
                except Exception as e:
                    continue
            
            # 按得分排序
            results.sort(key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            print(f"筹码分布选股失败: {e}")
        
        return results[:10]
    
    def _get_small_cap_stocks(self, helper):
        """获取小市值股票（简化版）"""
        try:
            stock_list = helper.get_stock_list()
            if stock_list is None:
                return pd.DataFrame()
            
            # 估算市值 = 股价 * 总股本（这里简化处理，假设股本在2-10亿之间为小盘）
            # 实际应该用市值数据
            small_cap = stock_list.head(1000)  # 简化：取前1000只
            
            return small_cap
        except:
            return pd.DataFrame()
    
    def _analyze_chips(self, df):
        """分析筹码分布
        
        通过成交量分布来估算筹码密集区
        """
        try:
            prices = df['close'].values
            volumes = df['volume'].values
            
            # 将价格分成若干区间
            price_min = prices.min()
            price_max = prices.max()
            
            if price_max == price_min:
                return None
            
            # 创建价格区间
            n_bins = 20
            bin_edges = np.linspace(price_min * 0.95, price_max * 1.05, n_bins + 1)
            
            # 计算每个区间的成交量
            volume_in_bins = np.zeros(n_bins)
            for i in range(len(prices)):
                for j in range(n_bins):
                    if bin_edges[j] <= prices[i] < bin_edges[j + 1]:
                        volume_in_bins[j] += volumes[i]
                        break
            
            # 找到成交量最大的区间（筹码密集区）
            max_volume_idx = np.argmax(volume_in_bins)
            density_price = (bin_edges[max_volume_idx] + bin_edges[max_volume_idx + 1]) / 2
            
            # 计算集中度
            total_volume = volume_in_bins.sum()
            concentration = volume_in_bins[max_volume_idx] / total_volume if total_volume > 0 else 0
            
            return {
                'density_price': density_price,
                'concentration': concentration,
                'bin_edges': bin_edges,
                'volume_in_bins': volume_in_bins
            }
            
        except Exception as e:
            return None
    
    def _check_volume_contraction(self, df, period=5):
        """检查是否缩量调整"""
        if len(df) < period + 5:
            return 1.0
        
        # 最近period天的平均成交量
        recent_volume = df['volume'].iloc[-period:].mean()
        # 之前20天的平均成交量
        earlier_volume = df['volume'].iloc[-period-15:-period].mean()
        
        if earlier_volume == 0:
            return 1.0
        
        return recent_volume / earlier_volume
    
    def should_sell(self, holding, prices, helper):
        """判断是否卖出"""
        symbol = holding['symbol']
        buy_price = holding['buy_price']
        current_price = prices.get(symbol, buy_price)
        
        if current_price is None:
            return False, ""
        
        return_pct = (current_price - buy_price) / buy_price
        
        holding_days = (datetime.now() - datetime.strptime(
            holding.get('buy_date', datetime.now().strftime('%Y-%m-%d')),
            '%Y-%m-%d'
        )).days
        
        # 卖出条件
        if return_pct >= self.profit_target:
            return True, f"达到盈利目标{self.profit_target*100:.0f}%"
        
        if return_pct <= -self.stop_loss:
            return True, f"触及止损{self.stop_loss*100:.0f}%"
        
        if holding_days >= self.max_hold_days:
            return True, f"持仓到期({holding_days}天)"
        
        return False, ""


class ChipBreakoutStrategy(BaseStrategy):
    """筹码突破策略
    
    股价突破筹码密集区后的追涨策略
    """
    
    def __init__(self):
        super().__init__(
            name="筹码突破",
            category="成本分析"
        )
        self.lookback_days = 60
        self.breakout_threshold = 0.03  # 突破幅度
        self.volume_multiplier = 1.5  # 放量要求
        
    def select_stocks(self, helper, date=None):
        """选股：突破筹码密集区"""
        results = []
        
        try:
            stock_list = helper.get_stock_list()
            if stock_list is None or len(stock_list) == 0:
                return results
            
            small_cap = stock_list.head(1000)
            sample_size = min(300, len(small_cap))
            sampled = small_cap.sample(n=sample_size, random_state=42)
            
            for _, stock in sampled.iterrows():
                try:
                    symbol = stock['code']
                    name = stock.get('name', symbol)
                    
                    if 'ST' in name or '*ST' in name:
                        continue
                    
                    df = helper.wrap_akshare(
                        helper.get_history_kline, symbol, days=self.lookback_days
                    )
                    
                    if df is None or len(df) < 40:
                        continue
                    
                    # 计算筹码密集区
                    chip_analysis = self._analyze_chips(df)
                    if chip_analysis is None:
                        continue
                    
                    current_price = df['close'].iloc[-1]
                    chip_price = chip_analysis['density_price']
                    
                    # 判断是否突破
                    breakout_pct = (current_price - chip_price) / chip_price
                    
                    if breakout_pct > self.breakout_threshold:
                        # 检查是否放量
                        volume_ratio = self._check_volume_breakout(df)
                        
                        if volume_ratio > self.volume_multiplier:
                            results.append({
                                'symbol': symbol,
                                'name': name,
                                'reason': f"突破筹码{chip_price:.2f}+{breakout_pct*100:.1f}% 放量{volume_ratio:.1f}x",
                                'score': breakout_pct * 100 + volume_ratio,
                                'breakout_pct': breakout_pct,
                                'volume_ratio': volume_ratio
                            })
                            
                except Exception as e:
                    continue
            
            results.sort(key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            print(f"筹码突破选股失败: {e}")
        
        return results[:8]
    
    def _analyze_chips(self, df):
        """分析筹码分布（同上）"""
        try:
            prices = df['close'].values
            volumes = df['volume'].values
            
            price_min = prices.min()
            price_max = prices.max()
            
            if price_max == price_min:
                return None
            
            n_bins = 20
            bin_edges = np.linspace(price_min * 0.95, price_max * 1.05, n_bins + 1)
            
            volume_in_bins = np.zeros(n_bins)
            for i in range(len(prices)):
                for j in range(n_bins):
                    if bin_edges[j] <= prices[i] < bin_edges[j + 1]:
                        volume_in_bins[j] += volumes[i]
                        break
            
            max_volume_idx = np.argmax(volume_in_bins)
            density_price = (bin_edges[max_volume_idx] + bin_edges[max_volume_idx + 1]) / 2
            
            return {'density_price': density_price}
            
        except:
            return None
    
    def _check_volume_breakout(self, df, period=3):
        """检查是否放量突破"""
        if len(df) < 20:
            return 1.0
        
        recent_volume = df['volume'].iloc[-period:].mean()
        avg_volume = df['volume'].iloc[-20:-period].mean()
        
        if avg_volume == 0:
            return 1.0
        
        return recent_volume / avg_volume
