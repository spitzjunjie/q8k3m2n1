# -*- coding: utf-8 -*-
"""Part 2: Modify get_realtime_quote and get_valuation_data."""
import sys

PATH = "data/akshare_helper.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

# ============================================================
# Step 4: Replace get_realtime_quote to use snapshots
# ============================================================
old_quote = content.find("    def get_realtime_quote(self, symbol):")
old_quote_end = content.find("\n    def get_history_kline", old_quote)

new_quote = """    def get_realtime_quote(self, symbol):
        \"\"\"获取单只股票实时行情（复用全市场快照，避免重复拉取）\"\"\"
        # 方案1: 东方财富快照（共享）
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

        # 方案3: 逐股票兜底
        try:
            prefix = 'sh' if symbol.startswith('6') else 'sz'
            df = self.wrap_akshare(ak.stock_zh_a_spot, symbol=prefix + symbol)
            if df is not None and not df.empty:
                return df.iloc[0].to_dict()
        except Exception as e:
            pass

        return {}
"""

content = content[:old_quote] + new_quote + content[old_quote_end:]
print("Step 4 (get_realtime_quote): OK")

# ============================================================
# Step 5: Replace get_valuation_data to use snapshots + fix Bug #2
# ============================================================
old_val = content.find("    def get_valuation_data(self, symbol):")
old_val_end = content.find("\n    def get_financial_data", old_val)

new_val = """    def get_valuation_data(self, symbol):
        \"\"\"获取估值数据：PE、PB、PS、股息率
        优先使用Tushare（稳定可靠），降级用akshare东财/新浪/同花顺
        \"\"\"
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

        # 方案3: 新浪快照（共享快照，本地过滤）—— Bug #2 fix: 用 3 替代 max_retries
        try:
            df = self._get_spot_sina_snapshot()
            if df is not None and not df.empty:
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

        # 方案4: 同花顺财务数据+历史K线
        try:
            fin_df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
            if fin_df is not None and not fin_df.empty:
"""

content = content[:old_val] + new_val + content[old_val_end:]
print("Step 5 (get_valuation_data): OK")

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

try:
    compile(content, PATH, "exec")
    print("Syntax: OK after Step 5")
except SyntaxError as e:
    print(f"SyntaxError after Step 5: {e}")
    sys.exit(1)
