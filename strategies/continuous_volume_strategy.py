"""
量价齐升策略

策略逻辑：
- 选取成交量持续放大且价格上涨的股票
- 要求量比 > 2
- 涨幅在5-15%之间（不是涨停）
- 持有5天

参考：量价配合是健康上涨的标志
"""

from strategies.base import BaseStrategy


class ContinuousVolumeStrategy(BaseStrategy):
    """量价齐升策略"""
    
    def __init__(self, 
                 vol_ratio=2,
                 min_return=5,
                 max_return=15,
                 holding_days=5,
                 top_n=10):
        super().__init__("量价齐升", "技术面")
        self.vol_ratio = vol_ratio
        self.min_return = min_return
        self.max_return = max_return
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"量价齐升：量比>{self.vol_ratio}, 涨幅{self.min_return}-{self.max_return}%, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：量价齐升"""
        results = []
        
        # 模拟热门股票池
        breakout_stocks = [
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600519', 'name': '贵州茅台'},
        ]
        
        for stock in breakout_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=30)
                if kline.empty or len(kline) < 10:
                    continue
                
                # 计算量比
                vol_ma = kline['volume'].tail(20).mean()
                current_vol = kline['volume'].iloc[-1]
                vol_ratio = current_vol / vol_ma if vol_ma > 0 else 0
                
                # 计算涨幅
                ret = (kline['close'].iloc[-1] / kline['close'].iloc[-2] - 1) * 100
                
                # 条件：放量 + 涨幅适中
                if vol_ratio > self.vol_ratio and self.min_return < ret < self.max_return:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"量价齐升：量比{round(vol_ratio, 1)}倍, 涨幅{ret:.1f}%"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
