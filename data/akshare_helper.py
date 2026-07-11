# -*- coding: utf-8 -*-
"""
AKShare数据封装模块
提供A股行情、财务数据、估值数据、资金流、事件数据等
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import time

class AKShareHelper:
    """AKShare数据助手"""

    def __init__(self, cache_dir="data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._hs300_cache = None

    def _get_cache(self, key, days=1):
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_file):
            file_time = os.path.getmtime(cache_file)
            if (datetime.now().timestamp() - file_time) < days * 86400:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        return None

    def _set_cache(self, key, data):
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # ==================== 基础行情 ====================

    def get_stock_list(self):
        """获取A股股票列表"""
        cache = self._get_cache("stock_list", days=7)
        if cache:
            return cache
        try:
            df = ak.stock_info_a_code_name()
            stocks = df.to_dict('records')
            self._set_cache("stock_list", stocks)
            return stocks
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            return []

    def get_realtime_quote(self, symbol):
        """获取实时行情"""
        try:
            df = ak.stock_zh_a_spot_em()
            stock = df[df['代码'] == symbol]
            if not stock.empty:
                return stock.iloc[0].to_dict()
        except Exception as e:
            print(f"获取实时行情失败 {symbol}: {e}")
        return None

    def get_etf_history_kline(self, symbol, period="daily", days=60, end_date=None):
        """获取ETF历史K线
        symbol: ETF代码，如 '510300' / '159915'
        end_date: 指定结束日期(YYYYMMDD字符串或YYYY-MM-DD)，None=今天
        使用东方财富ETF接口 fund_etf_hist_em
        """
        # 统一end_date格式为YYYYMMDD
        if end_date and isinstance(end_date, str) and '-' in end_date:
            end_date = end_date.replace('-', '')
        cache_key = f"etf_kline_{symbol}_{period}_{days}_{end_date or 'now'}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        actual_end = end_date or datetime.now().strftime("%Y%m%d")
        actual_start = (datetime.strptime(actual_end, "%Y%m%d") - timedelta(days=days*2)).strftime("%Y%m%d")
        
        try:
            df = ak.fund_etf_hist_em(symbol=symbol, period=period,
                                      start_date=actual_start, end_date=actual_end)
            if df is not None and not df.empty:
                df = df.tail(days)
                col_map = {
                    '日期': 'date', '开盘': 'open', '收盘': 'close',
                    '最高': 'high', '最低': 'low', '成交量': 'volume',
                    '成交额': 'amount', '振幅': 'amplitude'
                }
                df = df.rename(columns=col_map)
                if 'date' not in df.columns and '日期' not in df.columns:
                    # 尝试自动检测日期列
                    for col in df.columns:
                        if 'date' in col.lower() or '日期' in col:
                            df = df.rename(columns={col: 'date'})
                            break
                df['date'] = df['date'].astype(str)
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"ETF历史K线获取失败 {symbol}: {e}")
        return pd.DataFrame()

    def get_history_kline(self, symbol, period="daily", days=60, end_date=None):
        """获取历史K线（前复权）
        symbol: 6位股票代码，如 '000001' / '600000'
        end_date: 指定结束日期(YYYYMMDD字符串或YYYY-MM-DD)，None=今天
        优先用新浪源 stock_zh_a_daily（稳定），降级用东方财富 stock_zh_a_hist
        """
        # 统一end_date格式为YYYYMMDD
        if end_date and isinstance(end_date, str) and '-' in end_date:
            end_date = end_date.replace('-', '')
        cache_key = f"kline_{symbol}_{period}_{days}_{end_date or 'now'}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        actual_end = end_date or datetime.now().strftime("%Y%m%d")
        actual_start = (datetime.strptime(actual_end, "%Y%m%d") - timedelta(days=days*2)).strftime("%Y%m%d")

        # 方案1: 新浪源 stock_zh_a_daily（稳定，需要sz/sh前缀）
        try:
            # 转换symbol为新浪格式：6开头=sh，其余=sz
            prefix = 'sh' if symbol.startswith('6') else 'sz'
            sina_symbol = f"{prefix}{symbol}"
            df = ak.stock_zh_a_daily(symbol=sina_symbol, start_date=actual_start,
                                      end_date=actual_end, adjust="qfq")
            if df is not None and not df.empty:
                df = df.tail(days)
                # 自动检测并标准化日期列
                date_col = None
                for col in df.columns:
                    if 'date' in col.lower() or '日期' in col:
                        date_col = col
                        break
                if date_col:
                    df = df.rename(columns={date_col: 'date'})
                
                # 标准化列名
                keep_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
                existing_cols = [c for c in keep_cols if c in df.columns]
                df = df[existing_cols]
                
                if 'date' in df.columns:
                    df['date'] = df['date'].astype(str)
                
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"新浪源K线失败 {symbol}: {e}")

        # 方案2: 东方财富源 stock_zh_a_hist（降级）- 带重试
        max_retries = 3
        for attempt in range(max_retries):
            try:
                df = ak.stock_zh_a_hist(symbol=symbol, period=period,
                                        start_date=actual_start, end_date=actual_end, adjust="qfq")
                if df is not None and not df.empty:
                    df = df.tail(days)
                    col_map = {
                        '日期': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume',
                        '成交额': 'amount', '振幅': 'amplitude'
                    }
                    df = df.rename(columns=col_map)
                    self._set_cache(cache_key, df.to_dict('records'))
                    return df
                break
            except Exception as e:
                error_str = str(e)
                is_connection_error = any(x in error_str for x in [
                    'RemoteDisconnected', 'Connection aborted', 'ConnectionReset',
                    'ConnectionRefused', 'timed out', 'ReadTimeout'
                ])
                if is_connection_error and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"东财K线连接失败 {symbol}，{wait_time}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"东方财富源K线失败 {symbol}: {e}")
                    break
        
        return pd.DataFrame()

    def get_trading_dates(self, n=60, end_date=None):
        """获取过去n个交易日列表
        优先用新浪交易日历（稳定），降级用沪深300指数K线
        返回: ['2026-06-01', '2026-06-02', ...] YYYY-MM-DD格式
        """
        # 确定截止日期：默认今天
        if end_date:
            end_norm = end_date.replace('-', '') if '-' in end_date else end_date
        else:
            end_norm = datetime.now().strftime("%Y%m%d")

        # 优先方案：新浪交易日历
        try:
            cache_key = f"trade_dates_sina"
            cache = self._get_cache(cache_key, days=1)
            if cache:
                all_dates = cache
            else:
                df = ak.tool_trade_date_hist_sina()
                all_dates = df['trade_date'].astype(str).tolist()
                self._set_cache(cache_key, all_dates)
            # 过滤 <= end_norm（排除未来日期），取最后n个
            all_dates = [d for d in all_dates if d.replace('-', '') <= end_norm]
            dates = all_dates[-n:] if len(all_dates) >= n else all_dates
            # 统一为YYYY-MM-DD格式
            return [d if '-' in d else f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in dates]
        except Exception as e:
            print(f"新浪交易日历获取失败: {e}，降级用沪深300指数K线")

        # 降级方案：用沪深300指数K线（stock_zh_index_daily）
        try:
            df = ak.stock_zh_index_daily(symbol='sh000300')
            if df is not None and not df.empty:
                df['date'] = df['date'].astype(str)
                df = df[df['date'].str.replace('-', '') <= end_norm]
                dates = df['date'].tolist()[-n:]
                return dates
        except Exception as e:
            print(f"沪深300指数K线失败: {e}")
        return []

    def get_stock_pool(self, pool="hs300", sorted_by_market_value=False):
        """获取股票池（默认沪深300）

        Args:
            pool: 指数池 hs300/zz500/sz50
            sorted_by_market_value: True=按市值降序（用实时行情spot_em补充市值）
        """
        cache_key = f"pool_{pool}_mv{int(sorted_by_market_value)}"
        cache = self._get_cache(cache_key, days=7)
        if cache:
            return cache
        try:
            if pool == "hs300":
                df = ak.index_stock_cons_csindex(symbol="000300")
            elif pool == "zz500":
                df = ak.index_stock_cons_csindex(symbol="000905")
            elif pool == "sz50":
                df = ak.index_stock_cons_csindex(symbol="000016")
            else:
                df = ak.index_stock_cons_csindex(symbol="000300")

            if df is not None and not df.empty:
                # 统一成分股代码格式
                if '成分券代码' in df.columns:
                    stocks = df['成分券代码'].tolist()
                elif '代码' in df.columns:
                    stocks = df['代码'].tolist()
                else:
                    stocks = df.iloc[:, 0].tolist()

                # 按市值降序排序（抽样时取大盘股而非代码最小的）
                if sorted_by_market_value and stocks:
                    try:
                        spot = ak.stock_zh_a_spot_em()
                        spot = spot[spot['代码'].isin(stocks)]
                        if '总市值' in spot.columns:
                            spot = spot.sort_values('总市值', ascending=False)
                            stocks = spot['代码'].tolist()
                    except Exception as e:
                        print(f"按市值排序失败，降级用原顺序: {e}")

                self._set_cache(cache_key, stocks)
                return stocks
        except Exception as e:
            print(f"获取股票池失败: {e}")
        # 降级：返回常见大盘股
        return ['600519', '000858', '600036', '601318', '000333',
                '600276', '300750', '601012', '600900', '000651']

    # ==================== 财务指标 ====================

    def get_financial_indicator(self, symbol):
        """获取财务指标：ROE、ROIC、资产负债率、现金流等
        优先用 stock_financial_abstract_ths（新版可用），降级用东方财富接口
        """
        cache_key = f"fin_ind_{symbol}"
        cache = self._get_cache(cache_key, days=30)
        if cache:
            return cache
        
        def safe_pct(v):
            """处理百分比字符串"""
            if isinstance(v, str) and '%' in v:
                return self._safe_float(v.replace('%', ''), 0) / 100
            return self._safe_float(v, 0)
        
        try:
            # 方案1: 同花顺财务摘要（稳定可用）
            # 数据按时间升序，最新数据在最后一行
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
            if df is not None and not df.empty:
                latest = df.iloc[-1].to_dict()  # 取最新一期数据
                
                # 同花顺财务摘要的ROE列名可能是不同的，需要尝试多种列名
                # 可能列名：'净资产收益率', '净资产收益率-加权', '净资产收益率-摊薄'
                roe_value = 0
                roe_cols = ['净资产收益率-加权', '净资产收益率-摊薄', '净资产收益率', 'ROE(%)']
                for col in roe_cols:
                    if col in latest and latest[col] is not None:
                        roe_value = safe_pct(latest.get(col, 0))
                        break
                
                data = {
                    'roe': roe_value,
                    'roic': 0,  # ths数据不含ROIC
                    'debt_ratio': safe_pct(latest.get('资产负债率', 0)),
                    'current_ratio': self._safe_float(latest.get('流动比率', 0)),
                    'gross_margin': 0,  # ths数据不含毛利率
                    'net_margin': safe_pct(latest.get('销售净利率', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"同花顺财务指标失败 {symbol}: {e}")

        # 方案2: 东方财富财务分析指标（降级）
        try:
            df = ak.stock_financial_analysis_indicator_em(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[0].to_dict()
                data = {
                    'roe': safe_pct(latest.get('净资产收益率(%)', 0)),
                    'roic': safe_pct(latest.get('投入资本回报率(%)', 0)),
                    'debt_ratio': safe_pct(latest.get('资产负债率(%)', 0)),
                    'current_ratio': self._safe_float(latest.get('流动比率', 0)),
                    'gross_margin': safe_pct(latest.get('销售毛利率(%)', 0)),
                    'net_margin': safe_pct(latest.get('销售净利率(%)', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"东方财富财务指标失败 {symbol}: {e}")
        return {}

    def get_valuation_data(self, symbol):
        """获取估值数据：PE、PB、PS、股息率
        优先使用Tushare（稳定可靠），降级用akshare东财/新浪/同花顺
        """
        cache_key = f"val_{symbol}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return cache
        
        # 方案1: Tushare（最稳定）
        try:
            from .tushare_helper import TushareHelper
            ts_helper = TushareHelper()
            ts_data = ts_helper.get_valuation_data(symbol)
            if ts_data and ts_data.get('pe') and ts_data.get('pb'):
                data = {
                    'pe': float(ts_data.get('pe', 0)),
                    'pe_ttm': float(ts_data.get('pe', 0)),
                    'pb': float(ts_data.get('pb', 0)),
                    'ps': float(ts_data.get('ps', 0)),
                    'ps_ttm': float(ts_data.get('ps', 0)),
                    'dv_ratio': float(ts_data.get('dv_ratio', 0)),
                    'dv_ttm': float(ts_data.get('dv_ratio', 0)),
                    'total_mv': float(ts_data.get('total_mv', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"[Tushare]估值获取失败 {symbol}: {e}，降级到akshare")

        # 方案2: 东财实时行情（包含PE/PB/总市值）- 带重试
        max_retries = 3
        for attempt in range(max_retries):
            try:
                df = ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    stock = df[df['代码'] == symbol]
                    if not stock.empty:
                        row = stock.iloc[0]
                        data = {
                            'pe': self._safe_float(row.get('市盈率-动态', 0)),
                            'pe_ttm': self._safe_float(row.get('市盈率-动态', 0)),
                            'pb': self._safe_float(row.get('市净率', 0)),
                            'ps': self._safe_float(row.get('市销率', 0)),
                            'ps_ttm': self._safe_float(row.get('市销率TTM', 0)),
                            'dv_ratio': self._safe_float(row.get('股息率', 0)),
                            'dv_ttm': self._safe_float(row.get('股息率TTM', 0)),
                            'total_mv': self._safe_float(row.get('总市值', 0)),
                        }
                        self._set_cache(cache_key, data)
                        return data
                break
            except Exception as e:
                error_str = str(e)
                is_connection_error = any(x in error_str for x in [
                    'RemoteDisconnected', 'Connection aborted', 'ConnectionReset',
                    'ConnectionRefused', 'timed out', 'ReadTimeout'
                ])
                if is_connection_error and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"东财实时行情连接失败 {symbol}，{wait_time}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"东财实时行情估值失败 {symbol}: {e}")
                    break

        # 方案3: 新浪实时行情
        for attempt in range(max_retries):
            try:
                sina_symbol = f"sz{symbol}" if not symbol.startswith('6') else f"sh{symbol}"
                spot_df = ak.stock_zh_a_spot()
                if spot_df is not None and not spot_df.empty:
                    stock_spot = spot_df[spot_df['代码'] == sina_symbol]
                    if not stock_spot.empty:
                        row = stock_spot.iloc[0]
                        data = {
                            'pe': self._safe_float(row.get('市盈率-动态', 0)),
                            'pe_ttm': self._safe_float(row.get('市盈率-动态', 0)),
                            'pb': self._safe_float(row.get('市净率', 0)),
                            'ps': self._safe_float(row.get('市销率', 0)),
                            'ps_ttm': self._safe_float(row.get('市销率TTM', 0)),
                            'dv_ratio': self._safe_float(row.get('股息率', 0)),
                            'dv_ttm': self._safe_float(row.get('股息率TTM', 0)),
                            'total_mv': self._safe_float(row.get('总市值', 0)),
                        }
                        self._set_cache(cache_key, data)
                        return data
                break
            except Exception as e:
                error_str = str(e)
                is_connection_error = any(x in error_str for x in [
                    'RemoteDisconnected', 'Connection aborted', 'ConnectionReset',
                    'ConnectionRefused', 'timed out', 'ReadTimeout'
                ])
                if is_connection_error and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"新浪实时行情连接失败 {symbol}，{wait_time}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"新浪实时行情估值失败 {symbol}: {e}")
                    break

        # 方案4: 同花顺财务数据+历史K线
        try:
            fin_df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
            if fin_df is not None and not fin_df.empty:
                latest_fin = fin_df.iloc[-1].to_dict()
                kline = self.get_history_kline(symbol, days=5)
                if not kline.empty:
                    price = float(kline.iloc[-1].get('close', 0))
                    eps = self._safe_float(latest_fin.get('基本每股收益', 0))
                    book_per_share = self._safe_float(latest_fin.get('每股净资产', 0))
                    pe = price / eps if eps and eps > 0 else 0
                    pb = price / book_per_share if book_per_share and book_per_share > 0 else 0
                    data = {
                        'pe': pe,
                        'pe_ttm': pe,
                        'pb': pb,
                        'ps': 0,
                        'ps_ttm': 0,
                        'dv_ratio': 0,
                        'dv_ttm': 0,
                        'total_mv': 0,
                    }
                    self._set_cache(cache_key, data)
                    return data
        except Exception as e:
            print(f"同花顺+历史K线估值计算失败 {symbol}: {e}")
        return {}

    def get_growth_data(self, symbol):
        """获取成长数据：净利润增速、营收增速"""
        cache_key = f"growth_{symbol}"
        cache = self._get_cache(cache_key, days=30)
        if cache:
            return cache
        try:
            # 同花顺财务摘要（稳定可用）
            # 数据按时间升序，最新数据在最后一行
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
            if df is not None and not df.empty:
                latest = df.iloc[-1].to_dict()  # 取最新一期数据
                data = {
                    'profit_growth': self._safe_float(latest.get('净利润同比增长率', 0)),
                    'revenue_growth': self._safe_float(latest.get('营业总收入同比增长率', 0)),
                    'profit_yoy': self._safe_float(latest.get('净利润同比增长率', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取成长数据失败 {symbol}: {e}")
        return {}

    def get_cash_flow(self, symbol):
        """获取现金流数据
        优先用同花顺财务摘要（含每股经营现金流），降级用占位返回
        """
        cache_key = f"cashflow_{symbol}"
        cache = self._get_cache(cache_key, days=30)
        if cache:
            return cache
        try:
            # 方案1: 同花顺财务摘要（稳定可用，含每股经营现金流）
            # 数据按时间升序，最新数据在最后一行
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
            if df is not None and not df.empty:
                latest = df.iloc[-1].to_dict()  # 取最新一期数据
                op_cf_per_share = self._safe_float(latest.get('每股经营现金流', 0))
                net_profit = self._safe_float(latest.get('净利润', 0))
                eps = self._safe_float(latest.get('基本每股收益', 0))
                data = {
                    'operating_cf': op_cf_per_share * 1e8,  # 估算全公司经营现金流
                    'net_profit': net_profit,
                }
                # 现金流质量 = 每股经营现金流 / 每股收益
                if eps and eps != 0:
                    data['cf_quality'] = op_cf_per_share / eps
                else:
                    data['cf_quality'] = 0
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"同花顺现金流失败 {symbol}: {e}")

        # 方案2: 东财现金流报表（降级）
        try:
            df = ak.stock_cash_flow_sheet_by_quarterly_em(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[0].to_dict()
                data = {
                    'operating_cf': self._safe_float(latest.get('经营活动产生的现金流量净额', 0)),
                    'net_profit': self._safe_float(latest.get('净利润', 0)),
                }
                if data['net_profit'] and data['net_profit'] != 0:
                    data['cf_quality'] = data['operating_cf'] / data['net_profit']
                else:
                    data['cf_quality'] = 0
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"东财现金流失败 {symbol}: {e}")
        return {}

    # ==================== 资金流数据 ====================

    def get_north_holding(self, symbol):
        """获取个股北向资金持股比例
        使用 stock_hsgt_individual_em（稳定可用）
        """
        cache_key = f"north_{symbol}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return cache
        try:
            df = ak.stock_hsgt_individual_em(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[-1].to_dict()
                data = {
                    'hold_ratio': self._safe_float(latest.get('持股数量占A股百分比', 0)),
                    'hold_market_value': self._safe_float(latest.get('持股市值', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取北向持股失败 {symbol}: {e}")
        return {}

    def get_north_flow(self):
        """获取北向资金整体流向"""
        cache = self._get_cache("north_flow", days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_hsgt_hist_em(symbol="北向资金")
            if df is not None and not df.empty:
                df = df.tail(30)
                self._set_cache("north_flow", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取北向资金失败: {e}")
        return pd.DataFrame()

    # ==================== 南向资金数据 ====================

    def get_south_flow(self):
        """获取南向资金（港股通）历史流向数据
        返回: DataFrame，包含日期、净买入额等
        """
        cache = self._get_cache("south_flow", days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            # 方案1: 东财港股通历史流向
            df = ak.stock_hsgt_hsgt_list_em(symbol="南向资金")
            if df is not None and not df.empty:
                df = df.tail(30)
                self._set_cache("south_flow", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"东财南向资金流向失败: {e}")
        
        try:
            # 方案2: 港股通历史数据
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪股通")
            if df is not None and not df.empty:
                df = df.tail(30)
                self._set_cache("south_flow", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"南向资金流向失败: {e}")
        return pd.DataFrame()

    def get_south_holdings(self):
        """获取南向资金重仓股
        返回: [{'symbol': '600519', 'name': '贵州茅台', 'hold_ratio': 5.5}, ...]
        """
        cache = self._get_cache("south_holdings", days=1)
        if cache:
            return cache
        try:
            # 获取南向资金持股明细
            df = ak.stock_hsgt_hsgt_hold_stock_em(symbol="南向资金")
            if df is not None and not df.empty:
                results = []
                for _, row in df.head(20).iterrows():
                    # 尝试获取股票代码和名称
                    symbol = ''
                    name = ''
                    for col in df.columns:
                        if '代码' in col or 'symbol' in col.lower():
                            symbol = str(row[col])
                        if '名称' in col or 'name' in col.lower():
                            name = str(row[col])
                    
                    # 转换港股代码为A股代码（如果有对应关系）
                    symbol = self._convert_hk_to_a_share(symbol)
                    
                    if symbol:
                        results.append({
                            'symbol': symbol,
                            'name': name,
                            'hold_ratio': self._safe_float(row.get('持股数量占H股百分比', row.get('持股比例', 0))),
                        })
                self._set_cache("south_holdings", results)
                return results
        except Exception as e:
            print(f"获取南向资金重仓股失败: {e}")
        
        # 降级：返回常见港股通标的
        return self._get_south_stock_pool()

    def _convert_hk_to_a_share(self, hk_code):
        """将港股代码转换为A股代码（部分常见标的）
        港股代码如 00700 -> 腾讯控股，A股如 600519 -> 贵州茅台
        """
        # 常见AH对应关系
        ah_mapping = {
            '00700': None,  # 腾讯控股 - 无对应A股
            '09988': None,  # 阿里巴巴 - 无对应A股
            '03690': None,  # 美团 - 无对应A股
            '09888': None,  # 网易 - 无对应A股
            '09899': None,  # 京东 - 无对应A股
            '01810': None,  # 小米 - 无对应A股
            '00941': '600941',  # 中国移动 -> 中国移动
            '00939': '601939',  # 建设银行 -> 建设银行
            '00992': '601992',  # 中信股份 -> 金隅集团
            '01088': '601088',  # 中国神华 -> 中国神华
            '01398': '601398',  # 工商银行 -> 工商银行
            '03988': '601288',  # 农业银行 -> 农业银行
        }
        return ah_mapping.get(hk_code)

    def _get_south_stock_pool(self):
        """获取港股通标的池（A股中可投资港股的标的）"""
        return [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600887', 'name': '伊利股份'},
            {'symbol': '000333', 'name': '美的集团'},
            {'symbol': '600030', 'name': '中信证券'},
            {'symbol': '601166', 'name': '兴业银行'},
            {'symbol': '600900', 'name': '长江电力'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '601012', 'name': '隆基绿能'},
            {'symbol': '600276', 'name': '恒瑞医药'},
            {'symbol': '600028', 'name': '中国石化'},
            {'symbol': '601857', 'name': '中国石油'},
        ]

    # ==================== 事件数据 ====================

    def get_limit_up_list(self, date=None):
        """获取涨停板股票列表"""
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        cache_key = f"limitup_{date}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        
        # 尝试多个涨跌停接口
        funcs_to_try = [
            ('ak.stock_zt_pool_em', lambda: ak.stock_zt_pool_em(date=date)),
            ('ak.stock_zt_pool_cw', lambda: ak.stock_zt_pool_cw(date=date)),
        ]
        
        for func_name, func in funcs_to_try:
            try:
                df = func()
                if df is not None and not df.empty:
                    self._set_cache(cache_key, df.to_dict('records'))
                    return df
            except (AttributeError, Exception) as e:
                print(f"{func_name} 获取涨停板失败: {e}")
                continue
        
        print(f"获取涨停板失败: 所有接口均不可用")
        return pd.DataFrame()

    def get_dragon_tiger_list(self, date=None):
        """获取龙虎榜数据"""
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        cache_key = f"lhb_{date}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
            if df is not None and not df.empty:
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取龙虎榜失败: {e}")
        return pd.DataFrame()

    def get_executive_trading(self):
        """获取高管增减持数据"""
        cache = self._get_cache("exec_trade", days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_ggcg_em()
            if df is not None and not df.empty:
                df = df.head(100)  # 最近100条
                self._set_cache("exec_trade", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取高管增减持失败: {e}")
        return pd.DataFrame()

    def get_analyst_rating(self, symbol):
        """获取分析师评级"""
        cache_key = f"rating_{symbol}"
        cache = self._get_cache(cache_key, days=7)
        if cache:
            return cache
        try:
            df = ak.stock_research_report_em(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[0].to_dict()
                data = {
                    'rating': latest.get('评级', ''),
                    'target_price': self._safe_float(latest.get('目标价', 0)),
                    'institution': latest.get('机构', ''),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取分析师评级失败 {symbol}: {e}")
        return {}

    # ==================== 指数数据 ====================

    def get_index_data(self, symbol="000300", days=60):
        """获取指数历史数据"""
        cache_key = f"idx_{symbol}_{days}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_zh_index_daily(symbol=f"sh{symbol}" if symbol.startswith('000') else f"sz{symbol}")
            if df is not None and not df.empty:
                df = df.tail(days)
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取指数数据失败: {e}")
        return pd.DataFrame()

    # ==================== 批量数据 ====================

    def get_hs300_valuation_batch(self):
        """批量获取沪深300估值数据（用于因子选股）"""
        cache = self._get_cache("hs300_val_batch", days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            # 使用东财实时行情获取全部A股估值
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                # 筛选沪深300
                hs300 = self.get_stock_pool("hs300")
                df = df[df['代码'].isin(hs300)]
                # 重命名列
                df = df.rename(columns={
                    '代码': 'symbol', '名称': 'name',
                    '最新价': 'close', '涨跌幅': 'pct_change',
                    '市盈率-动态': 'pe', '市净率': 'pb',
                    '总市值': 'total_mv', '流通市值': 'circ_mv',
                    '换手率': 'turnover', '量比': 'volume_ratio'
                })
                self._set_cache("hs300_val_batch", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"批量获取估值失败: {e}")
        return pd.DataFrame()

    # ==================== 工具方法 ====================

    def _safe_float(self, value, default=0.0):
        """安全转换为浮点数，支持中文单位（万、亿）"""
        if value is None or value == '' or value == '--' or value is False:
            return default
        try:
            # 处理字符串类型
            if isinstance(value, str):
                value = value.strip()
                if not value or value == '--' or value == 'False':
                    return default
                # 处理中文单位
                multiplier = 1.0
                if '亿' in value:
                    multiplier = 1e8
                    value = value.replace('亿', '')
                elif '万' in value:
                    multiplier = 1e4
                    value = value.replace('万', '')
                elif '%' in value:
                    multiplier = 1.0
                    value = value.replace('%', '')
                value = value.strip()
                if not value:
                    return default
                return float(value) * multiplier
            return float(value)
        except (ValueError, TypeError):
            return default

    def get_market_baojun(self):
        """获取大盘指数行情"""
        cache = self._get_cache("market", days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            result = []
            for sym, name in [('000001', '上证指数'), ('399001', '深证成指'), ('399006', '创业板指')]:
                try:
                    df = ak.stock_zh_index_daily(symbol=f"sh{sym}" if sym.startswith('000') else f"sz{sym}")
                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        result.append({
                            'symbol': sym, 'name': name,
                            'close': latest.get('close', 0),
                            'open': latest.get('open', 0),
                            'high': latest.get('high', 0),
                            'low': latest.get('low', 0),
                            'volume': latest.get('volume', 0),
                        })
                except:
                    continue
            if result:
                self._set_cache("market", result)
                return pd.DataFrame(result)
        except Exception as e:
            print(f"获取大盘指数失败: {e}")
        return pd.DataFrame()

    # ==================== 融资融券数据 ====================

    def get_margin_trading(self, symbol):
        """获取个股融资融券数据
        返回：融资余额、融券余额、融资融券余额
        """
        cache_key = f"margin_{symbol}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return cache
        try:
            df = ak.stock_margin_detail_szse(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[-1].to_dict()
                data = {
                    'margin_balance': self._safe_float(latest.get('融资余额', 0)),  # 融资余额（元）
                    'short_balance': self._safe_float(latest.get('融券余额', 0)),   # 融券余额（元）
                    'margin_ratio': self._safe_float(latest.get('融资融券余额', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            # 尝试上交所
            try:
                df = ak.stock_margin_detail_sse(symbol=symbol)
                if df is not None and not df.empty:
                    latest = df.iloc[-1].to_dict()
                    data = {
                        'margin_balance': self._safe_float(latest.get('融资余额', 0)),
                        'short_balance': self._safe_float(latest.get('融券余额', 0)),
                        'margin_ratio': self._safe_float(latest.get('融资融券余额', 0)),
                    }
                    self._set_cache(cache_key, data)
                    return data
            except Exception as e2:
                print(f"获取融资融券失败 {symbol}: {e2}")
        return {}

    def get_margin_stocks(self):
        """获取融资融券标的股票列表"""
        cache = self._get_cache("margin_stocks", days=7)
        if cache:
            return cache
        try:
            df = ak.stock_margin_szse()
            if df is not None and not df.empty:
                stocks = df['股票代码'].tolist() if '股票代码' in df.columns else []
                self._set_cache("margin_stocks", stocks)
                return stocks
        except Exception as e:
            print(f"获取融资标的失败: {e}")
        try:
            df = ak.stock_margin_sse()
            if df is not None and not df.empty:
                stocks = df['股票代码'].tolist() if '股票代码' in df.columns else []
                self._set_cache("margin_stocks", stocks)
                return stocks
        except Exception as e:
            print(f"获取融资标的失败: {e}")
        return []

    def get_margin_flow(self, symbol, days=30):
        """获取融资融券历史流向"""
        cache_key = f"margin_flow_{symbol}_{days}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_margin_detail_szse(symbol=symbol)
            if df is not None and not df.empty:
                df = df.tail(days)
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取融资流向失败 {symbol}: {e}")
        return pd.DataFrame()

    # ==================== 龙虎榜增强 ====================

    def get_lhb_stats(self, symbol, days=30):
        """获取个股龙虎榜统计（近N日买入卖出席位）"""
        cache_key = f"lhb_stats_{symbol}_{days}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return cache
        try:
            df = ak.stock_lhb_detail_em(start_date=(
                datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"))
            if df is not None and not df.empty:
                # 筛选该股票
                stock_df = df[df['股票代码'] == symbol]
                if not stock_df.empty:
                    data = {
                        'lhb_count': len(stock_df),  # 上榜次数
                        'buy_amount': stock_df['买入金额'].sum() if '买入金额' in stock_df.columns else 0,
                        'sell_amount': stock_df['卖出金额'].sum() if '卖出金额' in stock_df.columns else 0,
                    }
                    self._set_cache(cache_key, data)
                    return data
        except Exception as e:
            print(f"获取龙虎榜统计失败 {symbol}: {e}")
        return {}

    # ==================== 大盘/市场情绪 ====================

    def get_market_sentiment(self):
        """获取市场情绪指标：上涨下跌家数、涨停跌停数、成交量"""
        cache = self._get_cache("sentiment", days=1)
        if cache:
            return cache
        try:
            # 涨跌统计
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                rise_count = len(df[df['涨跌幅'] > 0])
                fall_count = len(df[df['涨跌幅'] < 0])
                flat_count = len(df[df['涨跌幅'] == 0])
                limit_up = len(df[df['涨跌幅'] >= 9.5])  # 近似涨停
                limit_down = len(df[df['涨跌幅'] <= -9.5])  # 近似跌停

                # 市场宽度
                rise_pct = rise_count / (rise_count + fall_count) * 100 if (rise_count + fall_count) > 0 else 50

                data = {
                    'rise_count': rise_count,
                    'fall_count': fall_count,
                    'flat_count': flat_count,
                    'limit_up_count': limit_up,
                    'limit_down_count': limit_down,
                    'market_breadth': rise_pct,  # 市场广度（上涨家数占比）
                    'total_volume': df['成交量'].sum() if '成交量' in df.columns else 0,
                }
                self._set_cache("sentiment", data)
                return data
        except Exception as e:
            print(f"获取市场情绪失败: {e}")
        return {}

    # ==================== 机构持仓 ====================

    def get_institution_holding(self, symbol):
        """获取机构持仓数据（基金重仓股）
        优先使用东财基金重仓接口，失败时使用东财基金持股详情接口
        """
        cache_key = f"inst_hold_{symbol}"
        cache = self._get_cache(cache_key, days=7)
        if cache:
            return cache
        
        # 方案1: 使用东财基金重仓股接口
        try:
            df = ak.stock_fund_hold_em(symbol=symbol)
            if df is not None and not df.empty:
                # 获取该股票在最近报告期的基金持股数据
                if '基金持股占流通A股比例' in df.columns:
                    fund_ratio = df['基金持股占流通A股比例'].iloc[0]
                elif '基金持股比例' in df.columns:
                    fund_ratio = df['基金持股比例'].iloc[0]
                else:
                    fund_ratio = 0
                data = {
                    'fund_hold_ratio': self._safe_float(fund_ratio),
                    'inst_count': len(df),  # 持有该股的基金数量
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"东财基金重仓接口失败 {symbol}: {e}")
        
        # 方案2: 使用东财基金持股详情接口
        try:
            df = ak.stock_fund_hold_detail_em(symbol=symbol)
            if df is not None and not df.empty:
                latest = df.iloc[-1].to_dict()
                data = {
                    'fund_hold_ratio': self._safe_float(latest.get('基金持股占比', 0)),
                    'inst_count': len(df),  # 持有该股的基金数量
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"东财基金持股详情接口失败 {symbol}: {e}")
        return {}

    def get_institution调研(self, symbol):
        """获取机构调研数据"""
        cache_key = f"inst_research_{symbol}"
        cache = self._get_cache(cache_key, days=7)
        if cache:
            return cache
        try:
            df = ak.stock_jgyd_em(symbol=symbol)
            if df is not None and not df.empty:
                data = {
                    'research_count': len(df),
                    'latest_research_date': df['调研日期'].iloc[0] if '调研日期' in df.columns else '',
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取机构调研失败 {symbol}: {e}")
        return {}

    # ==================== 筹码分布 ====================

    def get_chip_distribution(self, symbol):
        """
        获取股票筹码分布数据
        使用AKShare的 stock_cyq_em 接口获取东方财富筹码分布数据
        
        Args:
            symbol: 6位股票代码，如 '600519'
            
        Returns:
            dict: 筹码分布数据
                {
                    'concentration': 集中度,
                    'avg_cost': 平均成本,
                    'profit_ratio': 获利比例,
                    'date': 数据日期
                }
        """
        cache_key = f"chip_dist_{symbol}"
        cache = self._get_cache(cache_key, days=1)  # 筹码数据每日更新
        if cache:
            return cache
        
        try:
            df = ak.stock_cyq_em(symbol=symbol)
            if df is not None and not df.empty:
                # 解析返回数据
                # 典型列：日期, 收盘, 涨跌幅, 获利比例, 平均成本, 集中度70, 集中度90等
                latest = df.iloc[0]
                
                data = {
                    'date': str(latest.get('日期', '')),
                    'close': float(latest.get('收盘', 0)),
                    'change_pct': float(latest.get('涨跌幅', 0)),
                    'profit_ratio': float(latest.get('获利比例', 0)),  # 获利盘比例 %
                    'avg_cost': float(latest.get('平均成本(元)', 0)),  # 平均成本
                    'concentration_70': float(latest.get('集中度70%', 0)),  # 70%筹码集中度
                    'concentration_90': float(latest.get('集中度90%', 0)),  # 90%筹码集中度
                    'concentration': float(latest.get('集中度70%', 0)),  # 默认使用70%集中度
                }
                
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取筹码分布失败 {symbol}: {e}")
        return {}


if __name__ == "__main__":
    helper = AKShareHelper()
    # 测试数据获取
    print("=== 测试数据层 ===")
    stocks = helper.get_stock_pool("hs300")
    print(f"沪深300成分股: {len(stocks)}只")

    if stocks:
        symbol = stocks[0]
        print(f"\n测试股票: {symbol}")

        kline = helper.get_history_kline(symbol, days=30)
        print(f"K线数据: {len(kline)}条")

        val = helper.get_valuation_data(symbol)
        print(f"估值数据: PE={val.get('pe')}, PB={val.get('pb')}")

        fin = helper.get_financial_indicator(symbol)
        print(f"财务指标: ROE={fin.get('roe')}")

        growth = helper.get_growth_data(symbol)
        print(f"成长数据: {growth}")
