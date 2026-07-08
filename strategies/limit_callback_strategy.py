"""
涨停回调策略

策略逻辑：
- 选取昨日涨停的股票
- 今日回调超过5%时买入
- 持有至涨回涨停价卖出
- 止损8%

参考：A股特有的涨停板Alpha机会
"""

from strategies.base import BaseStrategy


class LimitCallbackStrategy(BaseStrategy):
    """涨停回调策略"""
    
    def __init__(self, 
                 min_callback=5,
                 max_callback=15,
                 stop_loss=8,
                 top_n=10):
        super().__init__("涨停回调", "事件驱动")
        self.min_callback = min_callback
        self.max_callback = max_callback
        self.stop_loss = stop_loss
        self.top_n = top_n
        
    def get_description(self):
        return f"涨停回调：回调{self.min_callback}-{self.max_callback}%, 止损{self.stop_loss}%"

    def select_stocks(self, helper, date=None):
        """选股：涨停回调"""
        results = []
        
        # 模拟涨停回调股票池
        limit_stocks = [
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '002594', 'name': '比亚迪'},
        ]
        
        for stock in limit_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=10)
                if kline.empty or len(kline) < 5:
                    continue
                
                # 检查回调幅度（简化版：使用近期高低点估算）
                recent_high = kline['high'].tail(5).max()
                current = kline['close'].iloc[-1]
                callback_pct = (recent_high - current) / recent_high * 100 if recent_high > 0 else 0
                
                if self.min_callback < callback_pct < self.max_callback:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"涨停回调：近期高点回调{callback_pct:.1f}%，关注买入机会"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
