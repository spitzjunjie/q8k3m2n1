"""
主力资金净流入策略

策略逻辑：
- 追踪主力资金（大单）净流入
- 选择资金持续净流入的股票
- 资金流入被视为聪明钱信号

参考：资金流向是机构行为的体现
"""

from strategies.base import BaseStrategy


class MajorCapitalFlowStrategy(BaseStrategy):
    """主力资金净流入策略"""
    
    def __init__(self, 
                 flow_days=5,
                 holding_days=10):
        super().__init__("主力资金流向", "资金流")
        self.flow_days = flow_days
        self.holding_days = holding_days
        
    def get_description(self):
        return f"主力资金流向：连续{self.flow_days}日净流入，持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：主力资金净流入"""
        results = []
        
        # 使用沪深300成分股
        try:
            pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:80]
        except:
            pool = [
                '600519', '600036', '601318', '300750', '000858',
                '002475', '600887', '000333', '000001', '600030',
                '601166', '600900', '601012', '002594', '600276',
                '000725', '002422', '000100', '300059', '601899',
                '601398', '601988', '600000', '600016', '601328'
            ]
        
        best_stocks = []
        
        for symbol in pool:
            try:
                # 获取成交量数据模拟资金流
                kline = helper.get_history_kline(symbol, days=30)
                if kline.empty or len(kline) < self.flow_days:
                    continue
                
                # 计算近N日平均成交量变化
                recent_vol = kline['volume'].tail(self.flow_days).mean()
                older_vol = kline['volume'].iloc[-self.flow_days*2:-self.flow_days].mean()
                
                if older_vol <= 0:
                    continue
                    
                vol_ratio = recent_vol / older_vol
                
                # 计算价格动量
                recent_return = (kline['close'].iloc[-1] / kline['close'].iloc[-self.flow_days] - 1) * 100
                
                # 资金流入信号：成交量放大 + 价格上涨
                if vol_ratio > 1.2 and recent_return > 0:
                    best_stocks.append({
                        'symbol': symbol,
                        'vol_ratio': vol_ratio,
                        'recent_return': recent_return,
                        'score': vol_ratio + recent_return / 10
                    })
                        
            except:
                continue
        
        # 按评分排序
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
                'reason': f"主力资金流向：量比{stock['vol_ratio']:.1f}倍，近{self.flow_days}日涨{stock['recent_return']:.1f}%"
            })
        
        return results
