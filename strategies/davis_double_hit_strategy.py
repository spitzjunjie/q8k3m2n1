# -*- coding: utf-8 -*-
"""
戴维斯双击策略

策略逻辑：
- 业绩+估值双提升
- 低PE买入高PE卖出
- 净利润增速>20%
- 股价动量确认
- 中风险，中长期持有
- 适合成长股

参考：myhhub/stock - 戴维斯双击
"""

from strategies.base import BaseStrategy


class DavisDoubleHitStrategy(BaseStrategy):
    """戴维斯双击策略"""

    def __init__(self,
                 min_profit_growth=15,    # 最低净利润增速%（原20，当前市场达标股为0）
                 max_pe=35,              # 最高PE（原25，消费/科技白马常在30-40）
                 min_roe=8,              # 最低ROE%（原10，单季口径）
                 holding_days=30,        # 持有天数
                 top_n=5):
        super().__init__("戴维斯双击", "成长因子")
        self.min_profit_growth = min_profit_growth
        self.max_pe = max_pe
        self.min_roe = min_roe
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
        return (f"戴维斯双击：增速>{self.min_profit_growth}%, PE<{self.max_pe}, "
                f"ROE>{self.min_roe}%, 持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：戴维斯双击"""
        results = []

        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                # 获取财务数据
                growth = None
                fin = None
                val = None

                try:
                    growth = helper.get_growth_data(symbol)
                except Exception:
                    pass

                try:
                    fin = helper.get_financial_indicator(symbol)
                except Exception:
                    pass

                try:
                    val = helper.get_valuation_data(symbol)
                except Exception:
                    pass

                # 获取增速
                profit_growth = 0
                revenue_growth = 0
                if growth:
                    profit_growth = growth.get('profit_growth', 0) or 0
                    revenue_growth = growth.get('revenue_growth', 0) or 0

                # 宽松模式：增速缺失时用ROE
                if profit_growth == 0 and fin:
                    profit_growth = fin.get('roe', 0) or 0

                # 获取PE和ROE
                pe = val.get('pe_ttm', 100) if val else 100
                roe = fin.get('roe', 0) if fin else 0
                roe_pct = roe * 100  # helper 返回小数，策略阈值按百分数

                # 筛选条件：增速+低PE+高ROE
                if profit_growth >= self.min_profit_growth and pe <= self.max_pe and roe_pct >= self.min_roe:
                    # K线确认：趋势向上
                    kline = helper.get_history_kline(symbol, days=30, end_date=date)
                    if kline is None or kline.empty or len(kline) < 20:
                        continue

                    ma20 = kline['close'].iloc[-20:].mean()
                    current_price = kline['close'].iloc[-1]

                    if current_price > ma20 * 0.95:  # 趋势未破
                        results.append({
                            'symbol': symbol,
                            'name': symbol,
                            'reason': f"戴维斯双击：增速{profit_growth:.1f}%, PE={pe:.1f}, ROE={roe_pct:.1f}%"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 宽松备选
        if not results:
            for symbol in pool[:20]:
                try:
                    fin = helper.get_financial_indicator(symbol)
                    val = helper.get_valuation_data(symbol)
                    kline = helper.get_history_kline(symbol, days=30, end_date=date)

                    if fin is None or val is None or kline is None or kline.empty:
                        continue

                    roe = fin.get('roe', 0) or 0
                    roe_pct = roe * 100
                    pb = val.get('pb', 10) or 10

                    # 低PB+高ROE
                    if pb < 3 and roe_pct > 15:
                        results.append({
                            'symbol': symbol,
                            'name': symbol,
                            'reason': f"戴维斯双击备选：PB={pb:.1f}, ROE={roe_pct:.1f}%"
                        })

                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = DavisDoubleHitStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
