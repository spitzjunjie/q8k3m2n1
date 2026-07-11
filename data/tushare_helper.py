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
        self._kline_cache = {}  # K线缓存
        self._last_call_time = {}  # 记录上次调用时间
        self._min_interval = 1.5  # 最小调用间隔（秒），避免超限（1.5秒=40次/分，安全余量充足）

    def _normalize_code(self, symbol):
        """标准化股票代码为Tushare格式（加交易所后缀）"""
        code = symbol.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        if code.startswith('6') or code.startswith('5') or code.startswith('9'):
            return code + '.SH'
        elif code.startswith('8') or code.startswith('4'):
            return code + '.BJ'
        else:
            return code + '.SZ'

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
        """获取历史K线（带缓存）"""
        # 检查缓存
        cache_key = f"{symbol}_{days}_{end_date}"
        if cache_key in self._kline_cache:
            return self._kline_cache[cache_key]

        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        else:
            # 转换日期格式 2026-07-01 -> 20260701
            end_date = end_date.replace('-', '').replace('/', '')
        
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
                # 缓存结果
                self._kline_cache[cache_key] = df
                return df
        except Exception as e:
            print(f"[Tushare]获取K线失败 {symbol}: {e}")

        return pd.DataFrame()

    def get_batch_kline(self, symbols, days=60, end_date=None):
        """批量获取多个股票的K线（优化API调用）
        
        Args:
            symbols: 股票代码列表
            days: 获取天数
            end_date: 结束日期
            
        Returns:
            dict: {symbol: DataFrame}
        """
        results = {}
        
        # 批量调用前先检查缓存
        uncached_symbols = []
        for sym in symbols:
            cache_key = f"{sym}_{days}_{end_date}"
            if cache_key in self._kline_cache:
                results[sym] = self._kline_cache[cache_key]
            else:
                uncached_symbols.append(sym)
        
        if not uncached_symbols:
            return results
        
        # 批量获取未缓存的股票
        for sym in uncached_symbols:
            df = self.get_history_kline(sym, days, end_date)
            results[sym] = df
            # 添加短暂延迟，避免批量请求过快
            time.sleep(0.1)
        
        return results

    # ==================== 实时行情 ====================

    def get_realtime_quote(self, symbols):
        """获取实时行情 - 尝试多个接口"""
        if not symbols:
            return pd.DataFrame()

        try:
            if isinstance(symbols, str):
                symbols = [symbols]
            
            # 转换格式为Tushare标准格式 (单个代码)
            code = symbols[0].replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
            # 添加交易所后缀
            if code.startswith('6') or code.startswith('5') or code.startswith('9'):
                code = code + '.SH'
            elif code.startswith('8') or code.startswith('4'):
                code = code + '.BJ'
            else:
                code = code + '.SZ'
            
            # 方案1: realtime_quote - 单个股票直接传字符串
            try:
                df = self.pro.realtime_quote(ts_code=code)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                print(f"[Tushare]realtime_quote失败: {e}")
            
            # 方案2: rt_price - 实时价格接口
            try:
                df = self.pro.rt_price(ts_code=code)
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                print(f"[Tushare]rt_price失败: {e}")
            
            # 方案3: 批量实时行情
            if len(symbols) > 1:
                try:
                    codes = []
                    for s in symbols:
                        c = s.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
                        if c.startswith('6') or c.startswith('5') or c.startswith('9'):
                            c = c + '.SH'
                        elif c.startswith('8') or c.startswith('4'):
                            c = c + '.BJ'
                        else:
                            c = c + '.SZ'
                        codes.append(c)
                    codes_str = ','.join(codes)
                    df = self.pro.realtime_quote(ts_code=codes_str)
                    if df is not None and not df.empty:
                        return df
                except Exception as e:
                    print(f"[Tushare]批量realtime_quote失败: {e}")
            
            return pd.DataFrame()
        except Exception as e:
            print(f"[Tushare]获取实时行情失败: {e}")
            return pd.DataFrame()

    # ==================== 财务数据 ====================

    def get_financial_data(self, symbol):
        """获取财务数据"""
        code = self._normalize_code(symbol)
        try:
            df = self.pro.fina_indicator(ts_code=code, start_date='20240101')
            if df is not None and len(df) > 0:
                # 转换并返回关键指标
                row = df.iloc[0]
                return {
                    'roe': row.get('roe', 0),
                    'gross_margin': row.get('gross_margin', 0),
                    'net_margin': row.get('net_profit_ratio', 0),
                    'debt_ratio': row.get('debt_to_assets', 0),
                    'current_ratio': row.get('current_ratio', 0),
                    'roic': row.get('roic', 0),
                }
        except Exception as e:
            pass
        return {}

    def get_financial_indicator(self, symbol):
        """获取财务指标"""
        return self.get_financial_data(symbol)

    def get_growth_data(self, symbol):
        """获取成长数据（营收增速、净利润增速）"""
        code = self._normalize_code(symbol)
        try:
            df = self.pro.fina_indicator(ts_code=code, start_date='20240101', fields='ts_code,trade_date,roe,net_profit_ratio,revenue_ratio,profit_ratio')
            if df is not None and len(df) > 0:
                row = df.iloc[0]
                return {
                    'profit_growth': row.get('profit_ratio', 0) * 10,  # 简化处理
                    'revenue_growth': row.get('revenue_ratio', 0) * 10,  # 简化处理
                }
        except:
            pass
        # Fallback: 使用利润表数据
        try:
            df = self.pro.income(ts_code=code, start_date='20240101', fields='ts_code,end_date,total_profit,operating_revenue')
            if df is not None and len(df) >= 2:
                current = df.iloc[0]
                prev = df.iloc[1]
                if prev['total_profit'] != 0:
                    profit_growth = (current['total_profit'] / prev['total_profit'] - 1) * 100
                else:
                    profit_growth = 0
                if prev['operating_revenue'] != 0:
                    revenue_growth = (current['operating_revenue'] / prev['operating_revenue'] - 1) * 100
                else:
                    revenue_growth = 0
                return {'profit_growth': profit_growth, 'revenue_growth': revenue_growth}
        except:
            pass
        return {}

    def get_cash_flow(self, symbol):
        """获取现金流数据"""
        code = self._normalize_code(symbol)
        try:
            df = self.pro.cashflow(ts_code=code, start_date='20240101')
            if df is not None and len(df) > 0:
                row = df.iloc[0]
                return {
                    'operating_cf': row.get('netOperCashFlow', 0),
                    'investing_cf': row.get('netInvestCashFlow', 0),
                    'financing_cf': row.get('netFinCashFlow', 0),
                }
        except:
            pass
        return {}

    def get_valuation_data(self, symbol):
        """获取估值数据（PB、PE等）"""
        code = self._normalize_code(symbol)
        try:
            # 使用 daily_basic 接口获取最新估值
            df = self.pro.daily_basic(ts_code=code)
            if df is not None and len(df) > 0:
                row = df.iloc[0]
                return {
                    'pe': row.get('pe', 0),
                    'pb': row.get('pb', 0),
                    'ps': row.get('ps', 0),
                    'dv_ratio': row.get('dv_ratio', 0),
                    'total_mv': row.get('total_mv', 0),
                }
        except:
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

    def get_trade_dates(self, days=30, start_date=None):
        """获取最近交易日（升序排列）
        start_date: 开始日期（YYYYMMDD），None=自动从基准日期2026-05-26开始
        """
        end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            # 默认从基准日期开始（与backtest_history.py的BENCHMARK_START_DATE保持一致）
            start_date = '20260526'
        try:
            df = self.pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
            if df is not None:
                # 筛选交易日并排序（升序）
                dates = df[df['is_open'] == 1]['cal_date'].tolist()
                dates.sort()  # 升序排列
                # 筛选基准日期之后的交易日
                dates = [d for d in dates if d >= start_date]
                return dates[:days]  # 只返回最近的days个（从基准日期开始算）
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
