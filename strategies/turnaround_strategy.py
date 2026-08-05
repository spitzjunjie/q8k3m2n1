# -*- coding: utf-8 -*-
"""
困境反转策略

策略逻辑：
- 业绩底部反转
- 9类指标恢复率体系
- 毛利率恢复+净利率恢复+营收增速恢复
- 低估值底部介入
- 中风险，中长期持有

参考：myhhub/stock + 广发证券困境反转研报
"""

from strategies.base import BaseStrategy


class TurnaroundStrategy(BaseStrategy):
    """困境反转策略"""

    def __init__(self,
                 min_recovery_score=3,     # 最低恢复评分（9分制）
                 max_pb=2.5,             # 最高PB
                 min_roe=5,              # 最低ROE%
                 holding_days=30,         # 持有天数
                 top_n=5):
        super().__init__("困境反转", "价值因子")
        self.min_recovery_score = min_recovery_score
        self.max_pb = max_pb
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
        return (f"困境反转：恢复评分≥{self.min_recovery_score}/9, PB<{self.max_pb}, "
                f"ROE>{self.min_roe}%, 持有{self.holding_days}天")

    def select_stocks(self, helper, date=None):
        """选股：困境反转"""
        results = []

        pool = self._get_pool(helper, date)

        for symbol in pool:
            try:
                # 获取财务数据
                fin = None
                val = None
                growth = None

                try:
                    fin = helper.get_financial_indicator(symbol)
                except Exception:
                    pass

                try:
                    val = helper.get_valuation_data(symbol)
                except Exception:
                    pass

                try:
                    growth = helper.get_growth_data(symbol)
                except Exception:
                    pass

                # 计算恢复评分（9分制）
                recovery_score = 0

                # 1. 毛利率恢复（加分）
                gross_margin_pct = (fin.get('gross_margin', 0) if fin else 0) * 100
                if gross_margin_pct > 20:
                    recovery_score += 1
                elif gross_margin_pct > 10:
                    recovery_score += 0.5

                # 2. 净利率恢复（加分）
                net_margin_pct = (fin.get('net_margin', 0) if fin else 0) * 100
                if net_margin_pct > 10:
                    recovery_score += 1
                elif net_margin_pct > 5:
                    recovery_score += 0.5

                # 3. ROE恢复（加分）
                roe_pct = (fin.get('roe', 0) if fin else 0) * 100
                if roe_pct > 15:
                    recovery_score += 1
                elif roe_pct > self.min_roe:
                    recovery_score += 0.5

                # 4. 营收增速（加分）
                revenue_growth = 0
                if growth:
                    revenue_growth = growth.get('revenue_growth', 0) or 0
                if revenue_growth > 20:
                    recovery_score += 1
                elif revenue_growth > 10:
                    recovery_score += 0.5

                # 5. 净利润增速（加分）
                profit_growth = 0
                if growth:
                    profit_growth = growth.get('profit_growth', 0) or 0
                if profit_growth > 20:
                    recovery_score += 1
                elif profit_growth > 10:
                    recovery_score += 0.5

                # 6. 现金流改善（加分）
                cf = None
                try:
                    cf = helper.get_cash_flow(symbol)
                except Exception:
                    pass
                if cf:
                    ocf = cf.get('operating_cf', 0) or 0
                    if ocf > 0:
                        recovery_score += 1

                # 7. 负债率下降（加分）
                debt_ratio_pct = (fin.get('debt_ratio', 1.0) if fin else 1.0) * 100
                if debt_ratio_pct < 50:
                    recovery_score += 1
                elif debt_ratio_pct < 70:
                    recovery_score += 0.5

                # 8. 低PB（加分）
                pb = val.get('pb', 10) if val else 10
                if pb < 1.5:
                    recovery_score += 1
                elif pb < self.max_pb:
                    recovery_score += 0.5

                # 9. 估值修复空间（加分）
                pe = val.get('pe_ttm', 100) if val else 100
                if 0 < pe < 20:
                    recovery_score += 1
                elif pe < 30:
                    recovery_score += 0.5

                # 筛选条件
                if recovery_score >= self.min_recovery_score and pb <= self.max_pb and roe_pct >= self.min_roe:
                    # K线确认：超跌
                    kline = helper.get_history_kline(symbol, days=60, end_date=date)
                    if kline is None or kline.empty or len(kline) < 30:
                        continue

                    ma20 = kline['close'].iloc[-20:].mean()
                    ma60 = kline['close'].iloc[-60:].mean() if len(kline) >= 60 else kline['close'].mean()
                    current_price = kline['close'].iloc[-1]

                    # 底部特征：价格在低位
                    if current_price < ma60 * 1.1:
                        results.append({
                            'symbol': symbol,
                            'name': symbol,
                            'reason': f"困境反转：恢复评分{recovery_score}/9, PB={pb:.1f}, ROE={roe_pct:.1f}%"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 宽松备选：低PB超跌股
        if not results:
            for symbol in pool[:20]:
                try:
                    val = helper.get_valuation_data(symbol)
                    fin = helper.get_financial_indicator(symbol)
                    kline = helper.get_history_kline(symbol, days=60, end_date=date)

                    if val is None or fin is None or kline is None or kline.empty:
                        continue

                    pb = val.get('pb', 10) or 10
                    roe = fin.get('roe', 0) or 0
                    roe_pct = roe * 100

                    # 低PB超跌
                    if pb < 2 and roe_pct > 5:
                        ma60 = kline['close'].iloc[-60:].mean() if len(kline) >= 60 else kline['close'].mean()
                        current_price = kline['close'].iloc[-1]

                        if current_price < ma60 * 0.9:
                            results.append({
                                'symbol': symbol,
                                'name': symbol,
                                'reason': f"困境反转备选：PB={pb:.1f}, 超跌{((ma60-current_price)/ma60)*100:.1f}%"
                            })

                    if len(results) >= self.top_n:
                        break
                except Exception:
                    continue

        return results[:self.top_n]


if __name__ == '__main__':
    s = TurnaroundStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
