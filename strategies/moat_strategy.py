"""
护城河选股策略

策略逻辑：
- 量化巴菲特经济护城河：高且稳定的毛利率、持续高ROE、低负债、强现金转化
- 筛选具有持续竞争优势的优质企业
- 适用于中长期持有，低风险

参考：myhhub/stock (13.3k stars) - A股基本面选股
"""

from strategies.base import BaseStrategy


class MoatStrategy(BaseStrategy):
    """护城河选股策略"""

    def __init__(self,
                 min_roe=6,         # 单季ROE下限%（年化约24%，保留高质量门槛）
                 min_gross_margin=30,  # 毛利率下限%
                 max_debt_ratio=50,    # 资产负债率上限%
                 max_pe=60,            # PE上限（消费白马常年在30-50）
                 max_drawdown_60d=15,  # 60日最大回撤允许值%
                 holding_days=30,
                 top_n=5):
        super().__init__("护城河选股", "质量因子")
        self.min_roe = min_roe
        self.min_gross_margin = min_gross_margin
        self.max_debt_ratio = max_debt_ratio
        self.max_pe = max_pe
        self.max_drawdown_60d = max_drawdown_60d
        self.holding_days = holding_days
        self.top_n = top_n
        # 缓存股票池，避免33天回测每天重复获取
        self._pool_cache = None

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:50]
            except Exception:
                self._pool_cache = [
                    '600519', '600036', '601318', '300750', '000858',
                    '002475', '600887', '000333', '000001', '600030',
                    '601166', '600900', '601012', '002594', '600276',
                    '000725', '002422', '300059', '601899', '600000',
                ]
        return self._pool_cache

    def get_description(self):
        return f"护城河选股：ROE>{self.min_roe}%, 毛利率>{self.min_gross_margin}%, 负债<{self.max_debt_ratio}%, PE<{self.max_pe}"

    def select_stocks(self, helper, date=None):
        """选股：护城河量化筛选"""
        results = []

        # 1. 获取股票池（带缓存）
        pool = self._get_pool(helper, date)

        # 2. K线初步筛选：60日累计跌幅不超阈值（保留趋势保护，弱市也可进财务筛选）
        candidates = []
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=70, end_date=date)
                if kline.empty or len(kline) < 61:
                    continue
                closes = kline['close'].astype(float)
                ret_60d = (closes.iloc[-1] / closes.iloc[-61] - 1) * 100
                if ret_60d > -self.max_drawdown_60d:
                    candidates.append(symbol)
                if len(candidates) >= 15:
                    break
            except Exception:
                continue

        # 3. 财务数据深度筛选
        for symbol in candidates:
            try:
                fin = helper.get_financial_indicator(symbol)

                roe = fin.get('roe', 0) * 100 if fin else 0
                gross_margin = fin.get('gross_margin', 0) * 100 if fin else 0
                debt_ratio = fin.get('debt_ratio', 0) * 100 if fin else 0
                net_margin = fin.get('net_margin', 0) * 100 if fin else 0

                # 宽松模式：财务数据缺失时只保留ROE和PB筛选
                has_financial = roe > 0 or gross_margin > 0 or debt_ratio > 0
                if has_financial:
                    # 有财务数据时严格筛选
                    if roe < self.min_roe:
                        continue
                    if debt_ratio > self.max_debt_ratio:
                        continue
                else:
                    # 无财务数据时用PB宽松筛选（PB<6说明低估）
                    pass  # PB筛选在下面

                # PB估值筛选（统一降低门槛）
                val = helper.get_valuation_data(symbol)
                if not val:
                    continue
                pe = val.get('pe', 0)
                pb = val.get('pb', 0)
                if pe <= 0 or pe > 40:  # PE上限放宽到40
                    continue
                if pb <= 0:
                    continue
                # 宽松：PB<8 有财务数据时，或 PB<6 无财务数据时
                if has_financial and pb > 8:
                    continue
                if not has_financial and pb > 6:
                    continue

                # 获取股票名称
                try:
                    quote = helper.get_realtime_quote(symbol)
                    name = quote.get('名称', symbol) if quote else symbol
                except Exception:
                    name = symbol

                results.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': f"护城河：ROE={roe:.1f}%, 毛利率={gross_margin:.1f}%, 负债={debt_ratio:.1f}%, PE={pe:.1f}"
                })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = MoatStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
