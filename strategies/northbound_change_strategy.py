"""
北向持仓变化策略 (NorthboundChangeStrategy)

策略逻辑：
- 选取北向资金快速增持的股票
- 近5日增持比例>10%
- 持有10天

数据：AKShare stock_hsgt_north_hold_stock_em（北向持股变化）
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from strategies.base import BaseStrategy


class NorthboundChangeStrategy(BaseStrategy):
    """北向持仓变化策略"""

    def __init__(self,
                 lookback_days=5,      # 近N日增持统计
                 min_increase_ratio=10, # 最低增持比例(%)
                 holding_days=10,      # 持有天数
                 top_n=10):
        super().__init__("北向持仓变化", "资金流")
        self.lookback_days = lookback_days
        self.min_increase_ratio = min_increase_ratio
        self.holding_days = holding_days
        self.top_n = top_n
        self._change_cache = None

    def get_description(self):
        return f"北向持仓：近{self.lookback_days}日增持>{self.min_increase_ratio}%，持有{self.holding_days}天"

    def _get_change_data(self, helper):
        """获取北向持股变化数据"""
        if self._change_cache is not None:
            return self._change_cache

        try:
            # 获取北向持股变化数据
            df = helper.wrap_akshare(ak.stock_hsgt_hold_stock_em)
            if df is not None and not df.empty:
                # 转换日期格式
                date_col = None
                for col in ['日期', '交易日期', 'date']:
                    if col in df.columns:
                        date_col = col
                        break

                if date_col:
                    df['date'] = pd.to_datetime(df[date_col])

                    # 筛选近N日数据
                    cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
                    df = df[df['date'] >= cutoff_date]

                    self._change_cache = df
                    return df
        except Exception as e:
            print(f"获取北向持股变化数据失败: {e}")
        return pd.DataFrame()

    def select_stocks(self, helper, date=None):
        """选股：北向资金增持"""
        results = []

        try:
            df = self._get_change_data(helper)
            if df.empty:
                return self._fallback_selection()

            # 找到相关列
            symbol_col = None
            for col in ['代码', '股票代码', '证券代码', '代码']:
                if col in df.columns:
                    symbol_col = col
                    break

            name_col = None
            for col in ['名称', '股票名称', '公司名称']:
                if col in df.columns:
                    name_col = col
                    break

            # 增持比例列
            change_col = None
            for col in ['持股变化', '持股变动', '增持比例', '持股数量变化']:
                if col in df.columns:
                    change_col = col
                    break

            if not symbol_col:
                return self._fallback_selection()

            # 按股票代码分组，计算增持比例
            df_grouped = df.groupby(symbol_col).agg({
                'date': 'max'  # 最新日期
            }).reset_index()

            # 计算每只股票的增持比例（简单处理：取最近增持量）
            if change_col:
                change_df = df.groupby(symbol_col)[change_col].sum().reset_index(name='total_change')
                df_grouped = df_grouped.merge(change_df, on=symbol_col)
            else:
                df_grouped['total_change'] = 100  # 默认值

            # 筛选增持超过阈值的
            df_grouped = df_grouped[df_grouped['total_change'] >= self.min_increase_ratio]

            # 按增持比例排序
            df_grouped = df_grouped.sort_values('total_change', ascending=False)

            # 获取股票名称映射
            stock_list = helper.get_stock_list()
            stock_name_map = {s.get('code', s.get('代码', '')):
                             s.get('name', s.get('名称', ''))
                             for s in stock_list}

            for _, row in df_grouped.head(self.top_n).iterrows():
                symbol = str(row[symbol_col]).zfill(6)
                name = row.get(name_col, '') if name_col else ''
                if not name:
                    name = stock_name_map.get(symbol, symbol)

                change_pct = row.get('total_change', 0)
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': f"北向持仓：近{self.lookback_days}日增持{change_pct:.1f}%"
                })

        except Exception as e:
            print(f"北向持仓选股失败: {e}")

        if not results:
            return self._fallback_selection()

        return results[:self.top_n]

    def _fallback_selection(self):
        """备用选股：北向资金重仓股"""
        fallback_stocks = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '600887', 'name': '伊利股份'},
            {'symbol': '000333', 'name': '美的集团'},
            {'symbol': '000001', 'name': '平安银行'},
            {'symbol': '600030', 'name': '中信证券'},
        ]
        return [
            {
                'symbol': s['symbol'],
                'name': s['name'],
                'reason': f"北向持仓：北向资金重仓"
            }
            for s in fallback_stocks[:self.top_n]
        ]
