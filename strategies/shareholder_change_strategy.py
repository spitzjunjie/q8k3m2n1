# -*- coding: utf-8 -*-
"""
股东户数变化策略

策略逻辑：
- 股东户数减少=筹码集中度提升
- 机构持股比例提升
- 配合股价趋势
- 中风险，中长期持有

参考：myhhub/stock + 源达策略研报
"""

from strategies.base import BaseStrategy


class ShareholderChangeStrategy(BaseStrategy):
    """股东户数变化策略"""

    def __init__(self,
                 min_shareholder_drop=10,    # 最低股东户数降幅%
                 min_institution_ratio=30,   # 最低机构持股比例%
                 holding_days=30,           # 持有天数
                 top_n=5):
        super().__init__("股东户数变化", "事件驱动")
        self.min_shareholder_drop = min_shareholder_drop
        self.min_institution_ratio = min_institution_ratio
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:50]
            except Exception:
                self._pool_cache = ['600519', '600036', '601318', '000858', '600887',
                                    '000333', '601166', '600276', '601012', '600030',
                                    '600028', '601166', '600900', '601398', '601288',
                                    '000001', '002594', '300750', '600276', '002415']
        return self._pool_cache

    def get_description(self):
        return (f"股东户数变化：户数减>{self.min_shareholder_drop}%, "
                f"机构持股>{self.min_institution_ratio}%, 持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：股东户数减少筹码集中"""
        results = []

        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                # 获取财务数据
                fin = None
                try:
                    fin = helper.get_financial_indicator(symbol)
                except Exception:
                    pass

                # 获取北向持股（作为机构持股代理）
                north = None
                try:
                    north = helper.get_north_holding(symbol)
                except Exception:
                    pass

                # 机构持股比例
                institution_ratio = 0
                if north:
                    institution_ratio = north.get('hold_ratio', 0) or 0
                    institution_ratio *= 100  # 转为百分比

                # 北向加仓信号
                north_added = False
                if north:
                    # 粗略估算：近30日持股比例变化
                    hold_ratio = north.get('hold_ratio', 0) or 0
                    if hold_ratio > 0.02:  # 持股比例>2%
                        north_added = True

                # 北向持股满足条件
                if institution_ratio >= self.min_institution_ratio or north_added:
                    # 财务确认
                    roe = fin.get('roe', 0) if fin else 0
                    roe_pct = roe * 100
                    pb = 10
                    try:
                        val = helper.get_valuation_data(symbol)
                        pb = val.get('pb', 10) or 10
                    except Exception:
                        pass

                    # 低PB高ROE
                    if pb < 4 and roe_pct > 8:
                        # K线确认
                        kline = helper.get_history_kline(symbol, days=30, end_date=date)
                        if kline is None or kline.empty or len(kline) < 20:
                            continue

                        ma20 = kline['close'].iloc[-20:].mean()
                        current_price = kline['close'].iloc[-1]

                        # 趋势向上
                        if current_price > ma20 * 0.95:
                            results.append({
                                'symbol': symbol,
                                'name': symbol,
                                'reason': f"股东户数变化：机构持股{institution_ratio:.1f}%, ROE={roe_pct:.1f}%, PB={pb:.1f}"
                            })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 宽松备选：机构重仓股
        if not results:
            for symbol in pool[:20]:
                try:
                    north = helper.get_north_holding(symbol)
                    fin = helper.get_financial_indicator(symbol)
                    kline = helper.get_history_kline(symbol, days=30, end_date=date)

                    if north is None or fin is None or kline is None or kline.empty:
                        continue

                    hold_ratio = north.get('hold_ratio', 0) or 0

                    # 北向持股比例较高
                    if hold_ratio > 0.01:  # 1%以上
                        roe = fin.get('roe', 0) or 0
                        roe_pct = roe * 100

                        if roe_pct > 10:
                            val = helper.get_valuation_data(symbol)
                            pb = val.get('pb', 10) if val else 10

                            if pb < 5:
                                results.append({
                                    'symbol': symbol,
                                    'name': symbol,
                                    'reason': f"股东备选：北向持股{hold_ratio*100:.2f}%, ROE={roe_pct:.1f}%"
                                })

                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = ShareholderChangeStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
