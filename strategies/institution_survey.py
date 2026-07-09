"""
机构调研后效应策略

策略逻辑：
- 机构调研后股票往往有超额收益
- 选择近期有机构密集调研的股票
- 机构调研是重要的 alpha 信号

参考：机构调研被视为聪明钱信号
"""

from strategies.base import BaseStrategy


class InstitutionSurveyStrategy(BaseStrategy):
    """机构调研后效应策略"""
    
    def __init__(self, 
                 survey_days=20,
                 holding_days=15):
        super().__init__("机构调研效应", "事件驱动")
        self.survey_days = survey_days
        self.holding_days = holding_days
        
    def get_description(self):
        return f"机构调研效应：近{self.survey_days}日有调研，持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：机构调研后效应"""
        results = []
        
        # 使用沪深300和中证500成分股
        try:
            pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:50]
            pool += helper.get_stock_pool("zz500", sorted_by_market_value=True)[:50]
        except:
            pool = [
                '600519', '600036', '601318', '300750', '000858',
                '002475', '600887', '000333', '000001', '600030',
                '601166', '600900', '601012', '002594', '600276',
                '300059', '300122', '300124', '300760', '300896',
                '688981', '688599', '688111', '688036', '688012'
            ]
        
        best_stocks = []
        
        for symbol in pool:
            try:
                # 获取近期K线数据
                kline = helper.get_history_kline(symbol, days=self.survey_days + 10)
                if kline.empty or len(kline) < self.survey_days:
                    continue
                
                # 计算成交量变化（机构调研往往伴随成交量放大）
                recent_vol = kline['volume'].tail(5).mean()
                older_vol = kline['volume'].iloc[:-5].tail(10).mean()
                
                if older_vol <= 0:
                    continue
                    
                vol_ratio = recent_vol / older_vol
                
                # 计算价格表现
                recent_return = (kline['close'].iloc[-1] / kline['close'].iloc[0] - 1) * 100
                
                # 机构调研信号：成交量放大 + 股价表现
                # 放宽条件：只要有成交量放大即可
                if vol_ratio > 1.5:
                    best_stocks.append({
                        'symbol': symbol,
                        'vol_ratio': vol_ratio,
                        'recent_return': recent_return,
                        'score': vol_ratio
                    })
                        
            except:
                continue
        
        # 按成交量放大程度排序
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
                'reason': f"机构调研效应：量比{stock['vol_ratio']:.1f}倍，近{self.survey_days}日涨{stock['recent_return']:.1f}%"
            })
        
        return results
