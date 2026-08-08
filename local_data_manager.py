# -*- coding: utf-8 -*-
"""
本地数据管理器
长期方案：将历史数据缓存到本地，完全脱离网络依赖

功能：
1. 下载并保存历史数据到本地文件
2. 自动增量更新（只下载新数据）
3. 完全离线回测模式
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')


class LocalDataManager:
    """本地数据管理器"""
    
    def __init__(self, data_dir: str = "data/local"):
        self.data_dir = data_dir
        self.db_path = os.path.join(data_dir, "market_data.db")
        self.meta_path = os.path.join(data_dir, "metadata.json")
        
        os.makedirs(data_dir, exist_ok=True)
        self._init_database()
        self._load_metadata()
    
    def _init_database(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # K线数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kline_data (
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                adjust TEXT,
                PRIMARY KEY (symbol, date, adjust)
            )
        """)
        
        # 指数数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS index_data (
                index_code TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY (index_code, date)
            )
        """)
        
        # 交易日历表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trading_days (
                date TEXT PRIMARY KEY
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_metadata(self):
        """加载元数据"""
        if os.path.exists(self.meta_path):
            with open(self.meta_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {}
    
    def _save_metadata(self):
        """保存元数据"""
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def get_stock_hist(self, symbol: str, start: str = None, end: str = None, 
                       adjust: str = "qfq") -> Optional[pd.DataFrame]:
        """从本地获取股票K线数据"""
        
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT date, open, high, low, close, volume, amount FROM kline_data WHERE symbol = ? AND adjust = ?"
        params = [symbol, adjust]
        
        if start:
            query += " AND date >= ?"
            params.append(start)
        if end:
            query += " AND date <= ?"
            params.append(end)
        
        query += " ORDER BY date"
        
        try:
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            
            if len(df) > 0:
                return df
        except Exception as e:
            print(f"查询本地数据失败: {e}")
        finally:
            conn.close()
        
        return None
    
    def save_stock_hist(self, symbol: str, data: pd.DataFrame, adjust: str = "qfq"):
        """保存股票K线数据到本地"""
        
        if data is None or len(data) == 0:
            return
        
        conn = sqlite3.connect(self.db_path)
        
        # 确保数据格式正确
        df = data.copy()
        df['symbol'] = symbol
        df['adjust'] = adjust
        
        # 重命名列
        column_map = {
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume',
            '成交额': 'amount'
        }
        df = df.rename(columns=column_map)
        
        # 只保留需要的列
        columns = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'adjust']
        for col in columns:
            if col not in df.columns:
                df[col] = 0
        
        df = df[columns]
        
        # 插入数据（替换已存在的）
        df.to_sql('kline_data', conn, if_exists='replace', index=False)
        
        # 更新元数据
        self.metadata[f"{symbol}_{adjust}"] = {
            'last_update': datetime.now().isoformat(),
            'date_range': {
                'start': str(df['date'].min()),
                'end': str(df['date'].max())
            },
            'record_count': len(df)
        }
        self._save_metadata()
        
        conn.close()
        print(f"已保存 {symbol} 的 {len(df)} 条数据")
    
    def download_and_cache(self, symbols: List[str], start: str = None, end: str = None, 
                           adjust: str = "qfq"):
        """下载并缓存股票数据"""
        
        if end is None:
            end = datetime.now().strftime('%Y%m%d')
        if start is None:
            start = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        
        print(f"开始下载 {len(symbols)} 只股票的数据...")
        print(f"时间范围: {start} - {end}")
        
        success_count = 0
        fail_count = 0
        
        for i, symbol in enumerate(symbols, 1):
            # 检查是否已有最新数据
            meta_key = f"{symbol}_{adjust}"
            if meta_key in self.metadata:
                last_end = self.metadata[meta_key].get('date_range', {}).get('end', '')
                if last_end >= end:
                    print(f"[{i}/{len(symbols)}] {symbol} 已是最新，跳过")
                    success_count += 1
                    continue
            
            # 下载数据
            try:
                data = self._download_from_source(symbol, start, end, adjust)
                if data is not None and len(data) > 0:
                    self.save_stock_hist(symbol, data, adjust)
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"[{i}/{len(symbols)}] {symbol} 下载失败: {e}")
                fail_count += 1
        
        print(f"\n下载完成: 成功 {success_count}, 失败 {fail_count}")
    
    def _download_from_source(self, symbol: str, start: str, end: str, adjust: str) -> Optional[pd.DataFrame]:
        """从网络下载数据"""
        
        # 1. 尝试 AKShare
        try:
            import akshare as ak
            if len(symbol) == 6:
                symbol_fmt = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
            else:
                symbol_fmt = symbol
            
            df = ak.stock_zh_a_hist(symbol=symbol_fmt, start_date=start, end_date=end, adjust=adjust)
            if df is not None and len(df) > 0:
                return df
        except Exception:
            pass
        
        # 2. 尝试 Baostock
        try:
            import baostock as bs
            if symbol.startswith('6'):
                bs_code = f"sh.{symbol}"
            else:
                bs_code = f"sz.{symbol}"
            
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume,amount",
                start_date=start, end_date=end,
                frequency="d", adjust="3" if adjust == "qfq" else "1"
            )
            
            data_list = []
            while rs.error_code == '0' and rs.next():
                data_list.append(rs.get_row_data())
            
            if data_list:
                df = pd.DataFrame(data_list, columns=['日期', '开盘', '最高', '最低', '收盘', '成交量', '成交额'])
                return df
        except Exception:
            pass
        
        # 3. 尝试 EFinance
        try:
            import efinance as ef
            df = ef.stock.get_quote_history(symbol, start=start, end=end)
            if df is not None and len(df) > 0:
                return df
        except Exception:
            pass
        
        return None
    
    def get_index_hist(self, index_code: str = "000001", start: str = None, end: str = None) -> Optional[pd.DataFrame]:
        """获取指数历史数据"""
        
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT date, open, high, low, close, volume FROM index_data WHERE index_code = ?"
        params = [index_code]
        
        if start:
            query += " AND date >= ?"
            params.append(start)
        if end:
            query += " AND date <= ?"
            params.append(end)
        
        query += " ORDER BY date"
        
        try:
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            if len(df) > 0:
                return df
        except Exception:
            pass
        finally:
            conn.close()
        
        return None
    
    def save_index_hist(self, index_code: str, data: pd.DataFrame):
        """保存指数数据"""
        
        if data is None or len(data) == 0:
            return
        
        conn = sqlite3.connect(self.db_path)
        
        df = data.copy()
        df['index_code'] = index_code
        
        column_map = {
            '日期': 'date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'volume'
        }
        df = df.rename(columns=column_map)
        
        columns = ['index_code', 'date', 'open', 'high', 'low', 'close', 'volume']
        for col in columns:
            if col not in df.columns:
                df[col] = 0
        
        df = df[columns]
        df.to_sql('index_data', conn, if_exists='replace', index=False)
        
        conn.close()
        print(f"已保存指数 {index_code} 的 {len(df)} 条数据")
    
    def download_index(self, indices: List[str] = None):
        """下载指数数据"""
        
        if indices is None:
            indices = ['000001', '399001', '399006']  # 上证、深证、创业板
        
        print(f"开始下载 {len(indices)} 个指数的数据...")
        
        for index_code in indices:
            try:
                # 尝试各数据源
                data = None
                
                try:
                    import akshare as ak
                    df = ak.stock_zh_index_daily(symbol=f"sh{index_code}")
                    if df is not None:
                        data = df
                except Exception:
                    pass
                
                if data is None:
                    try:
                        import baostock as bs
                        if index_code == '000001':
                            bs_code = 'sh.000001'
                        elif index_code == '399001':
                            bs_code = 'sz.399001'
                        else:
                            bs_code = f'sh.{index_code}'
                        
                        rs = bs.query_history_k_data_plus(
                            bs_code,
                            "date,open,high,low,close,volume",
                            start_date='19900101',
                            frequency="d"
                        )
                        
                        data_list = []
                        while rs.error_code == '0' and rs.next():
                            data_list.append(rs.get_row_data())
                        
                        if data_list:
                            data = pd.DataFrame(data_list, columns=['日期', '开盘', '最高', '最低', '收盘', '成交量'])
                    except Exception:
                        pass
                
                if data is not None:
                    self.save_index_hist(index_code, data)
                else:
                    print(f"指数 {index_code} 下载失败")
                    
            except Exception as e:
                print(f"指数 {index_code} 下载异常: {e}")
        
        print("指数下载完成")
    
    def get_status(self) -> Dict:
        """获取本地数据状态"""
        conn = sqlite3.connect(self.db_path)
        
        # 统计股票数量
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM kline_data")
        stock_count = cursor.fetchone()[0]
        
        # 统计指数数量
        cursor.execute("SELECT COUNT(DISTINCT index_code) FROM index_data")
        index_count = cursor.fetchone()[0]
        
        # 统计K线记录数
        cursor.execute("SELECT COUNT(*) FROM kline_data")
        kline_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'stock_count': stock_count,
            'index_count': index_count,
            'kline_count': kline_count,
            'data_dir': self.data_dir,
            'metadata': self.metadata
        }
    
    def preload_common_stocks(self, count: int = 100):
        """预加载常用股票数据"""
        
        # 获取沪深300成分股
        try:
            import akshare as ak
            df = ak.index_zh_a_hist_min_em(symbol="000300", period="日", start_date="20230101")
            
            # 取成交额最大的100只股票作为常用股票
            common_symbols = [
                '600519', '600036', '601318', '000858', '600276',  # 茅台、招行、平安、五粮液、恒瑞
                '601166', '600887', '000333', '002415', '600030',  # 兴业、伊利、美的、海康、中信
                '601888', '600009', '601012', '002714', '600031',  # 中免、上海机场、隆基、牧原、三一
                '600028', '601398', '601288', '600000', '601328',  # 中石化、工行、农行、浦发、交通
                '000001', '601818', '600016', '600837', '601088',  # 平安银行、光大、民生、海通、神华
            ]
            
            # 补充到100只
            if len(common_symbols) < count:
                # 添加更多大盘股
                df_stocks = ak.stock_zh_a_spot_em()
                if df_stocks is not None:
                    top_stocks = df_stocks.nlargest(count * 2, '成交额')
                    for symbol in top_stocks['代码'].tolist():
                        if symbol not in common_symbols and len(common_symbols) < count:
                            common_symbols.append(symbol)
            
            self.download_and_cache(common_symbols)
            
        except Exception as e:
            print(f"预加载失败: {e}")


# 便捷函数
def create_local_manager() -> LocalDataManager:
    """创建本地数据管理器"""
    return LocalDataManager()


def init_local_data():
    """初始化本地数据（一次性设置）"""
    manager = LocalDataManager()
    
    # 下载指数数据
    print("=" * 50)
    print("初始化本地数据")
    print("=" * 50)
    
    # 1. 下载主要指数
    manager.download_index(['000001', '399001', '399006', '000300', '000016'])
    
    # 2. 预加载常用股票
    print("\n预加载常用股票数据...")
    manager.preload_common_stocks(100)
    
    # 3. 显示状态
    status = manager.get_status()
    print("\n" + "=" * 50)
    print("本地数据状态")
    print("=" * 50)
    print(f"股票数量: {status['stock_count']}")
    print(f"K线记录: {status['kline_count']}")
    print(f"数据目录: {status['data_dir']}")
    
    return manager
