# -*- coding: utf-8 -*-
"""
限售解禁策略

策略逻辑：
- 解禁前逆向博弈"利空出尽"
- 解禁前30-60日超跌股票可能有反弹机会
- 配合基本面：低估值+优质公司
- 中风险，适合事件驱动
- 适配3只持仓限制

参考：NengjiangLunpi/astockevent-mcp - 限售解禁事件
"""

from strategies.base import BaseStrategy


class LockupExpiryArbitrageStrategy(BaseStrategy):
    """限售解禁策略"""

    def __init__(self,
                 before_days=45,          # 解禁前天数
                 min_drop_pct=15,         # 最低跌幅%
                 max_drop_pct=40,         # 最高跌幅%
                 holding_days=20,         # 持有天数
                 top_n=3):
        super().__init__("限售解禁博弈", "事件驱动")
        self.before_days = before_days
        self.min_drop_pct = min_drop_pct
        self.max_drop_pct = max_drop_pct
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
        return (f"限售解禁博弈：解禁前{self.before_days}日, 跌幅{self.min_drop_pct}-{self.max_drop_pct}%, "
                f"持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：限售解禁逆向博弈"""
        results = []

        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=90, end_date=date)
                if kline is None or kline.empty or len(kline) < 60:
                    continue

                # 计算解禁前窗口期的跌幅
                lookback = min(self.before_days * 2, len(kline) - 10)
                high_price = kline['close'].iloc[-lookback:-self.before_days].max()
                current_price = kline['close'].iloc[-1]

                drop_pct = (high_price - current_price) / high_price * 100

                # 筛选跌幅区间
                if self.min_drop_pct <= drop_pct <= self.max_drop_pct:
                    # 估值确认
                    val = helper.get_valuation_data(symbol)
                    if val:
                        pb = val.get('pb', 5)
                        pe = val.get('pe_ttm', 50)

                        # 低估值
                        if pb < 3 and pe < 25:
                            # 财务确认
                            fin = helper.get_financial_indicator(symbol)
                            roe = fin.get('roe', 0) if fin else 0
                            roe_pct = roe * 100

                            if roe_pct > 8:  # 优质公司
                                results.append({
                                    'symbol': symbol,
                                    'name': symbol,
                                    'reason': f"限售解禁博弈：区间跌幅{drop_pct:.1f}%, PB={pb:.1f}, ROE={roe_pct:.1f}%"
                                })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 备选：超跌优质股
        if not results:
            for symbol in pool[:15]:
                try:
                    kline = helper.get_history_kline(symbol, days=60, end_date=date)
                    if kline is None or kline.empty or len(kline) < 30:
                        continue

                    ma20 = kline['close'].iloc[-20:].mean()
                    ma60 = kline['close'].iloc[-60:].mean() if len(kline) >= 60 else ma20
                    current_price = kline['close'].iloc[-1]

                    # 超跌
                    drop_from_ma20 = (ma20 - current_price) / ma20 * 100
                    drop_from_ma60 = (ma60 - current_price) / ma60 * 100 if ma60 != ma20 else drop_from_ma20

                    if drop_from_ma20 > 15 and drop_from_ma60 > 20:
                        val = helper.get_valuation_data(symbol)
                        pb = val.get('pb', 5) if val else 5

                        if pb < 2.5:
                            results.append({
                                'symbol': symbol,
                                'name': symbol,
                                'reason': f"解禁备选：超跌{drop_from_ma20:.1f}%, PB={pb:.1f}"
                            })

                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = LockupExpiryArbitrageStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
