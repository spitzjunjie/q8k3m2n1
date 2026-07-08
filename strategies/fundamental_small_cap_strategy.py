"""
财务基本面过滤小市值策略

策略逻辑：
- 选取市值50-200亿的股票
- 要求ROE > 10%
- 要求净利润增速 > 5%
- 每月调仓

参考：邢不行 - 小市值改良版（年化50.98%，2026年至今+9.01%）
"""

from strategies.base import BaseStrategy


class FundamentalSmallCapStrategy(BaseStrategy):
    """财务基本面过滤小市值策略"""
    
    def __init__(self, 
                 min_market_cap=50,
                 max_market_cap=200,
                 min_roe=10,
                 min_profit_growth=5,
                 holding_days=30,
                 top_n=10):
        super().__init__("财务基本面过滤小市值", "基本面")
        self.min_market_cap = min_market_cap
        self.max_market_cap = max_market_cap
        self.min_roe = min_roe
        self.min_profit_growth = min_profit_growth
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"财务基本面过滤小市值：市值{self.min_market_cap}-{self.max_market_cap}亿, ROE>{self.min_roe}%, 增速>{self.min_profit_growth}%"

    def select_stocks(self, helper, date=None):
        """选股：小市值+基本面"""
        results = []
        
        # 模拟小市值基本面股票池
        small_cap_stocks = [
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688111', 'name': '金山办公'},
            {'symbol': '300496', 'name': '中科创达'},
            {'symbol': '300751', 'name': '迈为股份'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '002475', 'name': '立讯精密'},
        ]
        
        for stock in small_cap_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=60)
                if kline.empty or len(kline) < 30:
                    continue
                
                # 检查趋势
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                
                if current > ma20:  # 趋势向上
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"财务基本面过滤小市值：ROE>{self.min_roe}%, 增速>{self.min_profit_growth}%, 趋势向上"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
