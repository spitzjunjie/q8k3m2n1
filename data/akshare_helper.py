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
import random

class AKShareHelper:
    """AKShare数据助手 - 优化版"""

    def __init__(self, cache_dir="data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._hs300_cache = None
        self._request_count = 0  # 请求计数器
        self._last_request_time = 0  # 上次请求时间
        self._min_request_interval = 0.3  # 最小请求间隔(秒)
        self._max_retries = 5  # 最大重试次数
        self._spot_em_snapshot = None  # 东财全市场快照缓存
        self._spot_sina_snapshot = None  # 新浪全市场快照缓存
        self._stock_news_cache = None  # 新闻缓存
        self._consecutive_network_failures = 0  # 连续网络失败计数
        self._base_wait_time = 2  # 基础等待时间(秒)

    def _rate_limit(self):
        """请求频率限制，避免被封"""
        self._request_count += 1
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        
        # 如果距离上次请求时间太短，等待一下
        if elapsed < self._min_request_interval:
            wait_time = self._min_request_interval - elapsed + random.uniform(0.1, 0.3)
            time.sleep(wait_time)
        
        # 每隔一定请求后增加随机等待
        if self._request_count % 10 == 0:
            time.sleep(random.uniform(0.5, 1.5))
        
        self._last_request_time = time.time()

    def _retry_request(self, func, *args, **kwargs):
        """带重试的请求，自动处理网络错误。连续网络失败 >= 3 次后进入快速熔断模式。"""
        FAST_FAIL_THRESHOLD = 3

        max_retries = 1 if self._consecutive_network_failures >= FAST_FAIL_THRESHOLD else self._max_retries
        last_error = None

        for attempt in range(max_retries):
            try:
                self._rate_limit()
                result = func(*args, **kwargs)
                self._consecutive_network_failures = 0
                return result
            except Exception as e:
                last_error = e
                error_str = str(e)

                is_network_error = any(x in error_str for x in [
                    'RemoteDisconnected', 'Connection aborted', 'ConnectionReset',
                    'ConnectionRefused', 'timed out', 'ReadTimeout',
                    'SSLError', 'EOF', 'getaddrinfo'
                ])

                if is_network_error:
                    self._consecutive_network_failures += 1
                    if attempt < max_retries - 1:
                        wait_time = self._base_wait_time * (attempt + 1) + random.uniform(0, 2)
                        print(f"  网络错误，{wait_time:.1f}秒后重试 ({attempt + 1}/{max_retries}): {e}")
                        time.sleep(wait_time)
                else:
                    self._consecutive_network_failures = 0
                    break

        raise last_error

    def wrap_akshare(self, func, *args, **kwargs):
        """包装AKShare函数，自动重试（供策略直接调用）"""
        return self._retry_request(func, *args, **kwargs)

    def _get_cache(self, key, days=1):
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_file):
            file_time = os.path.getmtime(cache_file)
            if (datetime.now().timestamp() - file_time) < days * 86400:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        return None


    def _get_spot_em_snapshot(self):
        """全市场实时行情快照（东财），同一实例/同一天内只抓一次。"""
        if self._spot_em_snapshot is not None:
            return self._spot_em_snapshot

        cache_key = "spot_em_snapshot"
        cached = self._get_cache(cache_key, days=1)
        if cached is not None:
            self._spot_em_snapshot = pd.DataFrame(cached)
            return self._spot_em_snapshot

        # 连续网络失败后进入快速熔断，避免每个策略都白等 3 次重试
        max_retries = 1 if self._consecutive_network_failures >= 3 else 3
        for attempt in range(max_retries):
            try:
                df = ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    self._set_cache(cache_key, df.to_dict('records'))
                    self._spot_em_snapshot = df
                    self._consecutive_network_failures = 0
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
                    print(f"东财实时行情连接失败，{wait_time}秒后重试 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    self._consecutive_network_failures += 1
                    print(f"东财实时行情获取失败: {e}")
                    break
        self._spot_em_snapshot = pd.DataFrame()
        return pd.DataFrame()

    def _get_spot_sina_snapshot(self):
        """新浪全市场实时行情快照，同一实例/同一天内只抓一次。"""
        if self._spot_sina_snapshot is not None:
            return self._spot_sina_snapshot

        cache_key = "spot_sina_snapshot"
        cached = self._get_cache(cache_key, days=1)
        if cached is not None:
            self._spot_sina_snapshot = pd.DataFrame(cached)
            return self._spot_sina_snapshot

        try:
            spot_df = ak.stock_zh_a_spot()
            if spot_df is not None and not spot_df.empty:
                self._set_cache(cache_key, spot_df.to_dict('records'))
                self._spot_sina_snapshot = spot_df
                return spot_df
        except Exception as e:
            print(f"新浪实时行情获取失败: {e}")
        self._spot_sina_snapshot = pd.DataFrame()
        return self._spot_sina_snapshot

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
        """获取单只股票实时行情（多备用接口）"""
        # 方案1: 东方财富
        try:
            df = self._get_spot_em_snapshot()
            if df is not None and not df.empty:
                stock = df[df['代码'] == symbol]
            if not stock.empty:
                return stock.iloc[0].to_dict()
        except Exception as e:
            pass

        # 方案2: 新浪快照（共享）
        try:
            df = self._get_spot_sina_snapshot()
            if df is not None and not df.empty:
                sina_symbol = f"sz{symbol}" if not symbol.startswith('6') else f"sh{symbol}"
                stock = df[df['代码'] == sina_symbol]
                if not stock.empty:
                    return stock.iloc[0].to_dict()
        except Exception as e:
            pass

        # 方案3: 腾讯财经
        try:
            df = self.wrap_akshare(ak.stock_zh_a_spot_tencent, symbol=symbol)
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()
        except Exception as e:
            pass

        return None

    def get_market_stocks(self):
        """获取全市场股票列表（多备用接口，带重试机制）"""
        cache = self._get_cache("market_stocks", days=1)
        if cache:
            return cache

        # 方案1: 东方财富全市场实时行情
        try:
            df = self.wrap_akshare(ak.stock_zh_a_spot_em)
            if df is not None and not df.empty:
                stocks = []
                for _, row in df.iterrows():
                    code = str(row.get('代码', ''))
                    name = str(row.get('名称', ''))

                    if not code or len(code) != 6:
                        continue
                    if 'ST' in name or '退' in name:
                        continue

                    total_mv = row.get('总市值', 0)
                    if total_mv and isinstance(total_mv, (int, float)):
                        total_mv = total_mv / 1e8

                    stocks.append({
                        'symbol': code,
                        'name': name,
                        'total_mv': total_mv,
                        'pb': row.get('市净率', 0),
                        'pe': row.get('市盈率-动态', 0),
                        'change_pct': row.get('涨跌幅', 0),
                    })

                self._set_cache("market_stocks", stocks)
                print(f"全市场股票获取成功: {len(stocks)} 只")
                return stocks
        except Exception as e:
            print(f"东方财富接口失败: {e}")

        # 方案2: 新浪实时行情
        try:
            df = self.wrap_akshare(ak.stock_zh_a_spot)
            if df is not None and not df.empty:
                stocks = []
                for _, row in df.iterrows():
                    code = str(row.get('symbol', '')).replace('sh', '').replace('sz', '')
                    name = str(row.get('name', ''))

                    if not code or len(code) != 6:
                        continue
                    if 'ST' in name or '退' in name:
                        continue

                    stocks.append({
                        'symbol': code,
                        'name': name,
                        'total_mv': 0,
                        'pb': 0,
                        'pe': 0,
                        'change_pct': row.get('change_pct', 0),
                    })

                self._set_cache("market_stocks", stocks)
                print(f"新浪接口获取成功: {len(stocks)} 只")
                return stocks
        except Exception as e:
            print(f"新浪接口失败: {e}")

        # 方案3: 新浪股票列表（基本信息）
        try:
            df = self.wrap_akshare(ak.stock_info_a_code_name)
            if df is not None and not df.empty:
                stocks = []
                for _, row in df.iterrows():
                    code = str(row.get('代码', ''))
                    name = str(row.get('名称', ''))

                    if not code or len(code) != 6:
                        continue
                    if 'ST' in name or '退' in name:
                        continue

                    stocks.append({
                        'symbol': code,
                        'name': name,
                        'total_mv': 0,
                        'pb': 0,
                        'pe': 0,
                        'change_pct': 0,
                    })

                self._set_cache("market_stocks", stocks)
                print(f"股票列表获取成功: {len(stocks)} 只")
                return stocks
        except Exception as e:
            print(f"股票列表接口失败: {e}")

        # 方案4: 腾讯财经接口
        try:
            df = self.wrap_akshare(ak.stock_zh_a_spot_tencent)
            if df is not None and not df.empty:
                stocks = []
                for _, row in df.iterrows():
                    code = str(row.get('code', ''))
                    name = str(row.get('name', ''))

                    if not code or len(code) != 6:
                        continue
                    if 'ST' in name or '退' in name:
                        continue

                    stocks.append({
                        'symbol': code,
                        'name': name,
                        'total_mv': 0,
                        'pb': 0,
                        'pe': 0,
                        'change_pct': 0,
                    })

                self._set_cache("market_stocks", stocks)
                print(f"腾讯财经接口获取成功: {len(stocks)} 只")
                return stocks
        except Exception as e:
            print(f"腾讯财经接口失败: {e}")

        return []

    def get_etf_history_kline(self, symbol, period="daily", days=60, end_date=None):
        """获取ETF历史K线（优化版）
        symbol: ETF代码，如 '510300' / '159915'
        end_date: 指定结束日期(YYYYMMDD字符串或YYYY-MM-DD)，None=今天
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
        
        # 方案1: 新浪ETF专用接口（稳定、免东财代理，沪深ETF均支持）
        try:
            etf_symbol = self._to_etf_sina_symbol(symbol)
            if etf_symbol:
                df = self._retry_request(ak.fund_etf_hist_sina, symbol=etf_symbol)
                if df is not None and not df.empty:
                    if 'date' not in df.columns:
                        for col in df.columns:
                            if 'date' in col.lower():
                                df = df.rename(columns={col: 'date'})
                                break
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
                    if end_date:
                        df = df[df['date'] <= end_date.replace('-', '')]
                    df = df.tail(days)
                    self._set_cache(cache_key, df.to_dict('records'))
                    return df
        except Exception as e:
            print(f"新浪ETF接口失败 {symbol}: {e}")

        # 方案2: 东方财富ETF接口（降级）
        try:
            df = self._retry_request(ak.fund_etf_hist_em, symbol=symbol, period=period,
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
                    for col in df.columns:
                        if 'date' in col.lower() or '日期' in col:
                            df = df.rename(columns={col: 'date'})
                            break
                df['date'] = df['date'].astype(str)
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"东财ETF接口失败 {symbol}: {e}")

        # 方案3: 降级用股票K线（ETF也是股票代码）
        try:
            df = self._retry_request(ak.stock_zh_a_daily, symbol=f"sh{symbol}",
                                     start_date=actual_start, end_date=actual_end, adjust="qfq")
            if df is not None and not df.empty:
                df = df.tail(days)
                df['date'] = df['date'].astype(str)
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"ETF备用接口也失败 {symbol}: {e}")

        return pd.DataFrame()

    def _to_etf_sina_symbol(self, symbol):
        """6 位 ETF 代码转新浪符号：510300 -> sh510300，159915 -> sz159915。"""
        symbol = str(symbol)
        if symbol.startswith('5'):
            return f"sh{symbol}"
        if symbol.startswith('1'):
            return f"sz{symbol}"
        return ""

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

        # 方案0: ETF 代码直接走新浪 ETF 接口（stock_zh_a_daily 不覆盖 ETF）
        etf_symbol = self._to_etf_sina_symbol(symbol)
        if etf_symbol:
            try:
                df = self._retry_request(ak.fund_etf_hist_sina, symbol=etf_symbol)
                if df is not None and not df.empty:
                    if 'date' not in df.columns:
                        for col in df.columns:
                            if 'date' in col.lower():
                                df = df.rename(columns={col: 'date'})
                                break
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
                    if end_date:
                        df = df[df['date'] <= end_date.replace('-', '')]
                    df = df.tail(days)
                    keep_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
                    existing_cols = [c for c in keep_cols if c in df.columns]
                    df = df[existing_cols]
                    self._set_cache(cache_key, df.to_dict('records'))
                    return df
            except Exception as e:
                print(f"新浪ETF K线失败 {symbol}: {e}")

        # 方案1: 新浪源 stock_zh_a_daily（稳定，需要sz/sh前缀）
        try:
            prefix = 'sh' if symbol.startswith('6') else 'sz'
            sina_symbol = f"{prefix}{symbol}"
            df = self._retry_request(ak.stock_zh_a_daily, symbol=sina_symbol, 
                                     start_date=actual_start, end_date=actual_end, adjust="qfq")
            if df is not None and not df.empty:
                df = df.tail(days)
                date_col = None
                for col in df.columns:
                    if 'date' in col.lower() or '日期' in col:
                        date_col = col
                        break
                if date_col:
                    df = df.rename(columns={date_col: 'date'})
                keep_cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
                existing_cols = [c for c in keep_cols if c in df.columns]
                df = df[existing_cols]
                if 'date' in df.columns:
                    df['date'] = df['date'].astype(str)
                self._set_cache(cache_key, df.to_dict('records'))
                return df
        except Exception as e:
            print(f"新浪源K线失败 {symbol}: {e}")

        # 方案2: 东方财富源 stock_zh_a_hist（降级）
        try:
            df = self._retry_request(ak.stock_zh_a_hist, symbol=symbol, period=period,
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
        except Exception as e:
            print(f"东方财富源K线失败 {symbol}: {e}")

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

    def get_new_stocks(self, days=400):
        """获取次新股列表（上市时间较短，新浪源）

        返回 6 位代码列表。次新股策略的固定池会随时间过期
        （2024-2025 的股票到 2026 年已不算次新），动态获取让池子保持新鲜。
        """
        cache_key = f"new_stocks_v2_{days}"
        cache = self._get_cache(cache_key, days=3)
        if cache:
            return cache
        try:
            df = self.wrap_akshare(ak.stock_zh_a_new)
            if df is not None and not df.empty and 'code' in df.columns:
                # 只保留沪深 A 股（60/00/30/68 开头），排除北交所（8/4/920）
                # —— 北交所涨跌幅 ±30%、流动性差、K线支持不完整，不适合纳入
                codes = [
                    str(c) for c in df['code'].tolist()
                    if str(c).isdigit() and len(str(c)) == 6
                    and str(c)[0] in ('6', '0', '3')
                ]
                if codes:
                    self._set_cache(cache_key, codes)
                    print(f"次新股列表获取成功: {len(codes)} 只")
                    return codes
        except Exception as e:
            print(f"获取次新股列表失败: {e}")
        return []

    # ==================== 财务指标 ====================

    def get_financial_indicator(self, symbol):
        """获取财务指标：ROE、ROIC、资产负债率、现金流等
        优先用新浪财务摘要（含 ROIC），降级用同花顺、东方财富接口
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

        def to_frac(v):
            """把百分数（10.57 或 '10.57%'）转成小数 0.1057。"""
            if v in (None, ''):
                return 0
            if isinstance(v, str) and '%' in v:
                return self._safe_float(v.replace('%', ''), 0) / 100
            return self._safe_float(v, 0) / 100

        # 方案1: 新浪财务摘要（含 ROIC / 毛利率 / 资产负债率）
        try:
            values = self._fetch_sina_financial_abstract(symbol)
            if values:
                roe = 0
                for col in ['净资产收益率(ROE)', '净资产收益率_平均', '摊薄净资产收益率']:
                    if values.get(col) not in (None, ''):
                        roe = to_frac(values.get(col))
                        break
                roic_raw = values.get('投入资本回报率')
                gross_raw = values.get('毛利率')
                net_raw = values.get('销售净利率')
                debt_raw = values.get('资产负债率')
                current_raw = values.get('流动比率')
                data = {
                    'roe': roe,
                    'roic': to_frac(roic_raw) if roic_raw not in (None, '') else 0,
                    'debt_ratio': to_frac(debt_raw) if debt_raw not in (None, '') else 0,
                    'current_ratio': self._safe_float(current_raw, 0) if current_raw not in (None, '') else 0,
                    'gross_margin': to_frac(gross_raw) if gross_raw not in (None, '') else 0,
                    'net_margin': to_frac(net_raw) if net_raw not in (None, '') else 0,
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"新浪财务摘要失败 {symbol}: {e}")

        try:
            # 方案2: 同花顺财务摘要（稳定可用，无 ROIC）
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

                roic_value = 0
                roic_cols = ['投入资本回报率', '投入资本回报率(%)', 'ROIC(%)']
                for col in roic_cols:
                    if col in latest and latest[col] is not None:
                        roic_value = safe_pct(latest.get(col, 0))
                        break

                gross_margin_value = 0
                margin_cols = ['毛利率', '销售毛利率', '毛利率(%)']
                for col in margin_cols:
                    if col in latest and latest[col] is not None:
                        gross_margin_value = safe_pct(latest.get(col, 0))
                        break

                data = {
                    'roe': roe_value,
                    'roic': roic_value,
                    'debt_ratio': safe_pct(latest.get('资产负债率', 0)),
                    'current_ratio': self._safe_float(latest.get('流动比率', 0)),
                    'gross_margin': gross_margin_value,
                    'net_margin': safe_pct(latest.get('销售净利率', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"同花顺财务指标失败 {symbol}: {e}")

        # 方案3: 东方财富财务分析指标（降级，需带市场后缀）
        try:
            secu_code = self._to_secu_code(symbol)
            if not secu_code:
                return {}
            df = ak.stock_financial_analysis_indicator_em(symbol=secu_code)
            if df is not None and not df.empty:
                latest = df.iloc[0].to_dict()
                data = {
                    'roe': to_frac(latest.get('ROE_DILUTED', 0)),
                    'roic': 0,
                    'debt_ratio': 0,
                    'current_ratio': 0,
                    'gross_margin': to_frac(latest.get('GROSS_PROFIT_RATIO', 0)),
                    'net_margin': to_frac(latest.get('NET_PROFIT_RATIO', 0)),
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"东方财富财务指标失败 {symbol}: {e}")
        return {}

    def _to_secu_code(self, symbol):
        """6 位代码转东财 SECUCODE（600519 -> 600519.SH）。"""
        symbol = str(symbol)
        if len(symbol) != 6 or not symbol.isdigit():
            return ""
        if symbol.startswith(('60', '68', '9')):
            return f"{symbol}.SH"
        if symbol.startswith(('00', '30', '20')):
            return f"{symbol}.SZ"
        if symbol.startswith(('43', '83', '87', '92')):
            return f"{symbol}.BJ"
        return ""

    def _fetch_sina_financial_abstract(self, symbol):
        """自请求新浪财务摘要（支持沪深两市），返回最新报告期 {指标名: 值}。"""
        import requests

        symbol = str(symbol)
        if symbol[0] in '69':
            prefix = 'sh'
        elif symbol[0] in '03':
            prefix = 'sz'
        else:
            prefix = 'bj'
        url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
        params = {
            "paperCode": prefix + symbol,
            "source": "gjzb",
            "type": "0",
            "page": "1",
            "num": "1000",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        report_list = resp.json().get("result", {}).get("data", {}).get("report_list", {})
        if not report_list:
            return {}
        latest_key = max(report_list.keys())
        values = {}
        for item in report_list[latest_key].get("data", []):
            title = item.get("item_title")
            if title:
                values[title] = item.get("item_value")
        return values

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

        # 方案2: 东财快照（共享快照，本地过滤）
        try:
            df = self._get_spot_em_snapshot()
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
        except Exception as e:
            print(f"东财实时行情估值失败 {symbol}: {e}")
        # 方案3: 同花顺财务数据 + 历史K线计算 PE/PB
        # 注：新浪全市场快照不含市盈率/市净率列，不能作为估值来源。
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

        # 方案4: 新浪快照（仅当包含市盈率列时兜底，不产生全 0 估值）
        try:
            df = self._get_spot_sina_snapshot()
            if df is not None and not df.empty and '市盈率-动态' in df.columns:
                sina_symbol = f"sz{symbol}" if not symbol.startswith('6') else f"sh{symbol}"
                stock_spot = df[df['代码'] == sina_symbol]
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
        except Exception as e:
            print(f"新浪实时行情估值失败 {symbol}: {e}")
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

    def get_stock_news(self):
        """获取财经新闻，主接口失败时依次降级到财新数据通、财联社电报、富途快讯。

        同实例内缓存结果，避免重复触发 stock_news_em 的 ArrowInvalid 解析错误。
        """
        if self._stock_news_cache is not None:
            return self._stock_news_cache

        # 1) 东方财富（列名天然匹配策略）
        try:
            df = self.wrap_akshare(ak.stock_news_em)
            if df is not None and not df.empty:
                self._stock_news_cache = df
                return df
        except Exception as e:
            print(f"东方财富新闻获取失败，尝试备用接口: {e}")

        # 2) 财新数据通
        try:
            df = self.wrap_akshare(ak.stock_news_main_cx)
            if df is not None and not df.empty:
                normalized = pd.DataFrame({
                    "关键词": df.get("tag", pd.Series("", index=df.index)).fillna(""),
                    "新闻标题": df.get("summary", pd.Series("", index=df.index)).fillna(""),
                    "新闻内容": df.get("summary", pd.Series("", index=df.index)).fillna(""),
                    "文章来源": "财新数据通",
                    "发布时间": "",
                    "新闻链接": df.get("url", pd.Series("", index=df.index)).fillna(""),
                })
                self._stock_news_cache = normalized
                return normalized
        except Exception as e:
            print(f"财新数据通新闻获取失败，尝试备用接口: {e}")

        # 3) 财联社电报（有界请求，避免 akshare 内部 10 次指数退避）
        try:
            df = self.wrap_akshare(self._fetch_cls_telegraph)
            if df is not None and not df.empty:
                normalized = pd.DataFrame({
                    "关键词": pd.Series("", index=df.index),
                    "新闻标题": df.get("标题", pd.Series("", index=df.index)).fillna(""),
                    "新闻内容": df.get("内容", pd.Series("", index=df.index)).fillna(""),
                    "文章来源": "财联社",
                    "发布时间": df.get("发布时间", pd.Series("", index=df.index)).fillna("").astype(str),
                    "新闻链接": pd.Series("", index=df.index),
                })
                self._stock_news_cache = normalized
                return normalized
        except Exception as e:
            print(f"财联社电报新闻获取失败: {e}")

        # 4) 富途快讯（标题/内容/发布时间/链接）
        try:
            df = self.wrap_akshare(ak.stock_info_global_futu)
            if df is not None and not df.empty:
                normalized = pd.DataFrame({
                    "关键词": pd.Series("", index=df.index),
                    "新闻标题": df.get("标题", pd.Series("", index=df.index)).fillna(""),
                    "新闻内容": df.get("内容", pd.Series("", index=df.index)).fillna(""),
                    "文章来源": "富途快讯",
                    "发布时间": df.get("发布时间", pd.Series("", index=df.index)).fillna("").astype(str),
                    "新闻链接": df.get("链接", pd.Series("", index=df.index)).fillna(""),
                })
                self._stock_news_cache = normalized
                return normalized
        except Exception as e:
            print(f"富途快讯新闻获取失败: {e}")

        self._stock_news_cache = pd.DataFrame()
        return pd.DataFrame()

    def _fetch_cls_telegraph(self):
        """有界请求财联社电报（10s 超时，避免 akshare 内部无限退避拖慢兜底）。"""
        import requests

        url = "https://www.cls.cn/nodeapi/telegraphList"
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "referer": "https://www.cls.cn/telegraph",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", {}).get("roll_data", [])
        rows = []
        for item in data:
            ctime = item.get("ctime", 0)
            rows.append({
                "标题": str(item.get("title", "")),
                "内容": str(item.get("content", "")),
                "发布时间": (
                    datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
                    if ctime else ""
                ),
            })
        return pd.DataFrame(rows)

    def get_limit_up_list(self, date=None):
        """获取涨停板股票列表，主接口失败时尝试强势股池兜底。

        统一走 wrap_akshare，便于体检插桩观测与网络快速熔断。
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        cache_key = f"limitup_{date}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)

        # 尝试多个涨跌停接口
        funcs_to_try = [
            ('ak.stock_zt_pool_em', lambda: self.wrap_akshare(ak.stock_zt_pool_em, date=date)),
            ('ak.stock_zt_pool_strong_em', lambda: self.wrap_akshare(ak.stock_zt_pool_strong_em, date=date)),
        ]

        for func_name, func in funcs_to_try:
            try:
                df = func()
                if df is not None and not df.empty:
                    self._set_cache(cache_key, df.to_dict('records'))
                    return df
            except Exception as e:
                print(f"{func_name} 获取涨停板失败: {e}")
                continue

        print("获取涨停板失败: 所有接口均不可用")
        return pd.DataFrame()

    def get_dragon_tiger_list(self, date=None):
        """获取龙虎榜数据（统一列名：代码/名称/净买入额[万元]）

        东财接口原始列为"龙虎榜净买额"（元），策略按"净买入额"解析且
        阈值以万元计（min_net_buy=500），这里统一映射+换算，否则
        策略即使拿到数据也解析不出（net_buy=0 被过滤）。
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        cache_key = f"lhb_v2_{date}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        try:
            df = ak.stock_lhb_detail_em(start_date=date, end_date=date)
            if df is not None and not df.empty:
                out = pd.DataFrame({
                    '代码': df['代码'],
                    '名称': df['名称'],
                    # 东财单位为元，策略阈值以万元计 -> 换算
                    '净买入额': df['龙虎榜净买额'] / 10000.0,
                })
                self._set_cache(cache_key, out.to_dict('records'))
                return out
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
                except Exception:
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
