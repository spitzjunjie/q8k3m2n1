# -*- coding: utf-8 -*-
"""
Tushare数据封装模块（主数据源）
更稳定的数据获取
"""

import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import time

class TushareHelper:
    """Tushare数据助手（主数据源）"""

    def __init__(self, token=None, cache_dir="data/cache"):
        # 获取token
        if token is None:
            token = os.getenv('TUSHARE_TOKEN')
        if token:
            ts.set_token(token)
        self.pro = ts.pro_api(token) if token else ts.pro_api()
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._hs300_cache = None
        self._last_call_time = {}  # 记录上次调用时间
        self._min_interval = 0.2  # 最小调用间隔（秒）

    def _rate_limit(self, api_name):
        """速率限制"""
        current_time = time.time()
        if api_name in self._last_call_time:
            elapsed = current_time - self._last_call_time[api_name]
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
        self._last_call_time[api_name] = time.time()

    def _get_cache(self, key, days=1):
        """读取缓存"""
        cache_file = os.path.join(self.cache_dir, f"ts_{key}.json")
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
        cache_file = os.path.join(self.cache_dir, f"ts_{key}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # ==================== 股票列表 ====================

    def get_stock_list(self):
        """获取A股股票列表"""
        cache = self._get_cache("stock_list", days=7)
        if cache:
            return cache

        try:
            # 获取所有上市股票
            df = self.pro.stock_basic(exchange='', list_status='L',
                                   fields='ts_code,symbol,name,industry,market')
            if df is not None and len(df) > 0:
                stocks = df.to_dict('records')
                self._set_cache("stock_list", stocks)
                return stocks
        except Exception as e:
            print(f"[Tushare]获取股票列表失败: {e}")
        return []

    # ==================== 股票池 ====================

    def get_stock_pool(self, pool_type='hs300', sorted_by_market_value=False):
        """获取股票池"""
        try:
            # 使用月度数据
            # 获取最近月份
            last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime('%Y%m%d')
            
            if pool_type == 'hs300':
                df = self.pro.index_weight(index_code='000300.SH', start_date=last_month, end_date=last_month)
            elif pool_type == 'zz500':
                df = self.pro.index_weight(index_code='000905.SH', start_date=last_month, end_date=last_month)
            elif pool_type == 'zz800':
                df = self.pro.index_weight(index_code='000852.SH', start_date=last_month, end_date=last_month)
            else:  # 全市场
                df = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code')
                if df is not None and len(df) > 0:
                    return df['ts_code'].tolist()
                return []

            if df is None or len(df) == 0:
                return []

            stocks = []
            for _, row in df.iterrows():
                code = row.get('con_code')
                if code:
                    stocks.append(str(code).strip())

            return stocks
        except Exception as e:
            print(f"[Tushare]获取股票池失败: {e}")
            return []

    # ==================== K线数据 ====================

    def get_history_kline(self, symbol, days=60, end_date=None):
        """获取历史K线"""
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')

        # 转换symbol格式
        code = symbol
        if code.endswith('.SH') or code.endswith('.SZ'):
            pass
        else:
            code = code + '.SH' if code.startswith(('6', '9')) else code + '.SZ'

        try:
            self._rate_limit('daily')
            df = self.pro.daily(ts_code=code, start_date=start_date, end_date=end_date)
            if df is not None and len(df) > 0:
                df = df.sort_values('trade_date')
                # 转换日期格式
                df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
                # 统一列名（tushare用vol，akshare用volume）
                if 'vol' in df.columns and 'volume' not in df.columns:
                    df['volume'] = df['vol']
                return df
        except Exception as e:
            print(f"[Tushare]获取K线失败 {symbol}: {e}")

        return pd.DataFrame()

    # ==================== 实时行情 ====================

    def get_realtime_quote(self, symbols):
        """获取实时行情"""
        if not symbols:
            return pd.DataFrame()

        try:
            if isinstance(symbols, str):
                symbols = [symbols]
            # 转换格式
            codes = []
            for s in symbols:
                code = s.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
                codes.append(code)
            df = self.pro.realtime_quote(ts_codes=codes)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"[Tushare]获取实时行情失败: {e}")
            return pd.DataFrame()

    # ==================== 财务数据 ====================

    def get_financial_data(self, symbol):
        """获取财务数据"""
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        try:
            df = self.pro.fina_indicator(ts_code=code, start_date='20240101')
            if df is not None and len(df) > 0:
                return df.iloc[0].to_dict()
        except Exception as e:
            pass
        return {}

    # ==================== 资金流 ====================

    def get_money_flow(self, symbol):
        """获取资金流"""
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        try:
            df = self.pro.moneyflow(ts_code=code)
            if df is not None and len(df) > 0:
                return df.iloc[0].to_dict()
        except:
            pass
        return {}

    # ==================== 龙虎榜 ====================

    def get_lhb_list(self, days=30):
        """获取龙虎榜"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        try:
            df = self.pro.top_list(start_date=start_date, end_date=end_date)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"[Tushare]获取龙虎榜失败: {e}")
            return pd.DataFrame()

    # ==================== 估值数据 ====================

    def get_valuation(self, symbol):
        """获取估值数据"""
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        try:
            df = self.pro.daily_indicator(ts_code=code, trade_date=datetime.now().strftime('%Y%m%d'))
            if df is not None and len(df) > 0:
                return df.iloc[0].to_dict()
        except:
            pass
        return {}

    # ==================== 指数成分 ====================

    def get_index_components(self, index_code='000300.SH'):
        """获取指数成分股"""
        trade_date = datetime.now().strftime('%Y%m%d')
        try:
            df = self.pro.index_weight(index_code=index_code, start_date=trade_date, end_date=trade_date)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"[Tushare]获取指数成分失败: {e}")
            return pd.DataFrame()

    # ==================== 交易日 ====================

    def is_trading_day(self, date=None):
        """检查是否交易日"""
        if not date:
            date = datetime.now().strftime('%Y%m%d')
        try:
            df = self.pro.trade_cal(exchange='SSE', start_date=date, end_date=date)
            return df is not None and len(df) > 0 and df.iloc[0]['is_open'] == 1
        except:
            return True

    def get_trade_dates(self, days=30):
        """获取最近交易日"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        try:
            df = self.pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
            if df is not None:
                return df[df['is_open'] == 1]['cal_date'].tolist()
        except:
            pass
        return []

    # ==================== 财报数据 ====================

    def get_annual_report(self, symbol):
        """获取年报数据"""
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        try:
            df = self.pro.fina_mainbz(ts_code=code, type='B')
            return df if df is not None else pd.DataFrame()
        except:
            return pd.DataFrame()
