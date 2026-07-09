"""
财报季业绩惊喜策略

策略逻辑：
- 业绩预告/公告后股价往往有反应
- 选择业绩改善的股票
- 财报季是A股重要的阿尔法来源

参考：业绩超预期是最强的alpha信号之一
"""

from strategies.base import BaseStrategy


class EarningsSurpriseV2Strategy(BaseStrategy):
    """财报季业绩惊喜策略"""
    
    def __init__(self, 
                 holding_days=15):
        super().__init__("财报季惊喜", "事件驱动")
        self.holding_days = holding_days
        
    def get_description(self):
        return f"财报季惊喜：业绩改善信号，持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：财报季业绩惊喜"""
        results = []
        
        # 使用沪深300成分股
        try:
            pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:60]
        except:
            pool = [
                '600519', '600036', '601318', '300750', '000858',
                '002475', '600887', '000333', '000001', '600030',
                '601166', '600900', '601012', '002594', '600276',
                '300059', '300122', '300124', '300760', '300896'
            ]
        
        best_stocks = []
        
        for symbol in pool:
            try:
                # 获取K线数据
                kline = helper.get_history_kline(symbol, days=40)
                if kline.empty or len(kline) < 30:
                    continue
                
                # 计算营收增长趋势
                recent_return = (kline['close'].iloc[-1] / kline['close'].iloc[-20] - 1) * 100
                older_return = (kline['close'].iloc[-20] / kline['close'].iloc[-40] - 1) * 100
                
                # 计算RSI
                delta = kline['close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1] if not rsi.empty else 50
                
                # 计算成交量变化
                vol_ratio = kline['volume'].tail(10).mean() / kline['volume'].iloc[-20:-10].mean()
                
                # 财报季惊喜信号：价格上涨加速 + RSI适中 + 成交量放大
                if recent_return > older_return and 30 < current_rsi < 65 and vol_ratio > 1.0:
                    acceleration = recent_return - older_return
                    best_stocks.append({
                        'symbol': symbol,
                        'recent_return': recent_return,
                        'acceleration': acceleration,
                        'rsi': current_rsi,
                        'score': acceleration + vol_ratio
                    })
                        
            except:
                continue
        
        # 按加速度排序
        best_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        for stock in best_stocks[:5]:
            try:
                name = helper.get_realtime_quote(stock['symbol'])
                name = name.get('名称', stock['symbol']) if name else stock['symbol']
            except:
                name = stock['symbol']
            
            results.append({
                'symbol': stock['symbol'],
                'name': name,
                'reason': f"财报季惊喜：近20日涨{stock['recent_return']:.1f}%，加速度{stock['acceleration']:.1f}%"
            })
        
        return results
