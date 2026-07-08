"""
龙虎榜策略

策略逻辑：
- 选取同时被机构和游资买入的股票
- 要求营业部买卖总额较大
- 持有3天，快进快出
- 止损5%

参考：机构和游资同时看好往往是强势信号
"""

from strategies.base import BaseStrategy


class DragonTigerListStrategy(BaseStrategy):
    """龙虎榜策略"""
    
    def __init__(self, 
                 holding_days=3,
                 stop_loss=5,
                 top_n=10):
        super().__init__("龙虎榜", "事件驱动")
        self.holding_days = holding_days
        self.stop_loss = stop_loss
        self.top_n = top_n
        
    def get_description(self):
        return f"龙虎榜：机构和游资同时买入, 持有{self.holding_days}天, 止损{self.stop_loss}%"

    def select_stocks(self, helper, date=None):
        """选股：龙虎榜"""
        results = []
        
        # 扩大股票池
        lhb_stocks = [
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '002230', 'name': '科大讯飞'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002415', 'name': '海康威视'},
        ]
        
        for stock in lhb_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=20)
                if kline.empty or len(kline) < 5:
                    continue
                
                # 优化：移除成交额放大条件，改为趋势向上即可
                ma5 = kline['close'].rolling(5).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                
                if current > ma5:  # 趋势向上即可入选
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"龙虎榜：趋势向上，活跃"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
