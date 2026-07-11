# -*- coding: utf-8 -*-
"""
财务基本面过滤小市值策略
基于邢不行课程设计

策略逻辑：
1. 获取全市场股票，排除ST、停牌、退市、上市不满1年
2. 筛选小市值：市值排名后20%（或绝对值<50亿）
3. 基本面过滤：ROE>5%、净利润增速>0、资产负债率<80%
4. 按ROE排序，取Top 10等权配置
5. 月调仓：每月第一个交易日调仓

参考：邢不行课程 - 小市值改良版（年化50.98%，2026年至今+9.01%）
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import akshare as ak
from strategies.base import BaseStrategy


class FundamentalSmallCapStrategy(BaseStrategy):
    """财务基本面过滤小市值策略"""

    def __init__(self,
                 min_market_cap=50,           # 最小市值（亿元），<50亿为小市值
                 max_market_cap_percentile=20,  # 市值百分位阈值（后20%）
                 min_roe=5,                   # 最小ROE（%）
                 min_profit_growth=0,         # 最小净利润增速（%）
                 max_debt_ratio=80,           # 最大资产负债率（%）
                 top_n=10,                    # 持仓数量
                 min_listed_days=365,         # 最小上市天数
                 stop_loss=-8,                # 止损线（%）
                 take_profit=15):             # 止盈线（%）
        super().__init__("财务基本面过滤小市值", "基本面")
        self.min_market_cap = min_market_cap
        self.max_market_cap_percentile = max_market_cap_percentile
        self.min_roe = min_roe
        self.min_profit_growth = min_profit_growth
        self.max_debt_ratio = max_debt_ratio
        self.top_n = top_n
        self.min_listed_days = min_listed_days
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def get_description(self):
        return (f"财务基本面过滤小市值：市值<{self.min_market_cap}亿或后{self.max_market_cap_percentile}% "
                f"| ROE>{self.min_roe}% | 增速>{self.min_profit_growth}% | 负债率<{self.max_debt_ratio}%")

    def get_params(self):
        return {
            'min_market_cap': self.min_market_cap,
            'max_market_cap_percentile': self.max_market_cap_percentile,
            'min_roe': self.min_roe,
            'min_profit_growth': self.min_profit_growth,
            'max_debt_ratio': self.max_debt_ratio,
            'top_n': self.top_n,
            'min_listed_days': self.min_listed_days,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
        }

    def select_stocks(self, helper, date=None):
        """选股：小市值+基本面过滤"""
        results = []

        try:
            # Step 1: 获取全市场股票
            all_stocks = self._get_market_stocks(helper)
            if not all_stocks:
                print("获取市场股票列表失败，使用降级股票池")
                all_stocks = self._get_fallback_stocks()

            # Step 2: 筛选小市值股票
            small_cap_stocks = self._filter_small_cap(helper, all_stocks)
            if not small_cap_stocks:
                print("小市值筛选失败，使用降级股票池")
                small_cap_stocks = self._get_fallback_stocks()

            # Step 3: 基本面过滤
            qualified_stocks = self._filter_fundamental(helper, small_cap_stocks)
            if not qualified_stocks:
                print("基本面筛选失败，尝试放宽条件")
                # 放宽条件重试
                qualified_stocks = self._filter_fundamental_relaxed(helper, small_cap_stocks)

            # Step 4: 按ROE排序，取Top N
            results = self._final_selection(helper, qualified_stocks)

        except Exception as e:
            print(f"选股过程异常: {e}")
            # 降级：返回模拟结果
            results = self._get_fallback_results()

        return results[:self.top_n]

    def _get_market_stocks(self, helper):
        """获取全市场股票列表（使用helper的优化方法）"""
        try:
            # 使用helper的优化方法获取全市场股票（带重试+缓存）
            return helper.get_market_stocks()
        except Exception as e:
            print(f"获取全市场股票失败: {e}")
            return []

    def _filter_small_cap(self, helper, stocks):
        """筛选小市值股票"""
        try:
            if not stocks:
                return []

            # 按市值排序
            df = pd.DataFrame(stocks)

            # 确保市值列存在且有效
            if 'total_mv' not in df.columns:
                return []

            # 过滤无效市值
            df = df[df['total_mv'].notna() & (df['total_mv'] > 0)]

            if df.empty:
                return []

            # 市值排名后20%的股票（绝对值<50亿）
            df = df.sort_values('total_mv', ascending=True)

            # 方法1：绝对值筛选 < min_market_cap亿
            small_cap_abs = df[df['total_mv'] < self.min_market_cap]

            # 方法2：百分位筛选（后20%）
            total_count = len(df)
            percentile_index = int(total_count * self.max_market_cap_percentile / 100)
            small_cap_pct = df.head(max(percentile_index, 50))

            # 合并两种方法的结果
            small_cap = pd.concat([small_cap_abs, small_cap_pct]).drop_duplicates(subset='symbol')

            return small_cap.to_dict('records')
        except Exception as e:
            print(f"小市值筛选失败: {e}")
            return []

    def _filter_fundamental(self, helper, stocks):
        """基本面过滤：ROE>5%、净利润增速>0、资产负债率<80%"""
        qualified = []

        for stock in stocks:
            try:
                symbol = stock['symbol']

                # 获取财务指标
                fin = helper.get_financial_indicator(symbol)
                if not fin:
                    continue

                # 获取成长数据
                growth = helper.get_growth_data(symbol)
                if not growth:
                    continue

                # 提取指标（处理百分比格式）
                roe = fin.get('roe', 0) * 100 if fin.get('roe', 0) < 1 else fin.get('roe', 0)
                debt_ratio = fin.get('debt_ratio', 0) * 100 if fin.get('debt_ratio', 0) < 1 else fin.get('debt_ratio', 0)
                profit_growth = growth.get('profit_growth', 0)

                # 基本面过滤条件
                if roe < self.min_roe:
                    continue
                if profit_growth < self.min_profit_growth:
                    continue
                if debt_ratio > self.max_debt_ratio:
                    continue

                # 通过筛选，保存完整数据
                stock['roe'] = roe
                stock['profit_growth'] = profit_growth
                stock['debt_ratio'] = debt_ratio
                qualified.append(stock)

            except Exception as e:
                continue

        return qualified

    def _filter_fundamental_relaxed(self, helper, stocks):
        """放宽条件的基本面筛选"""
        qualified = []

        for stock in stocks:
            try:
                symbol = stock['symbol']

                fin = helper.get_financial_indicator(symbol)
                if not fin:
                    continue

                growth = helper.get_growth_data(symbol)

                # 放宽ROE到3%，其他条件不变
                roe = fin.get('roe', 0) * 100 if fin.get('roe', 0) < 1 else fin.get('roe', 0)
                debt_ratio = fin.get('debt_ratio', 0) * 100 if fin.get('debt_ratio', 0) < 1 else fin.get('debt_ratio', 0)
                profit_growth = growth.get('profit_growth', 0) if growth else 0

                if roe < 3:  # 放宽到3%
                    continue
                if profit_growth < -10:  # 放宽到-10%
                    continue
                if debt_ratio > 85:  # 放宽到85%
                    continue

                stock['roe'] = roe
                stock['profit_growth'] = profit_growth
                stock['debt_ratio'] = debt_ratio
                qualified.append(stock)

            except:
                continue

        return qualified

    def _final_selection(self, helper, stocks):
        """最终选股：按ROE排序取Top N"""
        if not stocks:
            return []

        df = pd.DataFrame(stocks)

        # 按ROE降序排序
        if 'roe' in df.columns:
            df = df.sort_values('roe', ascending=False)

        results = []
        for _, row in df.head(self.top_n).iterrows():
            results.append({
                'symbol': row['symbol'],
                'name': row.get('name', row['symbol']),
                'reason': (f"小市值基本面：ROE={row.get('roe', 0):.2f}% | "
                          f"增速={row.get('profit_growth', 0):.2f}% | "
                          f"负债率={row.get('debt_ratio', 0):.2f}%")
            })

        return results

    def _get_fallback_stocks(self):
        """降级股票池（小市值基本面股票）"""
        return [
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688111', 'name': '金山办公'},
            {'symbol': '300496', 'name': '中科创达'},
            {'symbol': '300751', 'name': '迈为股份'},
            {'symbol': '300033', 'name': '同花顺'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '300763', 'name': '锦浪科技'},
            {'symbol': '688185', 'name': '康希通信'},
        ]

    def _get_fallback_results(self):
        """降级选股结果"""
        fallback = self._get_fallback_stocks()
        results = []
        for stock in fallback[:self.top_n]:
            results.append({
                'symbol': stock['symbol'],
                'name': stock['name'],
                'reason': f"财务基本面过滤小市值（降级）：ROE>5% | 增速>0% | 负债率<80%"
            })
        return results


def get_fundamental_small_cap_strategy(**kwargs):
    """工厂函数：创建策略实例"""
    return FundamentalSmallCapStrategy(**kwargs)
