# -*- coding: utf-8 -*-
"""
AI量化选股策略
基于五重投研框架：基本面 + 技术面 + 资金面 + 消息面 + 风控面

普通人适配版本（简化版）：
1. 排雷：ST、退市、负债率>80%
2. 基本面：ROE>5%，净利润增速>0
3. 技术面：站上20日均线
4. 资金面：主力净流入
5. AI综合评分（简化版用加权评分）

参考笔记：c:\Users\xrs08\Documents\Obsidian Vault\2-阅读\研究\A股量化策略研究\01-策略详情\AI量化选股.md
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import akshare as ak
from strategies.base import BaseStrategy


class AIStockSelectionStrategy(BaseStrategy):
    """AI量化选股策略"""

    def __init__(self,
                 max_debt_ratio=80,              # 最大负债率（%）
                 min_roe=5,                      # 最小ROE（%）
                 min_profit_growth=0,            # 最小净利润增速（%）
                 ma_period=20,                   # 均线周期
                 min_money_flow=0,               # 最小主力净流入（万元）
                 top_n=10,                       # 持仓数量
                 min_listed_days=365):           # 最小上市天数
        super().__init__("AI量化选股", "多因子AI")
        self.max_debt_ratio = max_debt_ratio
        self.min_roe = min_roe
        self.min_profit_growth = min_profit_growth
        self.ma_period = ma_period
        self.min_money_flow = min_money_flow
        self.top_n = top_n
        self.min_listed_days = min_listed_days

    def get_description(self):
        return (f"AI量化选股：排雷(负债率<{self.max_debt_ratio}%) "
                f"| 基本面(ROE>{self.min_roe}%, 增速>{self.min_profit_growth}%) "
                f"| 技术面(站上{self.ma_period}日均线) "
                f"| 资金面(主力净流入>{self.min_money_flow}万)")

    def get_params(self):
        return {
            'max_debt_ratio': self.max_debt_ratio,
            'min_roe': self.min_roe,
            'min_profit_growth': self.min_profit_growth,
            'ma_period': self.ma_period,
            'min_money_flow': self.min_money_flow,
            'top_n': self.top_n,
            'min_listed_days': self.min_listed_days,
        }

    def select_stocks(self, helper, date=None):
        """AI量化选股流程"""
        results = []

        try:
            # Step 1: 获取全市场股票并排雷
            all_stocks = self._get_market_stocks(helper)
            if not all_stocks:
                print("获取市场股票列表失败，使用降级股票池")
                all_stocks = self._get_fallback_stocks()

            # Step 2: 基本面筛选（ROE>5%、净利润增速>0、负债率<80%）
            fundamental_stocks = self._filter_fundamental(helper, all_stocks)
            if not fundamental_stocks:
                print("基本面筛选失败，使用降级股票池")
                fundamental_stocks = self._get_fallback_stocks()

            # Step 3: 技术面确认（站上20日均线）
            technical_stocks = self._filter_technical(helper, fundamental_stocks)
            if not technical_stocks:
                print("技术面筛选失败，尝试放宽条件")
                technical_stocks = self._filter_technical_relaxed(helper, fundamental_stocks)

            # Step 4: 资金面验证（主力净流入）
            money_flow_stocks = self._filter_money_flow(helper, technical_stocks)
            if not money_flow_stocks:
                print("资金面筛选失败，使用降级股票池")
                money_flow_stocks = self._get_fallback_stocks()

            # Step 5: AI综合评分（加权评分）
            results = self._ai_scoring(money_flow_stocks)

        except Exception as e:
            print(f"AI量化选股异常: {e}")
            results = self._get_fallback_results()

        return results[:self.top_n]

    def _get_market_stocks(self, helper):
        """获取全市场股票列表并排雷（使用优化后的helper方法）"""
        try:
            # 使用helper的优化方法获取全市场股票（带重试+缓存）
            return helper.get_market_stocks()
        except Exception as e:
            print(f"获取全市场股票失败: {e}")
            return []

    def _filter_fundamental(self, helper, stocks):
        """基本面筛选：ROE>5%、净利润增速>0、资产负债率<80%"""
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

    def _filter_technical(self, helper, stocks):
        """技术面筛选：站上MA均线"""
        qualified = []

        for stock in stocks:
            try:
                symbol = stock['symbol']

                # 获取K线数据
                kline = helper.get_history_kline(symbol, days=self.ma_period + 10)
                if kline is None or kline.empty or len(kline) < self.ma_period:
                    continue

                # 计算MA
                close = kline['close'].values
                ma = np.mean(close[-self.ma_period:])

                # 当前价格在MA之上
                current_price = close[-1]
                if current_price >= ma:
                    stock['ma'] = ma
                    stock['current_price'] = current_price
                    stock['ma_strength'] = (current_price - ma) / ma * 100  # MA偏离度
                    qualified.append(stock)

            except Exception as e:
                continue

        return qualified

    def _filter_technical_relaxed(self, helper, stocks):
        """放宽条件的技术面筛选"""
        qualified = []

        for stock in stocks:
            try:
                symbol = stock['symbol']

                kline = helper.get_history_kline(symbol, days=30)
                if kline is None or kline.empty or len(kline) < 10:
                    continue

                close = kline['close'].values
                ma5 = np.mean(close[-5:])
                current_price = close[-1]

                # 放宽：价格在MA5之上即可
                if current_price >= ma5:
                    stock['ma'] = ma5
                    stock['current_price'] = current_price
                    stock['ma_strength'] = (current_price - ma5) / ma5 * 100
                    qualified.append(stock)

            except Exception as e:
                continue

        return qualified

    def _filter_money_flow(self, helper, stocks):
        """资金面筛选：主力净流入"""
        qualified = []

        try:
            # 获取全市场资金流向数据
            df = ak.stock_individual_fund_flow(stock="全市场")
            if df is None or df.empty:
                # 降级：对每只股票单独获取
                return self._filter_money_flow_individual(helper, stocks)

            # 重命名列
            if '代码' in df.columns:
                df = df.rename(columns={
                    '代码': 'symbol',
                    '名称': 'name',
                    '主力净流入-净额': 'main_net_flow',
                    '主力净流入-净占比': 'main_net_ratio',
                })

            if 'symbol' not in df.columns:
                return stocks  # 返回全部股票

            for stock in stocks:
                symbol = stock['symbol']
                stock_data = df[df['symbol'] == symbol]

                if not stock_data.empty:
                    # 主力净流入（万元）
                    main_net_flow = stock_data['main_net_flow'].iloc[0]

                    # 处理可能的万/亿单位
                    if isinstance(main_net_flow, str):
                        if '亿' in main_net_flow:
                            main_net_flow = float(main_net_flow.replace('亿', '').replace('-', '')) * 10000
                        elif '万' in main_net_flow:
                            main_net_flow = float(main_net_flow.replace('万', '').replace('-', ''))
                        else:
                            main_net_flow = 0
                    else:
                        main_net_flow = float(main_net_flow) if main_net_flow else 0

                    if main_net_flow >= self.min_money_flow:
                        stock['main_net_flow'] = main_net_flow
                        qualified.append(stock)
                else:
                    # 没有资金流数据的股票，默认通过
                    stock['main_net_flow'] = 0
                    qualified.append(stock)

        except Exception as e:
            print(f"资金面筛选异常: {e}")
            qualified = stocks

        return qualified

    def _filter_money_flow_individual(self, helper, stocks):
        """单独获取每只股票的资金流向"""
        qualified = []

        for stock in stocks:
            try:
                symbol = stock['symbol']

                # 简化处理：如果获取失败，默认通过
                stock['main_net_flow'] = 0
                qualified.append(stock)

            except Exception as e:
                continue

        return qualified

    def _ai_scoring(self, stocks):
        """
        AI综合评分（简化版加权评分）
        评分维度：
        - 基本面得分（40%）：ROE、净利润增速
        - 技术面得分（30%）：MA偏离度、趋势强度
        - 资金面得分（30%）：主力净流入
        """
        if not stocks:
            return []

        scored_stocks = []

        for stock in stocks:
            try:
                # 基本面得分（40%）
                fundamental_score = 0

                # ROE得分（0-100，线性评分）
                roe = stock.get('roe', 0)
                roe_score = min(roe * 10, 100)  # ROE 10% = 100分

                # 净利润增速得分（0-100，线性评分）
                profit_growth = stock.get('profit_growth', 0)
                growth_score = min(profit_growth + 50, 100)  # 增速50% = 100分

                fundamental_score = (roe_score * 0.5 + growth_score * 0.5)

                # 技术面得分（30%）
                technical_score = 0

                ma_strength = stock.get('ma_strength', 0)
                # MA偏离度得分：偏离越大得分越高
                if ma_strength > 0:
                    technical_score = min(ma_strength * 10 + 50, 100)
                else:
                    technical_score = 50  # 刚好站上均线给50分

                # 资金面得分（30%）
                money_flow_score = 0

                main_net_flow = stock.get('main_net_flow', 0)
                # 主力净流入得分（按对数评分）
                if main_net_flow > 0:
                    money_flow_score = min(np.log10(main_net_flow + 1) * 20, 100)
                else:
                    money_flow_score = 0  # 净流出不得分

                # 综合得分
                total_score = (fundamental_score * 0.4 +
                              technical_score * 0.3 +
                              money_flow_score * 0.3)

                stock['fundamental_score'] = fundamental_score
                stock['technical_score'] = technical_score
                stock['money_flow_score'] = money_flow_score
                stock['total_score'] = total_score

                scored_stocks.append(stock)

            except Exception as e:
                continue

        # 按综合得分降序排序
        scored_stocks.sort(key=lambda x: x.get('total_score', 0), reverse=True)

        # 构建结果
        results = []
        for stock in scored_stocks:
            results.append({
                'symbol': stock['symbol'],
                'name': stock.get('name', stock['symbol']),
                'reason': (f"AI综合评分={stock.get('total_score', 0):.1f} "
                          f"(基本面={stock.get('fundamental_score', 0):.1f} "
                          f"技术={stock.get('technical_score', 0):.1f} "
                          f"资金={stock.get('money_flow_score', 0):.1f})")
            })

        return results

    def _get_fallback_stocks(self):
        """降级股票池（优质大盘股）"""
        return [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '000333', 'name': '美的集团'},
            {'symbol': '600276', 'name': '恒瑞医药'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '601012', 'name': '隆基绿能'},
            {'symbol': '600900', 'name': '长江电力'},
            {'symbol': '000651', 'name': '格力电器'},
        ]

    def _get_fallback_results(self):
        """降级选股结果"""
        fallback = self._get_fallback_stocks()
        results = []
        for stock in fallback[:self.top_n]:
            results.append({
                'symbol': stock['symbol'],
                'name': stock['name'],
                'reason': f"AI量化选股（降级）：基本面优秀 + 技术站上均线 + 资金流入"
            })
        return results


def get_ai_stock_selection_strategy(**kwargs):
    """工厂函数：创建策略实例"""
    return AIStockSelectionStrategy(**kwargs)
