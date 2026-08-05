"""
周期股择时策略

策略逻辑：
- 周期股PB分位反向操作：低PB买入，高PB卖出
- 用历史价格分位模拟估值分位（价格低位≈估值低位）
- PB<历史20%分位时建仓（低估）
- 叠加趋势反转信号（止跌企稳）
- 适用于周期底部反转

参考：DGU-stallion/huatai-finengi-report - PB分位<10%时12月平均回报27.3%
"""

import numpy as np
from strategies.base import BaseStrategy


class CycleTimingStrategy(BaseStrategy):
    """周期股择时策略"""

    def __init__(self,
                 low_pb=3.0,           # PB上限（放宽，不再只选低估）
                 price_percentile=80,  # 价格历史分位上限%（改为追涨，>80%分位=创新高）
                 max_pb=5.0,           # PB绝对上限（放宽）
                 holding_days=25,
                 top_n=5):
        super().__init__("周期股择时", "价值因子")
        self.low_pb = low_pb
        self.price_percentile = price_percentile
        self.max_pb = max_pb
        self.holding_days = holding_days
        self.top_n = top_n

        # 周期性行业股票池（钢铁、有色、煤炭、化工、建材）
        self.cycle_pool = [
            {'symbol': '601899', 'name': '紫金矿业'},  # 有色
            {'symbol': '600019', 'name': '宝钢股份'},  # 钢铁
            {'symbol': '601225', 'name': '陕西煤业'},  # 煤炭
            {'symbol': '600585', 'name': '海螺水泥'},  # 建材
            {'symbol': '601600', 'name': '中国铝业'},  # 有色
            {'symbol': '000878', 'name': '云南铜业'},  # 有色
            {'symbol': '600808', 'name': '马钢股份'},  # 钢铁
            {'symbol': '601678', 'name': '滨化股份'},  # 化工
            {'symbol': '002460', 'name': '赣锋锂业'},  # 有色
            {'symbol': '002466', 'name': '天齐锂业'},  # 有色
            {'symbol': '601857', 'name': '中国石油'},  # 石油
            {'symbol': '600028', 'name': '中国石化'},  # 石油
            {'symbol': '601088', 'name': '中国神华'},  # 煤炭
            {'symbol': '600547', 'name': '山东黄金'},  # 黄金
            {'symbol': '601618', 'name': '中国中冶'},  # 冶金
        ]

    def get_description(self):
        return f"周期股择时：PB<{self.low_pb}, 价格分位<{self.price_percentile}%, 持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：周期股PB低位+价格低位"""
        results = []

        scored = []
        for stock in self.cycle_pool:
            symbol = stock['symbol']
            try:
                # 1. 获取长期K线（120日）计算价格分位
                kline = helper.get_history_kline(symbol, days=120, end_date=date)
                if kline.empty or len(kline) < 60:
                    continue

                current = kline['close'].iloc[-1]
                # 价格历史分位（0=最低，100=最高）
                percentile = (kline['close'] < current).sum() / len(kline) * 100

                # 只选价格在低位（分位<20%）
                if percentile > self.price_percentile:
                    continue

                # 2. 趋势反转信号：近5日止跌企稳
                if len(kline) >= 5:
                    ma5 = kline['close'].iloc[-5:].mean()
                    if current < ma5:  # 仍在下跌
                        continue

                # 3. PB估值筛选
                val = helper.get_valuation_data(symbol)
                if not val:
                    continue
                pb = val.get('pb', 0)
                if pb <= 0 or pb > self.max_pb:
                    continue

                # 综合得分：价格在高位+PB低 = 强势周期股
                score = (percentile / 20) + (self.low_pb - pb) + (current / ma5)
                scored.append((symbol, stock['name'], score, pb, percentile))

            except Exception:
                continue

        # 4. 按得分排序
        scored.sort(key=lambda x: x[2], reverse=True)
        for symbol, name, score, pb, pct in scored[:self.top_n]:
            results.append({
                'symbol': symbol,
                'name': name,
                'reason': f"周期低估：PB={pb:.2f}, 价格分位={pct:.0f}%, 得分={score:.2f}"
            })

        return results[:self.top_n]


if __name__ == '__main__':
    s = CycleTimingStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
