# -*- coding: utf-8 -*-
"""
AKShare数据封装模块
提供A股行情、财务数据、北向资金等数据获取
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os

class AKShareHelper:
    """AKShare数据助手"""
    
    def __init__(self, cache_dir="data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache(self, key, days=1):
        """获取缓存"""
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        if os.path.exists(cache_file):
            file_time = os.path.getmtime(cache_file)
            if (datetime.now().timestamp() - file_time) < days * 86400:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        return None
    
    def _set_cache(self, key, data):
        """设置缓存"""
        cache_file = os.path.join(self.cache_dir, f"{key}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    
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
    
    def get_history_kline(self, symbol, period="daily", days=60):
        """获取历史K线"""
        cache_key = f"kline_{symbol}_{period}_{days}"
        cache = self._get_cache(cache_key, days=1)
        if cache:
            return pd.DataFrame(cache)
        
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust="qfq")
            df = df.tail(days)
            df.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount', 'amplitude']
            self._set_cache(cache_key, df.to_dict('records'))
            return df
        except Exception as e:
            print(f"获取历史K线失败 {symbol}: {e}")
            return pd.DataFrame()
    
    def get_financial_data(self, symbol):
        """获取财务数据"""
        cache_key = f"financial_{symbol}"
        cache = self._get_cache(cache_key, days=30)
        if cache:
            return cache
        
        try:
            # 获取ROE、PE、PB等
            df = ak.stock_financial_analysis_indicator(symbol=symbol)
            if not df.empty:
                data = {
                    'roe': df['净资产收益率(%)'].iloc[0] if '净资产收益率(%)' in df.columns else None,
                    'roic': df['投入资本回报率(%)'].iloc[0] if '投入资本回报率(%)' in df.columns else None,
                }
                self._set_cache(cache_key, data)
                return data
        except Exception as e:
            print(f"获取财务数据失败 {symbol}: {e}")
        return {}
    
    def get_financial_indicator_all(self):
        """获取所有股票的财务指标（用于因子选股）"""
        cache = self._get_cache("financial_all", days=7)
        if cache:
            return pd.DataFrame(cache)
        
        try:
            # 获取股票基本面数据
            df = ak.stock_board_industry_name_em()
            # 获取行业成分股
            all_stocks = []
            for _, row in df.iterrows():
                try:
                    industry = row['板块名称']
                    stocks = ak.stock_board_industry_cons_em(symbol=industry)
                    if not stocks.empty:
                        stocks['industry'] = industry
                        all_stocks.append(stocks)
                except:
                    continue
            if all_stocks:
                result = pd.concat(all_stocks, ignore_index=True)
                self._set_cache("financial_all", result.to_dict('records'))
                return result
        except Exception as e:
            print(f"获取财务指标失败: {e}")
        return pd.DataFrame()
    
    def get_north_flow(self):
        """获取北向资金流向"""
        cache = self._get_cache("north_flow", days=1)
        if cache:
            return pd.DataFrame(cache)
        
        try:
            df = ak.stock_hsgt_north_flow_hist_em(symbol="北向资金")
            df.columns = ['date', 'north_inflow', 'hgt_inflow', 'sgt_inflow', 'north_hold', 'hgt_hold', 'sgt_hold']
            self._set_cache("north_flow", df.tail(30).to_dict('records'))
            return df.tail(30)
        except Exception as e:
            print(f"获取北向资金失败: {e}")
            return pd.DataFrame()
    
    def get_north_hold(self):
        """获取北向资金持股"""
        cache = self._get_cache("north_hold", days=1)
        if cache:
            return pd.DataFrame(cache)
        
        try:
            df = ak.stock_hsgt_hold_stock_em(symbol="北向资金")
            if not df.empty:
                self._set_cache("north_hold", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取北向持股失败: {e}")
        return pd.DataFrame()
    
    def get_limit_up(self):
        """获取涨停板数据"""
        cache = self._get_cache("limit_up", days=1)
        if cache:
            return pd.DataFrame(cache)
        
        try:
            df = ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d"))
            if not df.empty:
                self._set_cache("limit_up", df.to_dict('records'))
                return df
        except Exception as e:
            print(f"获取涨停板失败: {e}")
        return pd.DataFrame()
    
    def get_market_baojun(self):
        """获取大盘指数行情"""
        cache = self._get_cache("market_baojun", days=1)
        if cache:
            return pd.DataFrame(cache)
        
        try:
            # 上证指数、深证成指、创业板指
            symbols = ['000001', '399001', '399006']
            result = []
            for sym in symbols:
                try:
                    df = ak.stock_zh_a_hist(symbol=sym, period="daily", adjust="qfq")
                    if not df.empty:
                        latest = df.iloc[-1]
                        result.append({
                            'symbol': sym,
                            'date': latest['日期'],
                            'close': latest['收盘'],
                            'open': latest['开盘'],
                            'high': latest['最高'],
                            'low': latest['最低'],
                            'volume': latest['成交量'],
                            'pct_change': (latest['收盘'] - latest['开盘']) / latest['开盘'] * 100
                        })
                except:
                    continue
            if result:
                self._set_cache("market_baojun", result)
                return pd.DataFrame(result)
        except Exception as e:
            print(f"获取大盘指数失败: {e}")
        return pd.DataFrame()
    
    def get_index_components(self, index_code="000300"):
        """获取指数成分股"""
        cache_key = f"index_{index_code}"
        cache = self._get_cache(cache_key, days=7)
        if cache:
            return cache
        
        try:
            if index_code == "000300":
                df = ak.index_hs300_cons_sina()
            elif index_code == "000852":
                df = ak.index_zh_a_hist(symbol="中证1000")
            else:
                return []
            
            if not df.empty:
                stocks = df['代码'].tolist() if '代码' in df.columns else []
                self._set_cache(cache_key, stocks)
                return stocks
        except Exception as e:
            print(f"获取指数成分股失败: {e}")
        return []


if __name__ == "__main__":
    helper = AKShareHelper()
    # 测试
    stocks = helper.get_stock_list()
    print(f"获取股票列表: {len(stocks)} 只")
