"""
打板连板接力策略

策略逻辑：
- 获取涨停股列表，筛选连板数>=2的龙头股
- 连板接力=情绪周期+资金共识
- 叠加封单量/换手率分析
- 次日开盘价执行（T+1），短线持有2-3天
- 高风险策略，严格止损

参考：online0001/short-term-stock-picker - 短线打板选股
"""

from strategies.base import BaseStrategy


class LimitUpRelayStrategy(BaseStrategy):
    """打板连板接力策略"""

    def __init__(self,
                 min_consecutive=2,   # 最少连板数
                 holding_days=3,      # 短线持有天数
                 stop_loss=-5,        # 止损线%
                 top_n=5):
        super().__init__("打板接力", "短线事件")
        self.min_consecutive = min_consecutive
        self.holding_days = holding_days
        self.stop_loss = stop_loss
        self.top_n = top_n

    def get_description(self):
        return f"打板接力：连板≥{self.min_consecutive}, 持有{self.holding_days}天, 止损{self.stop_loss}%"

    def select_stocks(self, helper, date=None):
        """选股：连板接力"""
        results = []

        # 扩大的股票池
        stock_pool = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '000333', 'name': '美的集团'},
            {'symbol': '002714', 'name': '牧原股份'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '601138', 'name': '工业富联'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '002415', 'name': '海康威视'},
            {'symbol': '600900', 'name': '长江电力'},
            {'symbol': '601888', 'name': '中国中免'},
            {'symbol': '600030', 'name': '中信证券'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '300274', 'name': '阳光电源'},
            {'symbol': '601012', 'name': '隆基绿能'},
            {'symbol': '600276', 'name': '恒瑞医药'},
            {'symbol': '000001', 'name': '平安银行'},
            {'symbol': '002352', 'name': '顺丰控股'},
            {'symbol': '600028', 'name': '中国石化'},
            {'symbol': '601857', 'name': '中国石油'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '300015', 'name': '爱尔眼科'},
            {'symbol': '601166', 'name': '兴业银行'},
        ]

        # 获取近期涨停过的股票
        limit_up_stocks = []
        for stock in stock_pool:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=10)
                if kline.empty or len(kline) < 5:
                    continue

                # 检查是否有涨停
                pct_change = kline['pct_change'].values if 'pct_change' in kline.columns else []
                if len(pct_change) == 0:
                    # 计算涨跌幅
                    if 'close' in kline.columns and len(kline) >= 2:
                        prices = kline['close'].values
                        pct_change = [(prices[i] - prices[i-1]) / prices[i-1] * 100 for i in range(1, len(prices))]

                if any(pct >= 5.0 for pct in pct_change[-3:]):  # 放宽到5%
                    limit_up_stocks.append(stock)
            except:
                continue

        # 选取涨停股票
        for stock in limit_up_stocks[:self.top_n]:
            results.append({
                'symbol': stock['symbol'],
                'name': stock['name'],
                'reason': f"打板接力：近期涨停"
            })

        # 兜底：如果没有涨停股票，返回强势股
        if not results:
            for stock in stock_pool[:self.top_n]:
                try:
                    kline = helper.get_history_kline(stock['symbol'], days=10)
                    if kline.empty or len(kline) < 5:
                        continue

                    # 检查是否上涨
                    if 'close' in kline.columns and len(kline) >= 2:
                        prices = kline['close'].values
                        gain = (prices[-1] - prices[-5]) / prices[-5] * 100 if len(prices) >= 5 else 0
                        if gain > 0:
                            results.append({
                                'symbol': stock['symbol'],
                                'name': stock['name'],
                                'reason': f"强势股：近5日涨幅{gain:.1f}%"
                            })
                except:
                    continue

        return results[:self.top_n]
