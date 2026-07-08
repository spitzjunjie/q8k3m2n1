# -*- coding: utf-8 -*-
"""
Tushare数据封装模块（主要数据源）
比AKShare更稳定
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
        self.token = token or os.getenv('TUSHARE_TOKEN')
        if self.token:
            ts.set_token(self.token)
        self.pro = ts.pro_api(self.token) if self.token else ts.pro_api()
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache(self, key, days=1):
        cache_file = os.path.join(self.cache_dir, f"ts_{key}.json")
        if os.path.exists(cache_file):
            file_time = os.path.getmtime(cache_file)
            if (datetime.now().timestamp() - file_time) < days * 86400:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        return None

    def _set_cache(self, key, data):
        cache_file = os.path.join(self.cache_dir, f"ts_{key}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # ==================== 基础行情 ====================

    def get_stock_list(self):
        """获取A股股票列表"""
        cache = self._get_cache("stock_list", days=7)
        if cache:
            return pd.DataFrame(cache)

        try:
            df = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,industry,market')
            stocks = df.to_dict('records')
            self._set_cache("stock_list", stocks)
            return df
        except Exception as e:
            print(f"[Tushare]获取股票列表失败: {e}")
            return pd.DataFrame()

    def get_history_kline(self, symbol, days=60, end_date=None):
        """获取历史K线"""
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days*2)).strftime('%Y%m%d')

        try:
            # 转换symbol格式
            code = symbol.replace('.SH', '.SH').replace('.SZ', '.SZ')
            if not code.endswith('.SH') and not code.endswith('.SZ'):
                code = code + '.SH' if code.startswith('6') else code + '.SZ'

            df = self.pro.bar(code, start_date=start_date, end_date=end_date, asset='E')
            if df is not None and not df.empty:
                df = df.sort_values('trade_date')
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"[Tushare]获取K线失败 {symbol}: {e}")
            return pd.DataFrame()

    def get_realtime_quote(self, symbols):
        """获取实时行情"""
        try:
            df = ts.realtime_quote(symbols=symbols)
            return df
        except Exception as e:
            print(f"[Tushare]获取实时行情失败: {e}")
            return pd.DataFrame()

    # ==================== 财务数据 ====================

    def get_financial_data(self, symbol):
        """获取财务数据"""
        try:
            code = symbol.replace('.SH', '').replace('.SZ', '')
            df = self.pro.fina_indicator(ts_code=code, start_date='20240101')
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()
            return {}
        except Exception as e:
            print(f"[Tushare]获取财务数据失败 {symbol}: {e}")
            return {}

    # ==================== 资金流 ====================

    def get_money_flow(self, symbol):
        """获取资金流数据"""
        try:
            code = symbol.replace('.SH', '').replace('.SZ', '')
            df = self.pro.moneyflow(ts_code=code)
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()
            return {}
        except Exception as e:
            return {}

    # ==================== 龙虎榜 ====================

    def get_lhb_list(self, days=30):
        """获取龙虎榜数据"""
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            df = self.pro.top_list(start_date=start_date, end_date=end_date)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            print(f"[Tushare]获取龙虎榜失败: {e}")
            return pd.DataFrame()

    # ==================== 估值数据 ====================

    def get_valuation(self, symbol):
        """获取估值数据"""
        try:
            code = symbol.replace('.SH', '').replace('.SZ', '')
            df = ts.realtime_quote(symbols=[code])
            if df is not None and not df.empty:
                return {
                    'pe': df['pe_ttm'].iloc[0] if 'pe_ttm' in df.columns else 0,
                    'pb': df['pb'].iloc[0] if 'pb' in df.columns else 0,
                    'price': df['price'].iloc[0] if 'price' in df.columns else 0,
                }
            return {}
        except Exception as e:
            return {}

    # ==================== 指数成分 ====================

    def get_index_components(self, index_code='000300.SH'):
        """获取指数成分股"""
        try:
            df = self.pro.index_weight(index_code=index_code)
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
            return df is not None and not df.empty and df['is_open'].iloc[0] == 1
        except:
            return True  # 默认当交易日处理

    def get_trade_dates(self, days=30):
        """获取最近交易日"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        try:
            df = self.pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
            if df is not None:
                return df[df['is_open']==1]['cal_date'].tolist()
            return []
        except:
            return []

    # ==================== 财报数据 ====================

    def get_annual_report(self, symbol):
        """获取年报数据"""
        try:
            code = symbol.replace('.SH', '').replace('.SZ', '')
            df = self.pro.fina_mainbz(ts_code=code, type='B')
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            return pd.DataFrame()
