# -*- coding: utf-8 -*-
"""
情绪冰点抄底策略
原理：在市场情绪极度悲观时买入，超跌反弹概率高
方法论：基于集思录情绪指标、恐慌指数、超买超卖指标

核心逻辑：
1. 情绪冰点特征：涨跌家数比极低、涨停稀少、炸板率高
2. 超跌信号：RSI<20 或 股价距离MA20超跌15%以上
3. 配合缩量（抛压衰竭）+ 支撑位

年化收益参考：待测
回测期限：2020-2024
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.base import BaseStrategy


class SentimentIcePointStrategy(BaseStrategy):
    """情绪冰点抄底策略
    
    在市场情绪极度悲观时买入超跌股票，等待反弹
    """
    
    def __init__(self):
        super().__init__(
            name="情绪冰点抄底",
            category="情绪反转"
        )
        # 参数
        self.min_rsi = 25  # RSI超卖阈值
        self.max_rsi = 40  # 抄底RSI上限
        self.overshoot_pct = 12  # 相对MA20超跌比例
        self.volume_ratio_min = 0.5  # 缩量比（相比20日均量）
        self.volume_ratio_max = 0.85  # 缩量上限
        self.max_hold_days = 5  # 最大持仓天数
        self.profit_target = 0.05  # 盈利目标5%
        self.stop_loss = 0.03  # 止损3%
        self.min_market_sentiment = 0.2  # 市场情绪最低要求（0-1）
        
    def select_stocks(self, helper, date=None):
        """选股：情绪冰点 + 超跌信号"""
        results = []
        
        try:
            # 1. 获取市场情绪指标
            sentiment = self._get_market_sentiment(helper)
            
            # 如果市场情绪不差，不抄底
            if sentiment > self.min_market_sentiment:
                return results
            
            # 2. 获取全市场股票
            stock_list = helper.get_stock_list()
            if stock_list is None or len(stock_list) == 0:
                return results
            
            # 3. 筛选超跌股票（取样，减少计算量）
            sample_size = min(500, len(stock_list))
            sampled = stock_list.sample(n=sample_size, random_state=42)
            
            for _, stock in sampled.iterrows():
                try:
                    symbol = stock['code']
                    name = stock.get('name', symbol)
                    
                    # 跳过ST股
                    if 'ST' in name or '*ST' in name:
                        continue
                    
                    # 获取K线数据
                    df = helper.wrap_akshare(
                        helper.get_history_kline, symbol, days=30
                    )
                    
                    if df is None or len(df) < 20:
                        continue
                    
                    # 4. 计算技术指标
                    current_price = df['close'].iloc[-1]
                    ma20 = df['close'].iloc[-20:].mean() if len(df) >= 20 else df['close'].mean()
                    
                    # RSI计算
                    rsi = self._calculate_rsi(df['close'], period=14)
                    current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
                    
                    # 超跌幅度
                    overshoot_pct = (ma20 - current_price) / ma20 * 100
                    
                    # 量能判断（缩量）
                    volume_ma20 = df['volume'].iloc[-20:].mean()
                    current_volume = df['volume'].iloc[-1]
                    volume_ratio = current_volume / volume_ma20 if volume_ma20 > 0 else 1
                    
                    # 5. 判断是否满足抄底条件
                    conditions = [
                        current_rsi < self.max_rsi,  # RSI不过高
                        overshoot_pct > 5,  # 有一定超跌
                        volume_ratio < self.volume_ratio_max,  # 量能萎缩
                    ]
                    
                    if all(conditions):
                        # 计算得分（越低分越高）
                        score = current_rsi + overshoot_pct
                        
                        # 优先选择RSI极低的
                        if current_rsi < self.min_rsi:
                            score -= 30
                        
                        results.append({
                            'symbol': symbol,
                            'name': name,
                            'reason': f"情绪冰点 RSI={current_rsi:.1f} 超跌{overshoot_pct:.1f}% 量比={volume_ratio:.2f}",
                            'score': score,
                            'current_rsi': current_rsi,
                            'overshoot_pct': overshoot_pct,
                            'volume_ratio': volume_ratio
                        })
                        
                except Exception as e:
                    continue
            
            # 按得分排序（低分优先）
            results.sort(key=lambda x: x['score'])
            
        except Exception as e:
            print(f"情绪冰点选股失败: {e}")
        
        return results[:10]  # 最多选10只
    
    def _get_market_sentiment(self, helper):
        """获取市场情绪指标（简化版）
        
        Returns: 情绪值 0-1，0=极度恐慌，1=极度贪婪
        """
        try:
            # 获取涨跌停数据
            limit_up_df = helper.wrap_akshare(
                helper.get_limit_list, date=None
            )
            
            if limit_up_df is not None and len(limit_up_df) > 0:
                limit_up_count = len(limit_up_df)
            else:
                limit_up_count = 10  # 默认值
            
            # 情绪指标：涨停家数越少，情绪越低
            # 正常涨停50+为情绪高涨，<20为情绪低迷
            sentiment = min(limit_up_count / 50, 1.0)
            
            return sentiment
            
        except Exception as e:
            print(f"获取市场情绪失败: {e}")
            return 0.5  # 返回中性情绪
    
    def _calculate_rsi(self, prices, period=14):
        """计算RSI"""
        deltas = prices.diff()
        gains = deltas.where(deltas > 0, 0)
        losses = -deltas.where(deltas < 0, 0)
        
        avg_gain = gains.rolling(window=period).mean()
        avg_loss = losses.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def should_buy(self, stock, helper):
        """判断是否买入（由父类决定何时调用）"""
        # 选股时已经做了筛选，补充市场时机判断
        return True
    
    def should_sell(self, holding, prices, helper):
        """判断是否卖出"""
        symbol = holding['symbol']
        buy_price = holding['buy_price']
        current_price = prices.get(symbol, buy_price)
        
        if current_price is None:
            return False, ""
        
        # 计算收益率
        return_pct = (current_price - buy_price) / buy_price
        
        # 持仓天数
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
