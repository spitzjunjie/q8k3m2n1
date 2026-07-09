"""
北向资金择时策略

策略逻辑：
- 北向资金被视为聪明钱
- 追踪北向资金持仓变化率
- 持仓增加时买入，减少时卖出

参考：北向资金是A股重要的边际力量
"""

from strategies.base import BaseStrategy


class NorthMoneyTimingStrategy(BaseStrategy):
    """北向资金择时策略"""
    
    def __init__(self, 
                 change_days=10,
                 holding_days=10):
        super().__init__("北向资金择时", "资金流")
        self.change_days = change_days
        self.holding_days = holding_days
        
    def get_description(self):
        return f"北向资金择时：近{self.change_days}日资金变化，持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：北向资金持仓变化"""
        results = []
        
        # 北向资金重仓股
        north_stocks = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600887', 'name': '伊利股份'},
            {'symbol': '000333', 'name': '美的集团'},
            {'symbol': '600030', 'name': '中信证券'},
            {'symbol': '600276', 'name': '恒瑞医药'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '601012', 'name': '隆基绿能'},
        ]
        
        best_stocks = []
        
        for stock in north_stocks:
            try:
                symbol = stock['symbol']
                # 获取近期K线数据
                kline = helper.get_history_kline(symbol, days=self.change_days + 10)
                if kline.empty or len(kline) < self.change_days:
                    continue
                
                # 计算成交量变化趋势
                recent_vol = kline['volume'].tail(self.change_days).mean()
                older_vol = kline['volume'].iloc[-self.change_days*2:-self.change_days].mean()
                
                if older_vol <= 0:
                    continue
                    
                vol_ratio = recent_vol / older_vol
                
                # 计算价格动量
                recent_return = (kline['close'].iloc[-1] / kline['close'].iloc[-self.change_days] - 1) * 100
                
                # 计算RSI
                delta = kline['close'].diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1] if not rsi.empty else 50
                
                # 北向资金择时信号：成交量放大 + 价格上涨 + RSI适中
                if vol_ratio > 1.1 and recent_return > 0 and 30 < current_rsi < 70:
                    best_stocks.append({
                        'symbol': symbol,
                        'name': stock['name'],
                        'vol_ratio': vol_ratio,
                        'recent_return': recent_return,
                        'rsi': current_rsi,
                        'score': vol_ratio * 2 + recent_return / 5
                    })
                        
            except:
                continue
        
        # 按评分排序
        best_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        for stock in best_stocks[:5]:
            results.append({
                'symbol': stock['symbol'],
                'name': stock['name'],
                'reason': f"北向资金择时：量比{stock['vol_ratio']:.1f}倍，RSI={stock['rsi']:.0f}，近{self.change_days}日涨{stock['recent_return']:.1f}%"
            })
        
        return results
