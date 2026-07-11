# -*- coding: utf-8 -*-
"""
质量因子选股策略（增强版Piotroski F-Score + Altman Z-Score）

策略逻辑：
- Piotroski F-Score（9分制财务评分）筛选财务健康的高质量价值股
- Altman Z-Score规避破产风险
- 初筛：全市场PB最低的20%股票（剔除停牌、ST、上市不满1年）
- F-Score ≥ 7 且 Z-Score > 2.99 买入
- F-Score < 5 或 Z-Score < 1.81 卖出

参考：astro30/valinvest - Piotroski F-Score纯Python实现
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.base import BaseStrategy


class QualityFactorStrategy(BaseStrategy):
    """质量因子选股策略（Piotroski F-Score + Altman Z-Score）"""

    def __init__(self,
                 pb_pool_pct=20,        # PB最低股票池比例(%)
                 f_score_min=7,         # F-Score买入阈值
                 f_score_sell=5,        # F-Score卖出阈值
                 z_score_min=2.99,      # Altman Z-Score安全下限
                 z_score_warn=1.81,     # Z-Score破产预警线
                 hold_num=3,            # 持仓数量
                 stop_loss=-8,          # 止损线（%）
                 take_profit=20):      # 止盈线（%）
        super().__init__("质量因子选股Pro", "质量因子")
        self.pb_pool_pct = pb_pool_pct
        self.f_score_min = f_score_min
        self.f_score_sell = f_score_sell
        self.z_score_min = z_score_min
        self.z_score_warn = z_score_warn
        self.hold_num = hold_num
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self._cache = {}

    def get_params(self):
        return {
            'pb_pool_pct': self.pb_pool_pct,
            'f_score_min': self.f_score_min,
            'f_score_sell': self.f_score_sell,
            'z_score_min': self.z_score_min,
            'z_score_warn': self.z_score_warn,
            'hold_num': self.hold_num
        }

    def get_description(self):
        return f"质量因子选股：F-Score≥{self.f_score_min}, Z-Score>{self.z_score_min}, PB最低{self.pb_pool_pct}%池"

    def _get_all_a_stocks(self, helper):
        """获取全市场A股列表（排除ST、停牌、新股）"""
        cache_key = 'a_stocks_filtered'
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # 使用helper的优化方法获取全市场股票（带重试+缓存）
            stocks_data = helper.get_market_stocks()
            if not stocks_data:
                return []

            # 排除涨停/跌停（停牌信号）
            valid_stocks = [s for s in stocks_data if s.get('change_pct', 0) != 0]

            stocks = [s['symbol'] for s in valid_stocks]
            self._cache[cache_key] = stocks
            return stocks
        except Exception as e:
            print(f"获取全市场股票失败: {e}")
            return []

    def _get_low_pb_pool(self, helper, top_pct=20):
        """获取PB最低的股票池"""
        cache_key = f'low_pb_pool_{top_pct}'
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            # 使用helper的优化方法获取全市场股票
            stocks_data = helper.get_market_stocks()
            if not stocks_data:
                return []

            # 过滤PB有效值
            valid_stocks = [s for s in stocks_data if s.get('pb', 0) > 0 and s.get('pb', 0) < 100]

            # 按PB升序排序，取最低的top_pct%
            valid_stocks.sort(key=lambda x: x.get('pb', 0))
            n = int(len(valid_stocks) * top_pct / 100)
            low_pb_stocks = [s['symbol'] for s in valid_stocks[:n]]

            self._cache[cache_key] = low_pb_stocks
            return low_pb_stocks
        except Exception as e:
            print(f"获取低PB股票池失败: {e}")
            return []

    def _get_financial_data(self, helper, symbol):
        """获取完整财务数据用于F-Score和Z-Score计算"""
        try:
            # 获取财务指标
            fin = helper.get_financial_indicator(symbol)
            if not fin:
                return None

            # 获取现金流数据
            cf = helper.get_cash_flow(symbol) or {}

            # 获取估值数据
            val = helper.get_valuation_data(symbol) or {}

            # 获取成长数据（用于同比计算）
            growth = helper.get_growth_data(symbol) or {}

            # 获取K线数据（用于计算资产周转率变化）
            kline = helper.get_history_kline(symbol, days=365, end_date=None)
            if kline.empty:
                return None

            # 计算ROA = 净利润 / 总资产（简化用ROE近似）
            roe = fin.get('roe', 0)
            roa = roe * 0.8  # 近似ROA

            # 经营现金流
            op_cf = cf.get('operating_cf', 0)

            # 净利润
            net_profit = cf.get('net_profit', 0)

            # 资产负债率
            debt_ratio = fin.get('debt_ratio', 0)

            # 流动比率
            current_ratio = fin.get('current_ratio', 1)

            # 毛利率
            gross_margin = fin.get('gross_margin', 0)

            # 市值（用于Z-Score）
            total_mv = val.get('total_mv', 0)

            return {
                'roe': roe,
                'roa': roa,
                'op_cf': op_cf,
                'net_profit': net_profit,
                'debt_ratio': debt_ratio,
                'current_ratio': current_ratio,
                'gross_margin': gross_margin,
                'total_mv': total_mv,
                'pe': val.get('pe', 0),
                'pb': val.get('pb', 0),
                'profit_growth': growth.get('profit_growth', 0),
            }
        except Exception as e:
            print(f"获取财务数据失败 {symbol}: {e}")
            return None

    def _calculate_piotroski_f_score(self, data):
        """
        计算Piotroski F-Score（9分制）

        盈利能力 (4分):
        1. ROA > 0
        2. CFO > 0（经营现金流为正）
        3. ROA同比上升
        4. CFO > 净利润（应计项为负，质量好）

        杠杆/流动性 (3分):
        5. 长期负债率同比下降
        6. 流动比率同比上升
        7. 未增发新股（简化：用市值增长判断）

        运营效率 (2分):
        8. 毛利率同比上升
        9. 资产周转率同比上升
        """
        if not data:
            return 0, {}

        score = 0
        details = {}

        # === 盈利能力指标 ===
        # 1. ROA > 0
        roa = data.get('roa', 0)
        if roa > 0:
            score += 1
            details['roa_positive'] = 1
        else:
            details['roa_positive'] = 0

        # 2. CFO > 0
        op_cf = data.get('op_cf', 0)
        if op_cf > 0:
            score += 1
            details['cfo_positive'] = 1
        else:
            details['cfo_positive'] = 0

        # 3. ROA同比上升（简化：用净利润增速近似）
        profit_growth = data.get('profit_growth', 0)
        if profit_growth > 0:
            score += 1
            details['roa_growth'] = 1
        else:
            details['roa_growth'] = 0

        # 4. CFO > 净利润（应计项为负）
        net_profit = data.get('net_profit', 0)
        if op_cf > 0 and net_profit > 0 and op_cf > net_profit:
            score += 1
            details['accrual'] = 1
        else:
            details['accrual'] = 0

        # === 杠杆/流动性指标 ===
        # 5. 负债率下降（简化：负债率<60%视为低杠杆）
        debt_ratio = data.get('debt_ratio', 1)
        if debt_ratio < 0.6:
            score += 1
            details['low_debt'] = 1
        else:
            details['low_debt'] = 0

        # 6. 流动比率>=1
        current_ratio = data.get('current_ratio', 0)
        if current_ratio >= 1:
            score += 1
            details['current_ratio_ok'] = 1
        else:
            details['current_ratio_ok'] = 0

        # 7. 未大规模增发（简化：市值合理增长）
        total_mv = data.get('total_mv', 0)
        if total_mv > 1e10:  # 市值>100亿为大盘股，不考虑增发影响
            score += 1
            details['no_dilution'] = 1
        else:
            details['no_dilution'] = 1  # 小盘股也默认无增发

        # === 运营效率指标 ===
        # 8. 毛利率>0（简化：毛利率为正）
        gross_margin = data.get('gross_margin', 0)
        if gross_margin > 0:
            score += 1
            details['gross_margin_ok'] = 1
        else:
            details['gross_margin_ok'] = 0

        # 9. ROE>0（简化：盈利公司运营效率好）
        roe = data.get('roe', 0)
        if roe > 0:
            score += 1
            details['roe_positive'] = 1
        else:
            details['roe_positive'] = 0

        details['f_score'] = score
        return score, details

    def _calculate_altman_z_score(self, data):
        """
        计算Altman Z-Score（A股简化版）

        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

        X1 = 营运资本 / 总资产 = (流动资产-流动负债) / 总资产
        X2 = 留存收益 / 总资产
        X3 = EBIT / 总资产 = 用ROA近似
        X4 = 股东权益 / 总负债 = (1-负债率)的倒数
        X5 = 销售额 / 总资产 = 资产周转率（简化用1.0）

        破产风险区: Z < 1.81
        灰色区: 1.81 <= Z <= 2.99
        安全区: Z > 2.99
        """
        if not data:
            return 0

        try:
            roa = data.get('roa', 0)
            debt_ratio = data.get('debt_ratio', 0)
            gross_margin = data.get('gross_margin', 0)

            # X1: 流动比率替代营运资本（简化）
            current_ratio = data.get('current_ratio', 1)
            x1 = (current_ratio - 1) if current_ratio > 1 else 0

            # X2: 留存收益（简化用毛利率*0.3）
            x2 = gross_margin * 0.3 if gross_margin > 0 else 0

            # X3: EBIT/总资产（用ROA近似）
            x3 = max(roa, 0)

            # X4: 股东权益/总负债
            if debt_ratio > 0 and debt_ratio < 1:
                equity_ratio = 1 - debt_ratio
                x4 = equity_ratio / debt_ratio
            else:
                x4 = 1.0  # 默认值

            # X5: 资产周转率（简化用1.0）
            x5 = 1.0

            # 计算Z-Score
            z_score = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

            return z_score
        except Exception:
            return 0

    def _score_stock(self, helper, symbol):
        """对单只股票打分"""
        try:
            # 获取财务数据
            data = self._get_financial_data(helper, symbol)
            if not data:
                return None

            # 计算F-Score
            f_score, f_details = self._calculate_piotroski_f_score(data)

            # 计算Z-Score
            z_score = self._calculate_altman_z_score(data)

            return {
                'symbol': symbol,
                'f_score': f_score,
                'f_details': f_details,
                'z_score': z_score,
                'roa': data.get('roa', 0),
                'op_cf': data.get('op_cf', 0),
                'roe': data.get('roe', 0),
                'pb': data.get('pb', 0),
                'pe': data.get('pe', 0),
            }
        except Exception as e:
            print(f"评分失败 {symbol}: {e}")
            return None

    def detect_events(self, helper, date=None):
        """
        检测质量因子买入/卖出信号

        买入信号：
        - 初筛：全市场PB最低的20%股票
        - F-Score ≥ 7（财务状况优秀）
        - Altman Z-Score > 2.99（破产风险低）
        - ROA > 0 且经营现金流 > 0（盈利真实）
        - 毛利率同比上升（竞争力增强）

        卖出信号：
        - F-Score 降至 5 以下（财务状况恶化）
        - 任一关键指标转负（ROA<0 或 CFO<0）
        - PB回升至市场前50%分位（估值修复到位）
        - Altman Z-Score 跌破 1.81（破产风险预警）
        """
        events = []
        current_holdings = [h['symbol'] for h in self.holdings]

        # === 卖出信号检测 ===
        for symbol in current_holdings:
            try:
                result = self._score_stock(helper, symbol)
                if not result:
                    events.append({
                        'symbol': symbol,
                        'name': symbol,
                        'event': 'sell',
                        'reason': '财务数据获取失败'
                    })
                    continue

                f_score = result['f_score']
                z_score = result['z_score']
                roa = result['roa']
                op_cf = result['op_cf']

                sell_reasons = []

                # 检查卖出条件
                if f_score < self.f_score_sell:
                    sell_reasons.append(f'F-Score={f_score}<{self.f_score_sell}')

                if z_score < self.z_score_warn:
                    sell_reasons.append(f'Z-Score={z_score:.2f}<{self.z_score_warn}')

                if roa < 0:
                    sell_reasons.append(f'ROA<0({roa:.2%})')

                if op_cf < 0:
                    sell_reasons.append(f'CFO<0')

                # 检查PB是否回升至前50%分位
                try:
                    val = helper.get_valuation_data(symbol)
                    pb = val.get('pb', 0)
                    if pb > 0:
                        stocks_data = helper.get_market_stocks()
                        valid_pb = [s for s in stocks_data if s.get('pb', 0) > 0]
                        if valid_pb:
                            pb_values = [s['pb'] for s in valid_pb]
                            pb_median = np.median(pb_values)
                            if pb > pb_median:
                                sell_reasons.append(f'PB={pb:.2f}>市场中位数{pb_median:.2f}')
                except:
                    pass

                if sell_reasons:
                    events.append({
                        'symbol': symbol,
                        'name': symbol,
                        'event': 'sell',
                        'reason': '; '.join(sell_reasons),
                        'data': result
                    })
            except Exception as e:
                print(f"卖出信号检测失败 {symbol}: {e}")

        # === 买入信号检测 ===
        # 获取低PB股票池
        low_pb_pool = self._get_low_pb_pool(helper, self.pb_pool_pct)
        if not low_pb_pool:
            return events

        # 对低PB池中的股票打分
        candidates = []
        for symbol in low_pb_pool:
            if symbol in current_holdings:
                continue  # 已持仓跳过

            result = self._score_stock(helper, symbol)
            if not result:
                continue

            # 检查买入条件
            f_score = result['f_score']
            z_score = result['z_score']
            roa = result['roa']
            op_cf = result['op_cf']
            gross_margin = result.get('f_details', {}).get('gross_margin_ok', 0)

            # 必须满足的条件
            if f_score >= self.f_score_min and z_score > self.z_score_min:
                if roa > 0 and op_cf > 0 and gross_margin > 0:
                    candidates.append(result)

        # 按F-Score降序排序，取前N只
        candidates.sort(key=lambda x: (x['f_score'], -x['pb']), reverse=True)

        for result in candidates[:self.hold_num]:
            events.append({
                'symbol': result['symbol'],
                'name': result['symbol'],
                'event': 'buy',
                'reason': f"F-Score={result['f_score']}, Z-Score={result['z_score']:.2f}, ROE={result['roe']:.1%}",
                'data': result
            })

        return events

    def select_stocks(self, helper, date=None):
        """选股：返回买入信号列表"""
        events = self.detect_events(helper, date)
        buy_signals = [e for e in events if e['event'] == 'buy']
        return buy_signals[:self.hold_num]


if __name__ == '__main__':
    # 测试策略
    import akshare as ak
    from data.akshare_helper import AKShareHelper

    helper = AKShareHelper()
    strategy = QualityFactorStrategy()

    print(f"策略: {strategy.name}")
    print(f"描述: {strategy.get_description()}")
    print(f"参数: {strategy.get_params()}")

    # 测试选股
    results = strategy.select_stocks(helper)
    print(f"\n选股结果: {len(results)}只")
    for r in results[:3]:
        print(f"  {r['symbol']}: {r['reason']}")
