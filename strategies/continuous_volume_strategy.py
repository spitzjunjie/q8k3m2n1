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
        self._pool_cache = None
        # 兜底池：helper 不可用时的降级方案，不再作为唯一股票池
        self._fallback_pool = [
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600519', 'name': '贵州茅台'},
        ]
        
    def get_description(self):
        return f"量价齐升：量比>{self.vol_ratio}, 涨幅{self.min_return}-{self.max_return}%, 持有{self.holding_days}天"

    def _get_pool(self, helper, date=None):
        """获取股票池：优先沪深300前50（真实数据），失败时退回硬编码兜底池"""
        if self._pool_cache is not None:
            return self._pool_cache
        try:
            stocks = helper.get_stock_pool("hs300", sorted_by_market_value=True)
            if stocks:
                self._pool_cache = [{'symbol': s, 'name': s} for s in stocks[:50]]
                return self._pool_cache
        except Exception:
            pass
        self._pool_cache = list(self._fallback_pool)
        return self._pool_cache

    def select_stocks(self, helper, date=None):
        """选股：量价齐升"""
        results = []

        for stock in self._get_pool(helper, date):
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
                    name = stock['name']
                    try:
                        quote = helper.get_realtime_quote(stock['symbol'])
                        if quote and quote.get('名称'):
                            name = quote.get('名称')
                    except Exception:
                        pass
                    results.append({
                        'symbol': stock['symbol'],
                        'name': name,
                        'reason': f"量价齐升：量比{round(vol_ratio, 1)}倍, 涨幅{ret:.1f}%"
                    })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
