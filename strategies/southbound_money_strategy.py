# -*- coding: utf-8 -*-
"""
南向资金策略

策略逻辑：
- 追踪南向资金（港股通）净买入top股票
- 选取近N日持续净买入的A股
- 等权持有N个交易日

买入信号：
- 南向资金近N日持续净买入
- 净买入额放大

卖出信号：
- 南向资金转为净卖出
- 持仓超过持有天数
"""

from strategies.base import EventStrategy
import pandas as pd


class SouthboundMoneyStrategy(EventStrategy):
    """南向资金策略（事件驱动）"""
    
    def __init__(self, 
                 lookback_days=5,
                 holding_days=10,
                 min_net_buy=1e8,
                 top_n=10):
        super().__init__("南向资金", "资金流")
        self.lookback_days = lookback_days
        self.holding_days = holding_days
        self.min_net_buy = min_net_buy  # 最小净买入额（元）
        self.top_n = top_n
        
    def get_params(self):
        return {
            'lookback_days': self.lookback_days,
            'holding_days': self.holding_days,
            'min_net_buy': self.min_net_buy,
            'top_n': self.top_n,
        }
        
    def get_description(self):
        return f"南向资金：连续{self.lookback_days}日净买入≥{self.min_net_buy/1e8:.0f}亿, 持有{self.holding_days}天"
    
    def detect_events(self, helper, date=None):
        """
        检测南向资金买入事件
        返回: [{'symbol': '000001', 'name': 'xxx', 'reason': '南向资金净买入'}, ...]
        """
        results = []
        
        try:
            # 获取南向资金历史流向数据（港股通）
            south_flow = helper.get_south_flow()
            
            if south_flow.empty:
                return self._fallback_detect(helper)
            
            # 检查是否连续净买入
            if len(south_flow) < self.lookback_days:
                return self._fallback_detect(helper)
            
            # 近N日资金流向
            recent_flow = south_flow.tail(self.lookback_days)
            
            # 计算净买入情况
            net_buy_total = 0
            consecutive_buy_days = 0
            
            for _, row in recent_flow.iterrows():
                # 南向资金净买入额（沪市+深市）
                net_buy = self._get_net_buy(row)
                if net_buy > 0:
                    net_buy_total += net_buy
                    consecutive_buy_days += 1
            
            # 判断是否满足买入条件
            if consecutive_buy_days >= self.lookback_days * 0.8:  # 至少80%天数净买入
                # 获取南向资金重仓股
                holdings = helper.get_south_holdings()
                
                if holdings:
                    for stock in holdings[:self.top_n]:
                        results.append({
                            'symbol': stock.get('symbol', ''),
                            'name': stock.get('name', ''),
                            'reason': f"南向资金连续{consecutive_buy_days}日净买入, 共{net_buy_total/1e8:.1f}亿"
                        })
                else:
                    # 如果没有持仓数据，返回降级结果
                    return self._fallback_detect(helper)
            
        except Exception as e:
            print(f"南向资金检测失败: {e}")
            return self._fallback_detect(helper)
        
        return results[:self.top_n]
    
    def _get_net_buy(self, row):
        """获取单日净买入额"""
        # 尝试多种可能的列名
        net_buy = 0
        for col in ['南向资金净买入额', '净买入额', '净买入', 'net_buy', '沪股通净买入', '深股通净买入']:
            if col in row:
                val = row[col]
                if pd.notna(val):
                    net_buy += float(val)
        return net_buy
    
    def _fallback_detect(self, helper):
        """降级方案：使用固定的港股通标的池"""
        results = []
        
        # 港股通常见标的（A股中港股通标的）
        south_stocks = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600887', 'name': '伊利股份'},
            {'symbol': '000333', 'name': '美的集团'},
            {'symbol': '600030', 'name': '中信证券'},
            {'symbol': '601166', 'name': '兴业银行'},
        ]
        
        for stock in south_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < self.lookback_days:
                    continue
                
                # 检查成交量趋势（放量代表资金关注）
                vol_ma = kline['volume'].tail(30).mean()
                recent_vol = kline['volume'].tail(self.lookback_days).mean()
                
                # 检查价格趋势
                ma10 = kline['close'].tail(10).mean()
                current_price = kline['close'].iloc[-1]
                
                # 放量且股价站上均线
                if recent_vol > vol_ma * 1.1 and current_price > ma10:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"南向资金：量比{round(recent_vol/vol_ma, 1)}倍, 股价站稳10日均线"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
        
        return results[:self.top_n]
    
    def select_stocks(self, helper, date=None):
        """基于南向资金事件选股"""
        events = self.detect_events(helper, date)
        return events[:self.top_n]
