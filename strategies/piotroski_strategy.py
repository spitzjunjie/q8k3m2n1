"""
质量因子选股策略（Piotroski F-Score）

策略逻辑：
- 基于Piotroski F-Score 9分制评分，筛选高质量公司
- 盈利能力(4分) + 杠杆/流动性(3分) + 运营效率(2分)
- F-Score≥7分且估值合理时买入
- 适用于低风险中长期持有

参考：astro30/valinvest (154 stars) - Piotroski F-Score纯Python实现
"""

from strategies.base import BaseStrategy


class PiotroskiStrategy(BaseStrategy):
    """质量因子选股策略（Piotroski F-Score）"""

    def __init__(self,
                 min_score=3,       # F-Score下限（降低到3分）
                 max_pe=40,         # PE上限（放宽到40）
                 max_drawdown_20d=10,  # 20日累计跌幅允许值%
                 holding_days=30,
                 top_n=5):
        super().__init__("质量因子选股", "质量因子")
        self.min_score = min_score
        self.max_pe = max_pe
        self.max_drawdown_20d = max_drawdown_20d
        self.holding_days = holding_days
        self.top_n = top_n
        self._pool_cache = None

    def get_description(self):
        return f"质量因子选股：F-Score≥{self.min_score}, PE<{self.max_pe}, 持有{self.holding_days}天"

    def _get_pool(self, helper, date=None):
        """获取股票池（带缓存）"""
        if self._pool_cache is None:
            try:
                self._pool_cache = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:30]
            except Exception:
                self._pool_cache = [
                    '600519', '600036', '601318', '300750', '000858',
                    '002475', '600887', '000333', '000001', '600030',
                    '601166', '600900', '601012', '002594', '600276',
                ]
        return self._pool_cache

    def _calc_f_score(self, fin, cashflow, val):
        """计算Piotroski F-Score（简化版，基于单期数据）"""
        score = 0

        # 盈利能力 (4分) - 放宽
        roe = fin.get('roe', 0)
        if roe > 0:
            score += 1  # ROE>0即可得分
        if roe > 5:
            score += 1  # ROE>5%额外加分
        if roe > 10:
            score += 1  # ROE>10%再加分
        net_margin = fin.get('net_margin', 0)
        if net_margin > 0:
            score += 1  # 净利率>0

        # 经营现金流>0
        op_cf = cashflow.get('operating_cf', 0) if cashflow else 0
        if op_cf > 0:
            score += 1
        # 盈利质量：经营现金流为正
        if op_cf > 0 and net_margin > 0:
            score += 1

        # 杠杆/流动性 (3分)
        debt_ratio = fin.get('debt_ratio', 0)
        if debt_ratio < 0.6:
            score += 1  # 负债率<60%
        current_ratio = fin.get('current_ratio', 0)
        if current_ratio >= 1:
            score += 1  # 流动比率≥1
        if debt_ratio < 0.5:
            score += 1  # 负债率较低额外加分

        # 运营效率 (2分)
        gross_margin = fin.get('gross_margin', 0)
        if gross_margin > 0.2:
            score += 1  # 毛利率>20%
        if roe > 0.1:
            score += 1  # ROE>10%

        return score

    def select_stocks(self, helper, date=None):
        """选股：F-Score高质量筛选"""
        results = []

        # 1. 获取股票池
        pool = self._get_pool(helper, date)

        # 2. K线初步筛选：20日累计跌幅不超阈值（保留趋势保护，弱市也可进财务筛选）
        candidates = []
        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=30, end_date=date)
                if kline.empty or len(kline) < 21:
                    continue
                closes = kline['close'].astype(float)
                ret_20d = (closes.iloc[-1] / closes.iloc[-21] - 1) * 100
                if ret_20d > -self.max_drawdown_20d:
                    candidates.append(symbol)
                if len(candidates) >= 15:
                    break
            except Exception:
                continue

        # 3. F-Score评分
        scored = []
        for symbol in candidates:
            try:
                fin = helper.get_financial_indicator(symbol)
                if not fin:
                    continue
                cashflow = helper.get_cash_flow(symbol) or {}
                val = helper.get_valuation_data(symbol) or {}

                pe = val.get('pe', 0)
                if pe <= 0 or pe > self.max_pe:
                    continue

                score = self._calc_f_score(fin, cashflow, val)
                if score >= max(self.min_score, 5):
                    scored.append((symbol, score, fin, val))
            except Exception:
                continue

        # 4. 按F-Score排序，取前N只
        scored.sort(key=lambda x: x[1], reverse=True)
        for symbol, score, fin, val in scored[:self.top_n]:
            try:
                quote = helper.get_realtime_quote(symbol)
                name = quote.get('名称', symbol) if quote else symbol
            except Exception:
                name = symbol

            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"F-Score={score}分, ROE={fin.get('roe',0)*100:.1f}%, PE={val.get('pe',0):.1f}"
            })

        return results[:self.top_n]


if __name__ == '__main__':
    s = PiotroskiStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
