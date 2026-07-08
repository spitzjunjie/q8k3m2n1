"""
反过度自信策略

策略逻辑：
- 选取近期跌幅较大（10-30%）的股票
- 要求RSI < 40（超卖）
- 在市场恐慌时买入，逆向投资
- 持有10天或达到目标收益卖出

参考：人弃我取的逆向投资理念
"""

from strategies.base import BaseStrategy


class AntiOverconfidenceStrategy(BaseStrategy):
    """反过度自信策略"""
    
    def __init__(self, 
                 drop_range=(10, 30),
                 max_rsi=40,
                 holding_days=10,
                 top_n=10):
        super().__init__("反过度自信", "逆向策略")
        self.drop_min, self.drop_max = drop_range
        self.max_rsi = max_rsi
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"反过度自信：跌幅{self.drop_min}-{self.drop_max}%, RSI<{self.max_rsi}，逆向买入"

    def select_stocks(self, helper, date=None):
        """选股：超跌后企稳"""
        results = []
        
        # 模拟超跌股票池
        oversold_stocks = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002236', 'name': '大华股份'},
            {'symbol': '002352', 'name': '顺丰控股'},
        ]
        
        for stock in oversold_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 20:
                    continue
                
                # 计算跌幅
                ret_20d = (kline['close'].iloc[-1] / kline['close'].iloc[-20] - 1) * 100
                
                # 计算RSI
                delta = kline['close'].diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss
                rsi = (100 - (100 / (1 + rs))).iloc[-1]
                
                # 条件：跌幅在范围内 + RSI超卖 + 价格企稳
                if self.drop_min < abs(ret_20d) < self.drop_max and rsi < self.max_rsi:
                    if kline['close'].iloc[-1] > kline['close'].iloc[-3]:
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': f"反过度自信：近20日跌幅{ret_20d:.1f}%, RSI={rsi:.1f}，企稳信号"
                        })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
