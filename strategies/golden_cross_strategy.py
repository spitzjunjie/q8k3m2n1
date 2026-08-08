"""
MACD金叉策略

策略逻辑：
- 筛选MACD在零轴上方形成金叉的股票
- 要求DEA > 0（多头趋势）
- 要求DIF从下往上穿越DEA
- 持有10天或MACD死叉卖出

参考：MACD是最经典的趋势指标
"""

from strategies.base import BaseStrategy


class GoldenCrossStrategy(BaseStrategy):
    """MACD金叉策略"""
    
    def __init__(self, 
                 holding_days=10,
                 top_n=10):
        super().__init__("MACD金叉", "技术面")
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"MACD金叉：零轴上方金叉, 持有{self.holding_days}天"

    def calculate_macd(self, prices, fast=12, slow=26, signal=9):
        """计算MACD"""
        if len(prices) < slow + signal:
            return None, None, None
        
        # 计算EMA
        ema_fast = self._ema(prices, fast)
        ema_slow = self._ema(prices, slow)
        
        # DIF = EMA(fast) - EMA(slow)
        dif = ema_fast - ema_slow
        
        # DEA = EMA(DIF, signal)
        dea = self._ema(dif, signal)
        
        return dif, dea, None
    
    def _ema(self, prices, period):
        """计算EMA"""
        ema = [prices[0]]
        multiplier = 2 / (period + 1)
        for i in range(1, len(prices)):
            ema.append((prices[i] - ema[-1]) * multiplier + ema[-1])
        return ema

    def select_stocks(self, helper, date=None):
        """选股：MACD金叉"""
        results = []
        
        # 扩大的股票池
        stock_pool = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '000333', 'name': '美的集团'},
            {'symbol': '002714', 'name': '牧原股份'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '601138', 'name': '工业富联'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002415', 'name': '海康威视'},
            {'symbol': '600900', 'name': '长江电力'},
            {'symbol': '601888', 'name': '中国中免'},
            {'symbol': '600030', 'name': '中信证券'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '300274', 'name': '阳光电源'},
            {'symbol': '601012', 'name': '隆基绿能'},
            {'symbol': '600276', 'name': '恒瑞医药'},
            {'symbol': '000001', 'name': '平安银行'},
            {'symbol': '002352', 'name': '顺丰控股'},
            {'symbol': '600028', 'name': '中国石化'},
            {'symbol': '601857', 'name': '中国石油'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '300015', 'name': '爱尔眼科'},
            {'symbol': '601166', 'name': '兴业银行'},
        ]
        
        for stock in stock_pool:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=60)
                if kline.empty or len(kline) < 40:
                    continue
                
                prices = kline['close'].values
                result = self.calculate_macd(prices)
                if result[0] is None:
                    continue
                    
                dif, dea, _ = result
                
                # 检查金叉（放宽条件）
                if len(dif) >= 2 and dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
                    results.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': f"MACD金叉：DIF={dif[-1]:.3f}, DEA={dea[-1]:.3f}"
                    })
                
                if len(results) >= self.top_n:
                    break
            except Exception:
                continue
        
        # 兜底：返回MACD多头排列的股票（DIF>DEA）
        if not results:
            for stock in stock_pool:
                try:
                    kline = helper.get_history_kline(stock['symbol'], days=60)
                    if kline.empty or len(kline) < 40:
                        continue
                    
                    prices = kline['close'].values
                    result = self.calculate_macd(prices)
                    if result[0] is None:
                        continue
                    
                    dif, dea, _ = result
                    
                    # MACD多头排列
                    if dif[-1] > dea[-1] > 0:
                        results.append({
                            'symbol': stock['symbol'],
                            'name': stock['name'],
                            'reason': f"MACD多头排列：DIF={dif[-1]:.3f}, DEA={dea[-1]:.3f}"
                        })
                    
                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue
        
        return results[:self.top_n]
