# -*- coding: utf-8 -*-
"""
Baostock数据封装模块
免费数据源，无需token
提供A股历史K线、股票列表、交易日等数据
"""

import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import time

class BaostockHelper:
    """Baostock数据助手 - 免费数据源"""

    def __init__(self, cache_dir="data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._logged_in = False
        self._kline_cache = {}  # K线缓存
        self._last_call_time = 0
        self._min_interval = 0.2  # 最小调用间隔（秒）
        self._login()

    def _login(self):
        """登录baostock"""
        try:
            result = bs.login()
            if result.error_code == '0':
                self._logged_in = True
            else:
                print(f"[Baostock] 登录失败: {result.error_msg}")
        except Exception as e:
            print(f"[Baostock] 登录异常: {e}")
            self._logged_in = False

    def _logout(self):
        """登出baostock"""
        if self._logged_in:
            try:
                bs.logout()
            except:
                pass
            self._logged_in = False

    def _ensure_login(self):
        """确保已登录"""
        if not self._logged_in:
            self._login()

    def _rate_limit(self):
        """速率限制"""
        current_time = time.time()
        elapsed = current_time - self._last_call_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call_time = time.time()

    def _get_cache(self, key, days=1):
        """读取缓存"""
        cache_file = os.path.join(self.cache_dir, f"bs_{key}.json")
        if os.path.exists(cache_file):
            file_time = os.path.getmtime(cache_file)
            if (datetime.now().timestamp() - file_time) < days * 86400:
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except:
                    pass
        return None

    def _set_cache(self, key, data):
        """写入缓存"""
        cache_file = os.path.join(self.cache_dir, f"bs_{key}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def _normalize_code(self, symbol):
        """标准化股票代码为baostock格式 (sh.600000 / sz.000001)"""
        # 移除已有的前缀
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        code = code.replace('sh', '').replace('sz', '').replace('bj', '')

        if code.startswith('6') or code.startswith('9') or code.startswith('5'):
            return f"sh.{code}"
        else:
            return f"sz.{code}"

    def _convert_to_standard_code(self, baostock_code):
        """将baostock代码转换为标准代码 (600000.SH / 000001.SZ)"""
        if not baostock_code:
            return ""
        code = baostock_code.lower().replace('sh.', '').replace('sz.', '')
        if code.startswith('6') or code.startswith('9') or code.startswith('5'):
            return f"{code}.SH"
        else:
            return f"{code}.SZ"

    # ==================== 股票列表 ====================

    def get_stock_list(self):
        """获取A股股票列表"""
        cache = self._get_cache("stock_list", days=7)
        if cache:
            return cache

        self._ensure_login()
        stocks = []

        try:
            # 获取上海股票列表
            rs = bs.query_all_stock(day=datetime.now().strftime('%Y-%m-%d'))
            if rs.error_code == '0':
                while rs.next():
                    row = rs.get_row_data()
                    code = row[0]  # 如 'sh.600000'
                    name = row[1]  # 如 '浦发银行'
                    code_str = code.lower().replace('sh.', '').replace('sz.', '')

                    if code_str.startswith('6') or code_str.startswith('9') or code_str.startswith('5'):
                        standard_code = f"{code_str}.SH"
                    else:
                        standard_code = f"{code_str}.SZ"

                    stocks.append({
                        'symbol': standard_code,
                        'name': name,
                        'code': code,
                    })

            self._set_cache("stock_list", stocks)
            return stocks
        except Exception as e:
            print(f"[Baostock]获取股票列表失败: {e}")
        return stocks

    # ==================== K线数据 ====================

    def get_history_kline(self, symbol, days=60, end_date=None):
        """获取历史K线（日线，前复权）
        symbol: 6位股票代码，如 '600000' 或 '600000.SH'
        返回: DataFrame，包含 date, open, high, low, close, volume
        """
        # 检查缓存
        cache_key = f"{symbol}_{days}_{end_date}"
        if cache_key in self._kline_cache:
            return self._kline_cache[cache_key]

        self._ensure_login()
        self._rate_limit()

        # 转换symbol格式
        bs_code = self._normalize_code(symbol)

        # 计算日期范围
        if end_date:
            if isinstance(end_date, str) and '-' in end_date:
                end_date = end_date.replace('-', '')
            end_dt = datetime.strptime(end_date, '%Y%m%d')
        else:
            end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days * 2)

        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = end_dt.strftime('%Y-%m-%d')

        try:
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount,turn",
                start_date=start_str,
                end_date=end_str,
                frequency="daily",
                adjustflag="2"  # 前复权
            )

            if rs.error_code == '0' and rs is not None:
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())

                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    # 转换数据类型
                    for col in ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn']:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    # 统一列名
                    if 'date' in df.columns:
                        df['date'] = df['date'].astype(str)
                    # 缓存结果
                    self._kline_cache[cache_key] = df
                    return df
        except Exception as e:
            print(f"[Baostock]获取K线失败 {symbol}: {e}")

        return pd.DataFrame()

    def get_batch_kline(self, symbols, days=60, end_date=None):
        """批量获取多个股票的K线

        Args:
            symbols: 股票代码列表
            days: 获取天数
            end_date: 结束日期

        Returns:
            dict: {symbol: DataFrame}
        """
        results = {}

        for sym in symbols:
            cache_key = f"{sym}_{days}_{end_date}"
            if cache_key in self._kline_cache:
                results[sym] = self._kline_cache[cache_key]
            else:
                df = self.get_history_kline(sym, days, end_date)
                results[sym] = df
                time.sleep(0.1)  # 避免请求过快

        return results

    # ==================== 实时行情 ====================

    def get_realtime_quote(self, symbols):
        """获取实时行情（单只或多只股票）
        注意: baostock免费版实时行情数据有限
        """
        if not symbols:
            return pd.DataFrame()

        self._ensure_login()

        if isinstance(symbols, str):
            symbols = [symbols]

        results = []
        for sym in symbols[:10]:  # 限制单次查询数量
            bs_code = self._normalize_code(sym)
            try:
                rs = bs.query_trade_data(
                    bs_code,
                    start_date=datetime.now().strftime('%Y-%m-%d'),
                    end_date=datetime.now().strftime('%Y-%m-%d')
                )
                if rs.error_code == '0':
                    while rs.next():
                        row = rs.get_row_data()
                        results.append({
                            'symbol': sym,
                            'date': row[0],
                            'open': float(row[1]) if row[1] else 0,
                            'high': float(row[2]) if row[2] else 0,
                            'low': float(row[3]) if row[3] else 0,
                            'close': float(row[4]) if row[4] else 0,
                            'volume': float(row[5]) if row[5] else 0,
                        })
            except Exception as e:
                print(f"[Baostock]获取实时行情失败 {sym}: {e}")
            time.sleep(0.1)

        if results:
            return pd.DataFrame(results)
        return pd.DataFrame()

    # ==================== 交易日 ====================

    def get_trade_dates(self, days=30, start_date=None):
        """获取最近交易日列表（升序排列）
        注意: baostock本身不提供直接的交易日期查询，通过K线数据获取
        """
        if start_date:
            # 从指定日期开始计算
            try:
                start_dt = datetime.strptime(start_date, '%Y%m%d')
            except:
                start_dt = datetime.now() - timedelta(days=730)
        else:
            start_dt = datetime.now() - timedelta(days=730)

        end_dt = datetime.now()
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = end_dt.strftime('%Y-%m-%d')

        cache_key = f"trade_dates_{start_str}_{end_str}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            if start_date:
                # 从缓存中筛选
                dates = [d for d in cache if d >= str(start_date)]
                return dates[-days:] if len(dates) >= days else dates
            return cache[-days:] if len(cache) >= days else cache

        # 使用沪深300指数K线获取交易日
        self._ensure_login()
        self._rate_limit()

        try:
            rs = bs.query_history_k_data_plus(
                "sh.000300",
                "date",
                start_date=start_str,
                end_date=end_str,
                frequency="daily"
            )

            if rs.error_code == '0':
                dates = []
                while rs.next():
                    row = rs.get_row_data()
                    if row[0]:
                        dates.append(row[0])

                if dates:
                    dates.sort()  # 升序
                    self._set_cache(cache_key, dates)
                    if start_date:
                        dates = [d for d in dates if d >= str(start_date)]
                    return dates[-days:] if len(dates) >= days else dates
        except Exception as e:
            print(f"[Baostock]获取交易日失败: {e}")

        return []

    def get_trading_dates(self, n=60, end_date=None):
        """获取过去n个交易日列表（别名方法，兼容akshare）
        返回: ['2026-06-01', '2026-06-02', ...] YYYY-MM-DD格式
        """
        dates = self.get_trade_dates(days=n, start_date=None)
        # 转换为 YYYY-MM-DD 格式（如果还不是）
        return [d if '-' in str(d) else f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in dates]

    # ==================== 股票池 ====================

    def get_stock_pool(self, pool_type='hs300', sorted_by_market_value=False):
        """获取股票池（沪深300、中证500等）
        注意: baostock不提供指数成分股权威数据，使用K线近似获取
        """
        cache_key = f"pool_{pool_type}"
        cache = self._get_cache(cache_key, days=7)
        if cache:
            return cache

        self._ensure_login()

        # 使用沪深300指数成分股的近似列表
        # baostock免费版不提供成分股权威数据，返回常用的成分股
        if pool_type == 'hs300':
            # 常见沪深300大盘股
            pool = [
                '600519', '000858', '600036', '601318', '000333',
                '600276', '300750', '601012', '600900', '000651',
                '600887', '002475', '000568', '600030', '601166',
                '600050', '000001', '601398', '601288', '600000',
                '601088', '601857', '600028', '601012', '600690',
                '601328', '601601', '601668', '601186', '601766',
                '601988', '601628', '600104', '600309', '600585',
                '601111', '601919', '601818', '601336', '600837',
                '600999', '601888', '601800', '601229', '601198',
                '600918', '601066', '601688', '600588', '002142',
                '002415', '002460', '002594', '002230', '000725',
                '000333', '000338', '000002', '000100', '000651',
            ]
        elif pool_type == 'zz500':
            pool = [
                '600521', '300122', '002371', '002049', '600535',
                '600487', '002236', '002044', '300015', '300059',
                '002252', '300124', '300408', '300012', '002410',
                '002353', '002601', '300223', '002812', '300725',
                '300759', '300785', '300896', '300888', '300999',
            ]
        elif pool_type == 'sz50':
            pool = [
                '600519', '600036', '601318', '600000', '600016',
                '601398', '601288', '601988', '601328', '601166',
                '601012', '600030', '601601', '601088', '601857',
                '600028', '601628', '601186', '601766', '601668',
            ]
        else:
            # 全市场：返回所有股票代码
            all_stocks = self.get_stock_list()
            pool = [s.get('symbol', '').replace('.SH', '').replace('.SZ', '') for s in all_stocks[:500]]

        self._set_cache(cache_key, pool)
        return pool

    # ==================== 财务数据 ====================

    def get_financial_data(self, symbol):
        """获取财务数据（简化版）"""
        return self.get_financial_indicator(symbol)

    def get_financial_indicator(self, symbol):
        """获取财务指标
        baostock免费版提供部分财务数据
        """
        cache_key = f"fin_ind_{symbol}"
        cache = self._get_cache(cache_key, days=30)
        if cache:
            return cache

        self._ensure_login()
        bs_code = self._normalize_code(symbol)

        try:
            # 获取杜邦数据
            rs = bs.query_dupont_data(bs_code, start_date='2020-01-01', end_date=datetime.now().strftime('%Y-%m-%d'))
            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                if data_list and len(data_list) > 0:
                    latest = data_list[-1]
                    # baostock杜邦数据列: statDate, roeAvg, npMargin, assetTurnover, financialLeverage
                    data = {
                        'roe': float(latest[1]) if latest[1] else 0,  # roeAvg
                        'net_margin': float(latest[2]) if latest[2] else 0,  # npMargin
                        'asset_turnover': float(latest[3]) if latest[3] else 0,  # assetTurnover
                        'financial_leverage': float(latest[4]) if latest[4] else 0,  # financialLeverage
                    }
                    self._set_cache(cache_key, data)
                    return data
        except Exception as e:
            print(f"[Baostock]获取财务指标失败 {symbol}: {e}")

        return {}

    def get_growth_data(self, symbol):
        """获取成长数据（营收增速、净利润增速）"""
        cache_key = f"growth_{symbol}"
        cache = self._get_cache(cache_key, days=30)
        if cache:
            return cache

        self._ensure_login()
        bs_code = self._normalize_code(symbol)

        try:
            rs = bs.query_profit_data(bs_code, start_date='2020-01-01', end_date=datetime.now().strftime('%Y-%m-%d'))
            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                if data_list and len(data_list) >= 2:
                    current = data_list[-1]
                    prev = data_list[-2]
                    # 计算增速
                    if prev[4] and float(prev[4]) != 0:  # 净利润
                        profit_growth = (float(current[4]) - float(prev[4])) / abs(float(prev[4])) * 100
                    else:
                        profit_growth = 0
                    if prev[3] and float(prev[3]) != 0:  # 营业收入
                        revenue_growth = (float(current[3]) - float(prev[3])) / abs(float(prev[3])) * 100
                    else:
                        revenue_growth = 0
                    data = {
                        'profit_growth': profit_growth,
                        'revenue_growth': revenue_growth,
                    }
                    self._set_cache(cache_key, data)
                    return data
        except Exception as e:
            print(f"[Baostock]获取成长数据失败 {symbol}: {e}")

        return {}

    # ==================== 估值数据 ====================

    def get_valuation_data(self, symbol):
        """获取估值数据（PE、PB等）
        baostock提供市盈率、市净率等指标
        """
        cache_key = f"val_{symbol}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return cache

        self._ensure_login()
        bs_code = self._normalize_code(symbol)

        try:
            rs = bs.query_valuation_data(bs_code, start_date='2020-01-01', end_date=datetime.now().strftime('%Y-%m-%d'))
            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                if data_list and len(data_list) > 0:
                    latest = data_list[-1]
                    # 格式: date, code, pe, pb, ps, pcf, market_cap, circ_market_cap
                    data = {
                        'pe': float(latest[2]) if latest[2] else 0,
                        'pb': float(latest[3]) if latest[3] else 0,
                        'ps': float(latest[4]) if latest[4] else 0,
                        'total_mv': float(latest[6]) if latest[6] else 0,
                    }
                    self._set_cache(cache_key, data)
                    return data
        except Exception as e:
            print(f"[Baostock]获取估值数据失败 {symbol}: {e}")

        return {}

    # ==================== 指数数据 ====================

    def get_index_data(self, symbol="000300", days=60):
        """获取指数历史数据"""
        cache_key = f"idx_{symbol}_{days}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)

        self._ensure_login()
        self._rate_limit()

        # 转换指数代码
        if symbol.startswith('000') or symbol.startswith('399'):
            idx_code = f"sh.{symbol}"
        else:
            idx_code = f"sz.{symbol}"

        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y-%m-%d')

        try:
            rs = bs.query_history_k_data_plus(
                idx_code,
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="daily"
            )

            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                if data_list:
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    df['date'] = df['date'].astype(str)
                    self._set_cache(cache_key, df.to_dict('records'))
                    return df
        except Exception as e:
            print(f"[Baostock]获取指数数据失败 {symbol}: {e}")

        return pd.DataFrame()

    # ==================== 工具方法 ====================

    def is_trading_day(self, date=None):
        """检查是否交易日"""
        if not date:
            date = datetime.now().strftime('%Y%m%d')
        else:
            date = str(date).replace('-', '')

        dates = self.get_trade_dates(days=1, start_date=date)
        return len(dates) > 0 and dates[0].replace('-', '') == date

    def __del__(self):
        """析构时登出"""
        self._logout()


if __name__ == "__main__":
    helper = BaostockHelper()
    print("=== Baostock 测试 ===")

    # 测试股票列表
    stocks = helper.get_stock_list()
    print(f"股票列表: {len(stocks)} 只")

    # 测试K线
    df = helper.get_history_kline('600000', days=10)
    print(f"K线数据: {len(df)} 条")

    # 测试交易日
    dates = helper.get_trade_dates(days=5)
    print(f"交易日: {dates}")

    # 测试估值
    val = helper.get_valuation_data('600000')
    print(f"估值数据: {val}")

    # 测试财务指标
    fin = helper.get_financial_indicator('600000')
    print(f"财务指标: {fin}")
