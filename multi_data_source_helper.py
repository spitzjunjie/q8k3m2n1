# -*- coding: utf-8 -*-
"""
多数据源助手
中期方案：自动切换多个数据源，解决网络不稳定问题

数据源优先级：
1. AKShare（主力）
2. Baostock（备用）
3. Tushare（备用）
4. EFinance（备用）
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time

sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')


class MultiDataSourceHelper:
    """多数据源助手 - 自动切换数据源"""
    
    def __init__(self):
        self.current_source = None
        self.source_priority = ['akshare', 'baostock', 'efinance', 'tushare']
        self.cache_dir = "data/cache"
        self.cache = {}  # 内存缓存
        
        # 初始化数据源
        self._init_sources()
        
    def _init_sources(self):
        """初始化各数据源"""
        self.sources = {}
        
        # 1. AKShare
        try:
            import akshare as ak
            self.sources['akshare'] = {
                'module': ak,
                'enabled': True
            }
        except Exception:
            self.sources['akshare'] = {'enabled': False}
        
        # 2. Baostock（免费，无需token）
        try:
            import baostock as bs
            bs.login()
            self.sources['baostock'] = {
                'module': bs,
                'enabled': True
            }
        except Exception:
            self.sources['baostock'] = {'enabled': False}
        
        # 3. EFinance
        try:
            import efinance as ef
            self.sources['efinance'] = {
                'module': ef,
                'enabled': True
            }
        except Exception:
            self.sources['efinance'] = {'enabled': False}
        
        # 4. Tushare
        try:
            import tushare as ts
            # 使用环境变量或默认token
            token = os.environ.get('TUSHARE_TOKEN', 'your_token_here')
            if token != 'your_token_here':
                ts.set_token(token)
            self.sources['tushare'] = {
                'module': ts,
                'pro': ts.pro_api() if token != 'your_token_here' else None,
                'enabled': token != 'your_token_here'
            }
        except Exception:
            self.sources['tushare'] = {'enabled': False}
        
        # 统计可用数据源
        available = [k for k, v in self.sources.items() if v.get('enabled')]
        print(f"[多数据源] 可用数据源: {available}")
        
        if available:
            self.current_source = available[0]
    
    def get_stock_hist(self, symbol: str, start: str = None, end: str = None, adjust: str = "qfq") -> Optional[any]:
        """获取股票历史K线（自动切换数据源）"""
        
        # 检查缓存
        cache_key = f"{symbol}_{start}_{end}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # 按优先级尝试各数据源
        for source_name in self.source_priority:
            if not self.sources.get(source_name, {}).get('enabled'):
                continue
            
            try:
                result = self._get_from_source(source_name, symbol, start, end, adjust)
                if result is not None and len(result) > 0:
                    self.current_source = source_name
                    self.cache[cache_key] = result
                    return result
            except Exception as e:
                print(f"[{source_name}] 获取{symbol}失败: {str(e)[:50]}")
                continue
        
        return None
    
    def _get_from_source(self, source: str, symbol: str, start: str, end: str, adjust: str):
        """从指定数据源获取数据"""
        
        if source == 'akshare':
            import akshare as ak
            # 转换symbol格式
            if len(symbol) == 6:
                if symbol.startswith('6'):
                    symbol_fmt = f"sh{symbol}"
                else:
                    symbol_fmt = f"sz{symbol}"
            else:
                symbol_fmt = symbol
            
            df = ak.stock_zh_a_hist(symbol=symbol_fmt, start_date=start, end_date=end, adjust=adjust)
            if df is not None and '日期' in df.columns:
                return df
            return None
        
        elif source == 'baostock':
            import baostock as bs
            # 转换symbol格式
            if symbol.startswith('6'):
                bs_code = f"sh.{symbol}"
            else:
                bs_code = f"sz.{symbol}"
            
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount",
                start_date=start, end_date=end,
                frequency="d", adjust="qfq"
            )
            
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())
            
            if data_list:
                import pandas as pd
                df = pd.DataFrame(data_list, columns=['日期', '开盘', '最高', '最低', '收盘', '成交量', '成交额'])
                return df
            return None
        
        elif source == 'efinance':
            import efinance as ef
            df = ef.stock.get_quote_history(symbol, start=start, end=end)
            if df is not None and '日期' in df.columns:
                return df
            return None
        
        elif source == 'tushare':
            ts_pro = self.sources['tushare'].get('pro')
            if not ts_pro:
                return None
            
            # 转换symbol格式
            if symbol.startswith('6'):
                ts_code = f"{symbol}.SH"
            else:
                ts_code = f"{symbol}.SZ"
            
            df = ts_pro.daily(ts_code=ts_code, start_date=start, end_date=end)
            if df is not None:
                df['日期'] = df['trade_date']
                return df
            return None
        
        return None
    
    def get_realtime_price(self, symbol: str) -> Optional[float]:
        """获取实时价格（多数据源）"""
        
        for source in self.source_priority:
            if not self.sources.get(source, {}).get('enabled'):
                continue
            
            try:
                if source == 'akshare':
                    import akshare as ak
                    if len(symbol) == 6:
                        symbol_fmt = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
                    else:
                        symbol_fmt = symbol
                    
                    df = ak.stock_zh_a_spot_em()
                    if df is not None:
                        row = df[df['代码'] == symbol]
                        if not row.empty:
                            return float(row['最新价'].values[0])
                
                elif source == 'efinance':
                    import efinance as ef
                    quotes = ef.stock.get_realtime_quotes(symbol)
                    if quotes is not None and len(quotes) > 0:
                        return float(quotes.iloc[0]['最新价'])
                
                elif source == 'baostock':
                    import baostock as bs
                    if symbol.startswith('6'):
                        bs_code = f"sh.{symbol}"
                    else:
                        bs_code = f"sz.{symbol}"
                    
                    rs = bs.query_real_time_quotes(bs_code)
                    if rs.error_code == '0' and rs.next():
                        return float(rs.get_row_data()[3])  # 当前价
                        
            except Exception as e:
                continue
        
        return None
    
    def get_index_hist(self, index_code: str = "000001", start: str = None, end: str = None) -> Optional[any]:
        """获取指数历史数据"""
        
        for source in self.source_priority:
            if not self.sources.get(source, {}).get('enabled'):
                continue
            
            try:
                if source == 'akshare':
                    import akshare as ak
                    df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
                    if df is not None:
                        if start:
                            df = df[df['日期'] >= start]
                        if end:
                            df = df[df['日期'] <= end]
                        return df
                
                elif source == 'baostock':
                    import baostock as bs
                    if index_code == "000001":
                        bs_code = "sh.000001"
                    else:
                        bs_code = f"sh.{index_code}"
                    
                    rs = bs.query_history_k_data_plus(
                        bs_code,
                        "date,open,high,low,close,volume",
                        start_date=start, end_date=end,
                        frequency="d"
                    )
                    
                    data_list = []
                    while rs.error_code == '0' and rs.next():
                        data_list.append(rs.get_row_data())
                    
                    if data_list:
                        import pandas as pd
                        df = pd.DataFrame(data_list, columns=['日期', '开盘', '最高', '最低', '收盘', '成交量'])
                        return df
                        
            except Exception:
                continue
        
        return None
    
    def get_trading_days(self, start: str, end: str) -> List[str]:
        """获取交易日列表"""
        df = self.get_index_hist("000001", start, end)
        if df is not None:
            return df['日期'].tolist()
        return []
    
    def close(self):
        """关闭连接"""
        try:
            import baostock as bs
            bs.logout()
        except Exception:
            pass


# 便捷函数
def create_multi_source_helper() -> MultiDataSourceHelper:
    """创建多数据源助手"""
    return MultiDataSourceHelper()
