"""
ETF二八轮动策略

策略逻辑：
- 比较沪深300ETF和中创业板ETF的20日涨幅
- 哪个强持有哪个
- 每月第一个交易日调仓

适合：小资金（ETF免印花税）
"""

from strategies.base import BaseStrategy


class ETFRotationStrategy(BaseStrategy):
    """ETF二八轮动策略"""
    
    def __init__(self, lookback_days=20):
        super().__init__("ETF二八轮动", "轮动策略")
        self.lookback_days = lookback_days
        
    def get_description(self):
        return f"ETF二八轮动：比较沪深300和创业板，选择强势品种，{self.lookback_days}日调仓"

    def select_stocks(self, helper, date=None):
        """选股：选择强势ETF"""
        results = []
        
        # 模拟ETF池
        etf_pool = [
            {'symbol': '510300', 'name': '沪深300ETF'},
            {'symbol': '159915', 'name': '创业板ETF'},
            {'symbol': '588000', 'name': '科创50ETF'},
            {'symbol': '515980', 'name': '人工智能ETF'},
        ]
        
        best_etf = None
        best_return = -999
        
        for etf in etf_pool:
            try:
                kline = helper.get_history_kline(etf['symbol'], days=self.lookback_days + 10)
                if kline.empty or len(kline) < self.lookback_days:
                    continue
                    
                ret = (kline['close'].iloc[-1] / kline['close'].iloc[0] - 1) * 100
                if ret > best_return:
                    best_return = ret
                    best_etf = etf
            except:
                continue
        
        if best_etf:
            results.append({
                'symbol': best_etf['symbol'],
                'name': best_etf['name'],
                'reason': f"ETF二八轮动：{best_etf['name']}近{self.lookback_days}日涨幅{best_return:.2f}%，最强"
            })
        
        return results
