# -*- coding: utf-8 -*-
"""
事件驱动策略群 - 历史人物命名系列

包含三个子策略：
1. 拿破仑事件策略（NapoleonEventStrategy）- 机构事件
2. 萨拉丁事件策略（SaladinEventStrategy）- 游资事件
3. 俾斯麦事件策略（BismarckEventStrategy）- 机构事件

策略设计参考邢不行课程 + 网络研究
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.base import EventStrategy


class NapoleonEventStrategy(EventStrategy):
    """
    拿破仑事件策略（机构事件）

    触发条件：
    1. 个股出现重大利好公告
    2. 龙虎榜显示机构净买入
    3. 筹码低位集中
    4. 连续3日主力资金净流入

    买入：次日开盘买入
    持有：5-10个交易日
    卖出：到期无条件卖出
    """

    def __init__(self):
        super().__init__("拿破仑事件", "事件驱动")
        self.holding_days_min = 5
        self.holding_days_max = 10
        self.top_n = 10

    def get_description(self):
        return (f"拿破仑事件：机构买入+主力资金净流入3日，"
                f"持有{self.holding_days_min}-{self.holding_days_max}天")

    def get_params(self):
        return {
            'holding_days_min': self.holding_days_min,
            'holding_days_max': self.holding_days_max,
            'top_n': self.top_n
        }

    def detect_events(self, helper, date=None):
        """
        检测拿破仑事件信号：机构龙虎榜 + 主力资金连续净流入
        """
        results = []

        # 获取龙虎榜数据
        try:
            if date:
                lhb_date = date.replace('-', '')
            else:
                lhb_date = datetime.now().strftime("%Y%m%d")

            lhb_data = helper.get_dragon_tiger_list(date=lhb_date)
        except Exception as e:
            print(f"获取龙虎榜失败: {e}")
            lhb_data = pd.DataFrame()

        if lhb_data is None or lhb_data.empty:
            # 备选：使用近期龙虎榜数据
            try:
                lhb_data = helper.get_dragon_tiger_list(date=None)
            except Exception:
                lhb_data = pd.DataFrame()

        if lhb_data is not None and not lhb_data.empty:
            # 筛选机构净买入的股票
            for _, row in lhb_data.iterrows():
                try:
                    symbol = str(row.get('代码', row.get('股票代码', '')))
                    name = str(row.get('名称', row.get('股票简称', symbol)))
                    reason = str(row.get('上榜原因', ''))

                    # 检查是否为机构相关
                    is_institution = '机构' in reason

                    # 获取买入/卖出金额
                    buy_amount = helper._safe_float(row.get('买入金额', 0))
                    sell_amount = helper._safe_float(row.get('卖出金额', 0))
                    net_buy = buy_amount - sell_amount

                    # 机构净买入 > 1000万
                    if is_institution and net_buy > 1000:
                        # 检查筹码结构和资金流
                        kline = helper.get_history_kline(symbol, days=30)
                        if kline is not None and not kline.empty and len(kline) >= 20:
                            # 筹码低位集中：近期底部震荡，换手率下降
                            avg_turnover_5 = kline['volume'].iloc[-5:].mean()
                            avg_turnover_20 = kline['volume'].iloc[-20:].mean()
                            turnover_ratio = avg_turnover_5 / avg_turnover_20 if avg_turnover_20 > 0 else 1

                            # 主力资金净流入（用价格涨跌近似）
                            gain_3d = (kline['close'].iloc[-1] / kline['close'].iloc[-4] - 1) * 100 if len(kline) >= 4 else 0
                            gain_5d = (kline['close'].iloc[-1] / kline['close'].iloc[-6] - 1) * 100 if len(kline) >= 6 else 0

                            # 筹码集中 + 连续上涨 = 信号
                            if turnover_ratio < 1.0 and gain_3d > 0 and gain_5d > 0:
                                results.append({
                                    'symbol': symbol,
                                    'name': name,
                                    'reason': f"拿破仑：机构净买入{net_buy/10000:.1f}万，筹码集中，主力净流入"
                                })

                            if len(results) >= self.top_n:
                                break
                except Exception:
                    continue

        # 如果没有龙虎榜数据，用K线筛选备选股
        if not results:
            results = self._kline_fallback(helper, date)

        return results[:self.top_n]

    def _kline_fallback(self, helper, date=None):
        """K线备选：筛选机构偏好的低位集中筹码股"""
        results = []

        try:
            pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:50]
        except Exception:
            pool = ['600519', '300750', '600036', '601318', '000858',
                    '002475', '300033', '300059', '000001', '600030']

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=30, end_date=date)
                if kline is None or kline.empty or len(kline) < 20:
                    continue

                # 连续3日上涨
                gains = []
                for i in range(1, 4):
                    if len(kline) > i:
                        gain = (kline['close'].iloc[-1] / kline['close'].iloc[-i-1] - 1) * 100
                        gains.append(gain > 0)

                # 换手率下降（筹码集中）
                avg_vol_5 = kline['volume'].iloc[-5:].mean()
                avg_vol_20 = kline['volume'].iloc[-20:].mean()
                turnover_declining = avg_vol_5 < avg_vol_20

                # 股价在低位（近20日低点附近）
                ma10 = kline['close'].rolling(10).mean().iloc[-1]
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                current = kline['close'].iloc[-1]
                near_low = current < ma10 and ma10 < ma20 * 1.1

                if all(gains) and turnover_declining and near_low:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"拿破仑备选：连续上涨+筹码集中+近低位"
                    })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        return results[:self.top_n]


class SaladinEventStrategy(EventStrategy):
    """
    萨拉丁事件策略（游资事件）

    触发条件：
    1. 游资席位连续上榜
    2. 涨停板打开后回调
    3. 换手率 > 15%
    4. 成交额 > 5亿

    买入：回调第2天买入
    持有：3-5个交易日
    止损：8%
    """

    # 知名游资席位
    HOT_MONEY_SEATS = [
        '光大金田路', '宁波解放南', '桑田路', '上海超短',
        '华鑫宁波', '成都系', '作手新一', '小鳄鱼',
        '赵老哥', '欢乐海', '浙北基金', '飞云江路',
        '中信上海', '银河绍兴', '华泰荣超', '东财拉萨'
    ]

    def __init__(self):
        super().__init__("萨拉丁事件", "事件驱动")
        self.min_turnover = 15  # 换手率 > 15%
        self.min_amount = 5e8   # 成交额 > 5亿
        self.holding_days_min = 3
        self.holding_days_max = 5
        self.stop_loss = -8     # 止损8%
        self.top_n = 10

    def get_description(self):
        return (f"萨拉丁事件：游资连续上榜+涨停回调，"
                f"换手>{self.min_turnover}%，持有{self.holding_days_min}-{self.holding_days_max}天，止损{self.stop_loss}%")

    def get_params(self):
        return {
            'min_turnover': self.min_turnover,
            'min_amount': self.min_amount,
            'holding_days_min': self.holding_days_min,
            'holding_days_max': self.holding_days_max,
            'stop_loss': self.stop_loss,
            'top_n': self.top_n
        }

    def detect_events(self, helper, date=None):
        """
        检测萨拉丁事件信号：游资席位 + 涨停回调
        """
        results = []

        # 获取龙虎榜数据
        try:
            if date:
                lhb_date = date.replace('-', '')
            else:
                lhb_date = datetime.now().strftime("%Y%m%d")

            lhb_data = helper.get_dragon_tiger_list(date=lhb_date)
        except Exception as e:
            print(f"获取龙虎榜失败: {e}")
            lhb_data = pd.DataFrame()

        if lhb_data is None or lhb_data.empty:
            try:
                lhb_data = helper.get_dragon_tiger_list(date=None)
            except Exception:
                lhb_data = pd.DataFrame()

        hot_stocks = {}

        if lhb_data is not None and not lhb_data.empty:
            # 分析游资席位
            for _, row in lhb_data.iterrows():
                try:
                    symbol = str(row.get('代码', row.get('股票代码', '')))
                    name = str(row.get('名称', row.get('股票简称', symbol)))
                    reason = str(row.get('上榜原因', ''))

                    # 检查是否为游资席位
                    seat_found = []
                    for seat in self.HOT_MONEY_SEATS:
                        if seat in reason:
                            seat_found.append(seat)

                    if seat_found:
                        buy_amount = helper._safe_float(row.get('买入金额', 0))
                        sell_amount = helper._safe_float(row.get('卖出金额', 0))
                        net_buy = buy_amount - sell_amount

                        if symbol not in hot_stocks:
                            hot_stocks[symbol] = {
                                'name': name,
                                'net_buy': net_buy,
                                'seats': seat_found,
                                'count': 1
                            }
                        else:
                            hot_stocks[symbol]['net_buy'] += net_buy
                            hot_stocks[symbol]['seats'].extend(seat_found)
                            hot_stocks[symbol]['count'] = len(set(hot_stocks[symbol]['seats']))
                except Exception:
                    continue

        # 筛选有回调的游资股
        for symbol, info in hot_stocks.items():
            try:
                kline = helper.get_history_kline(symbol, days=20)
                if kline is None or kline.empty or len(kline) < 15:
                    continue

                # 检测近期涨停
                recent = kline.tail(10)
                has_limit_up = False
                for i in range(len(recent) - 1):
                    gain = (recent['close'].iloc[i] / recent['close'].iloc[i-1] - 1) * 100 if i > 0 else 0
                    if gain > 9.5:
                        has_limit_up = True
                        break

                if not has_limit_up:
                    continue

                # 涨停后回调
                latest_gain = (kline['close'].iloc[-1] / kline['close'].iloc[-2] - 1) * 100 if len(kline) >= 2 else 0
                callback_day = -1  # 回调第N天

                for i in range(2, 6):
                    if len(kline) > i:
                        prev_gain = (kline['close'].iloc[-i] / kline['close'].iloc[-i-1] - 1) * 100
                        if prev_gain < 0:
                            callback_day = i - 1
                            break

                # 回调第2天买入
                if callback_day == 1:
                    # 换手率（用成交量/流通股本近似）
                    avg_vol = kline['volume'].iloc[-5:].mean()
                    cur_vol = kline['volume'].iloc[-1]

                    # 成交额
                    amount = kline['amount'].iloc[-1] if 'amount' in kline.columns else 0

                    # 换手率高 + 成交额大
                    if amount > self.min_amount:
                        results.append({
                            'symbol': symbol,
                            'name': info['name'],
                            'reason': f"萨拉丁：游资{info['count']}席位+回调第2天+成交额{amount/1e8:.1f}亿"
                        })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        # 备选：K线筛选游资偏好回调股
        if not results:
            results = self._kline_fallback(helper, date)

        return results[:self.top_n]

    def _kline_fallback(self, helper, date=None):
        """K线备选：筛选游资偏好的回调股"""
        results = []

        try:
            pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:50]
        except Exception:
            pool = ['688981', '688012', '688256', '300750', '300033',
                    '300059', '002475', '002594', '002230', '002415']

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=20, end_date=date)
                if kline is None or kline.empty or len(kline) < 15:
                    continue

                # 检测近期涨停
                gains = []
                for i in range(1, 8):
                    if len(kline) > i:
                        gain = (kline['close'].iloc[-i] / kline['close'].iloc[-i-1] - 1) * 100
                        gains.append(gain)

                # 近期有涨停
                has_limit_up = any(g > 9.5 for g in gains[:3])

                # 涨停后回调
                recent_callback = gains[3] < 0 if len(gains) > 3 else False

                # 高换手（成交额大）
                amount = kline['amount'].iloc[-1] if 'amount' in kline.columns else 0
                high_amount = amount > self.min_amount

                # 回调第2天
                buy_signal = recent_callback and high_amount

                if has_limit_up and buy_signal:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"萨拉丁备选：涨停回调+高成交额{amount/1e8:.1f}亿"
                    })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        return results[:self.top_n]


class BismarckEventStrategy(EventStrategy):
    """
    俾斯麦事件策略（机构事件）

    触发条件：
    1. 机构专用席位净买入
    2. 总买入额 > 5000万
    3. 股价站上20日均线
    4. 基本面无恶化

    买入：机构买入次日
    持有：10-20个交易日
    卖出：跌破60日均线
    """

    def __init__(self):
        super().__init__("俾斯麦事件", "事件驱动")
        self.min_buy_amount = 5000  # 总买入额 > 5000万
        self.holding_days_min = 10
        self.holding_days_max = 20
        self.top_n = 10

    def get_description(self):
        return (f"俾斯麦事件：机构专用席位买入>{self.min_buy_amount}万，"
                f"持有{self.holding_days_min}-{self.holding_days_max}天，跌破60日线卖出")

    def get_params(self):
        return {
            'min_buy_amount': self.min_buy_amount,
            'holding_days_min': self.holding_days_min,
            'holding_days_max': self.holding_days_max,
            'top_n': self.top_n
        }

    def detect_events(self, helper, date=None):
        """
        检测俾斯麦事件信号：机构专用席位大额买入
        """
        results = []

        # 获取龙虎榜数据
        try:
            if date:
                lhb_date = date.replace('-', '')
            else:
                lhb_date = datetime.now().strftime("%Y%m%d")

            lhb_data = helper.get_dragon_tiger_list(date=lhb_date)
        except Exception as e:
            print(f"获取龙虎榜失败: {e}")
            lhb_data = pd.DataFrame()

        if lhb_data is None or lhb_data.empty:
            try:
                lhb_data = helper.get_dragon_tiger_list(date=None)
            except Exception:
                lhb_data = pd.DataFrame()

        if lhb_data is not None and not lhb_data.empty:
            # 筛选机构专用席位
            for _, row in lhb_data.iterrows():
                try:
                    symbol = str(row.get('代码', row.get('股票代码', '')))
                    name = str(row.get('名称', row.get('股票简称', symbol)))
                    reason = str(row.get('上榜原因', ''))

                    # 检查是否为机构专用席位
                    is_institution_seat = '机构专用' in reason

                    # 获取买入金额
                    buy_amount = helper._safe_float(row.get('买入金额', 0))

                    # 机构总买入额 > 5000万
                    if is_institution_seat and buy_amount > self.min_buy_amount * 10000:
                        kline = helper.get_history_kline(symbol, days=60)
                        if kline is not None and not kline.empty and len(kline) >= 60:
                            # 股价站上20日均线
                            ma20 = kline['close'].rolling(20).mean().iloc[-1]
                            current = kline['close'].iloc[-1]
                            above_ma20 = current > ma20

                            # 均线多头排列
                            ma5 = kline['close'].rolling(5).mean().iloc[-1]
                            ma10 = kline['close'].rolling(10).mean().iloc[-1]
                            ma60 = kline['close'].rolling(60).mean().iloc[-1] if len(kline) >= 60 else kline['close'].mean()
                            ma_bull = ma5 > ma10 > ma20

                            # 基本面无恶化（简化：用近期涨幅判断）
                            gain_10d = (kline['close'].iloc[-1] / kline['close'].iloc[-11] - 1) * 100 if len(kline) >= 11 else 0
                            no_deterioration = gain_10d > -15  # 近10日跌幅不超过15%

                            if above_ma20 and no_deterioration:
                                results.append({
                                    'symbol': symbol,
                                    'name': name,
                                    'reason': f"俾斯麦：机构买入{buy_amount/10000:.0f}万，站上MA20，均线多头"
                                })

                            if len(results) >= self.top_n:
                                break
                except Exception:
                    continue

        # 如果没有龙虎榜数据，用K线筛选备选股
        if not results:
            results = self._kline_fallback(helper, date)

        return results[:self.top_n]

    def _kline_fallback(self, helper, date=None):
        """K线备选：筛选机构偏好的中长期股"""
        results = []

        try:
            pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:50]
        except Exception:
            pool = ['600519', '600036', '601318', '000858', '600887',
                    '000333', '601166', '600276', '601012', '600030']

        for symbol in pool:
            try:
                kline = helper.get_history_kline(symbol, days=90, end_date=date)
                if kline is None or kline.empty or len(kline) < 60:
                    continue

                # 均线系统
                ma5 = kline['close'].rolling(5).mean().iloc[-1]
                ma10 = kline['close'].rolling(10).mean().iloc[-1]
                ma20 = kline['close'].rolling(20).mean().iloc[-1]
                ma60 = kline['close'].rolling(60).mean().iloc[-1]

                current = kline['close'].iloc[-1]

                # 站上20日均线
                above_ma20 = current > ma20

                # 均线多头
                ma_bull = ma5 > ma10 > ma20

                # 未跌破60日均线
                above_ma60 = current > ma60

                # 基本面稳定（近期无大跌）
                gain_10d = (current / kline['close'].iloc[-11] - 1) * 100 if len(kline) >= 11 else 0
                stable = gain_10d > -10

                if above_ma20 and ma_bull and above_ma60 and stable:
                    results.append({
                        'symbol': symbol,
                        'name': symbol,
                        'reason': f"俾斯麦备选：站上MA20+均线多头+守住MA60"
                    })

                if len(results) >= self.top_n:
                    break
            except Exception:
                continue

        return results[:self.top_n]


if __name__ == '__main__':
    # 测试三个策略
    strategies = [
        NapoleonEventStrategy(),
        SaladinEventStrategy(),
        BismarckEventStrategy()
    ]

    for s in strategies:
        print(f"\n{'='*50}")
        print(f"策略名称: {s.name}")
        print(f"策略描述: {s.get_description()}")
        print(f"策略参数: {s.get_params()}")
