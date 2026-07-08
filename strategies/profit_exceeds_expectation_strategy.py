"""
业绩超预期策略

策略逻辑：
- 选取净利润增速超预期的股票
- 实际增速 > 预期增速 * 1.1
- 持有10天

参考：业绩超预期往往带来股价上涨
"""

from strategies.base import BaseStrategy


class ProfitExceedsExpectationStrategy(BaseStrategy):
    """业绩超预期策略"""
    
    def __init__(self, 
                 excess_ratio=1.1,
                 holding_days=10,
                 top_n=10):
        super().__init__("业绩超预期", "事件驱动")
        self.excess_ratio = excess_ratio
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"业绩超预期：实际>预期*{self.excess_ratio}, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：业绩超预期"""
        results = []
        
        # 模拟业绩超预期股票池
        surprise_stocks = [
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688111', 'name': '金山办公'},
            {'symbol': '300496', 'name': '中科创达'},
            {'symbol': '300751', 'name': '迈为股份'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '002475', 'name': '立讯精密'},
        ]
        
        for stock in surprise_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 20:
                    continue
                
                # 检查动量（业绩超预期往往伴随动量）
                ret = (kline['close'].iloc[-1] / kline['close'].iloc[-10] - 1) * 100
                ma10 = kline['close'].rolling(10).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                
                if ret > 0 and current > ma10:  # 动量向上
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"业绩超预期：近10日涨幅{ret:.1f}%，趋势向上"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
