# -*- coding: utf-8 -*-
"""
可转债下修博弈策略

策略逻辑：
- 正股跌破回售触发价（通常为转股价的70%）
- 公司有下修转股价的意愿和空间
- 下修博弈：买入正股，等待下修后转债上涨
- 中风险，适合震荡市或熊市
- 适配3只持仓限制

参考：jackluson/convertible-bond-crawler - 可转债下修博弈
"""

from strategies.base import BaseStrategy


class ConvertibleBondDownwardStrategy(BaseStrategy):
    """可转债下修博弈策略"""

    def __init__(self,
                 min_downward_space=10,    # 最低下修空间%（转股价距离正股价）
                 max_price=115,           # 最高转债价格
                 holding_days=30,          # 持有天数
                 top_n=3):
        super().__init__("可转债下修博弈", "事件驱动")
        self.min_downward_space = min_downward_space
        self.max_price = max_price
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:30]
            except Exception:
                self._pool_cache = ['600519', '600036', '601318', '000858', '600887',
                                    '000333', '601166', '600276', '601012', '600030',
                                    '600028', '601166', '600900', '601398', '601288']
        return self._pool_cache

    def get_description(self):
        return (f"可转债下修博弈：下修空间>{self.min_downward_space}%, "
                f"转债价格<{self.max_price}元, 持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：可转债下修博弈"""
        results = []

        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=60, end_date=date)
                if kline is None or kline.empty or len(kline) < 30:
                    continue

                current_price = kline['close'].iloc[-1]

                # 估算转股价（取历史高点作为参考）
                high_60d = kline['high'].iloc[-60:].max() if len(kline) >= 60 else kline['high'].max()

                # 下修空间估算
                if high_60d > 0:
                    downward_space = (high_60d - current_price) / high_60d * 100
                else:
                    downward_space = 0

                # 当前跌幅
                ma20 = kline['close'].iloc[-20:].mean() if len(kline) >= 20 else kline['close'].mean()
                ma60 = kline['close'].iloc[-60:].mean() if len(kline) >= 60 else kline['close'].mean()

                # 下修博弈特征：股价超跌，在低位
                if downward_space >= self.min_downward_space and current_price < ma20:
                    # 财务数据确认
                    fin = helper.get_financial_indicator(symbol)
                    if fin:
                        roe = fin.get('roe', 0)
                        roe_pct = roe * 100
                        # ROE>5%的公司更可能下修
                        if roe_pct > 5:
                            results.append({
                                'symbol': symbol,
                                'name': symbol,
                                'reason': f"可转债下修博弈：距高点{downward_space:.1f}%, ROE={roe_pct:.1f}%, 超跌"
                            })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 备选：超跌大盘股
        if not results:
            for symbol in pool[:15]:
                try:
                    kline = helper.get_history_kline(symbol, days=60, end_date=date)
                    if kline is None or kline.empty or len(kline) < 30:
                        continue

                    ma20 = kline['close'].iloc[-20:].mean()
                    current_price = kline['close'].iloc[-1]

                    # 超跌：价格低于20日均线10%以上
                    if current_price < ma20 * 0.9:
                        # 估值低位
                        val = helper.get_valuation_data(symbol)
                        pb = val.get('pb', 5) if val else 5

                        if pb < 2:  # 低PB
                            results.append({
                                'symbol': symbol,
                                'name': symbol,
                                'reason': f"下修备选：超跌{((ma20-current_price)/ma20)*100:.1f}%, PB={pb:.1f}"
                            })

                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = ConvertibleBondDownwardStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
