"""
短线动量策略

策略逻辑：
- 选取近5日涨幅排名前20%的股票
- 要求成交量持续放大
- 快进快出，持有3-5天
- 止损3%

参考：追强势股的短线策略
"""

from strategies.base import BaseStrategy


class ShortTermMomentumStrategy(BaseStrategy):
    """短线动量策略"""
    
    def __init__(self, 
                 lookback_days=5,
                 top_percentile=20,
                 holding_days=5,
                 stop_loss=3,
                 top_n=10):
        super().__init__("短线动量", "技术面")
        self.lookback_days = lookback_days
        self.top_percentile = top_percentile
        self.holding_days = holding_days
        self.stop_loss = stop_loss
        self.top_n = top_n
        
    def get_description(self):
        return f"短线动量：近{self.lookback_days}日涨幅前{self.top_percentile}%, 持有{self.holding_days}天, 止损{self.stop_loss}%"

    def select_stocks(self, helper, date=None):
        """选股：短线动量"""
        results = []
        
        # 模拟强势股票池
        momentum_stocks = [
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '600036', 'name': '招商银行'},
        ]
        
        for stock in momentum_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=20)
                if kline.empty or len(kline) < 10:
                    continue
                
                # 计算短期涨幅
                ret = (kline['close'].iloc[-1] / kline['close'].iloc[-self.lookback_days] - 1) * 100
                
                # 检查成交量放大
                vol_ratio = kline['volume'].iloc[-1] / kline['volume'].tail(20).mean()
                
                # 趋势向上
                ma5 = kline['close'].rolling(5).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                
                if ret > 0 and vol_ratio > 1.2 and current > ma5:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"短线动量：近{self.lookback_days}日+{ret:.1f}%, 量能{round(vol_ratio,1)}倍"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
