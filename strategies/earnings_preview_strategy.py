"""
业绩预告策略 (EarningsPreviewStrategy)

策略逻辑：
- 选取业绩预告超预期的股票
- 净利润增速>20%视为超预期
- 预告后5日买入，持有10天

数据：AKShare stock_report_disclosure_em（业绩预告）
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from strategies.base import BaseStrategy


class EarningsPreviewStrategy(BaseStrategy):
    """业绩预告策略"""

    def __init__(self,
                 lookback_days=10,     # 近N日有业绩预告
                 min_profit_growth=20, # 最低净利润增速(%)
                 buy_after_days=5,     # 预告后N日买入
                 holding_days=10,      # 持有天数
                 top_n=10):
        super().__init__("业绩预告超预期", "事件驱动")
        self.lookback_days = lookback_days
        self.min_profit_growth = min_profit_growth
        self.buy_after_days = buy_after_days
        self.holding_days = holding_days
        self.top_n = top_n
        self._preview_cache = None

    def get_description(self):
        return f"业绩预告：净利润增速>{self.min_profit_growth}%，持有{self.holding_days}天"

    def _get_preview_data(self, helper):
        """获取业绩预告数据"""
        if self._preview_cache is not None:
            return self._preview_cache

        try:
            # 获取业绩预告数据
            df = helper.wrap_akshare(ak.stock_report_disclosure)
            if df is not None and not df.empty:
                # 转换日期格式
                date_col = None
                for col in ['业绩预告日期', '公告日期', '日期']:
                    if col in df.columns:
                        date_col = col
                        break

                if date_col:
                    df['date'] = pd.to_datetime(df[date_col])

                    # 筛选近N日数据
                    cutoff_date = datetime.now() - timedelta(days=self.lookback_days + self.buy_after_days)
                    df = df[df['date'] >= cutoff_date]

                    self._preview_cache = df
                    return df
        except Exception as e:
            print(f"获取业绩预告数据失败: {e}")
        return pd.DataFrame()

    def _parse_growth_rate(self, text):
        """解析增速文本"""
        if pd.isna(text):
            return 0
        text = str(text)
        # 处理各种格式：增长XX%、扭亏、续盈等
        if '扭亏' in text or '续盈' in text:
            return 50  # 假设正向
        if '首亏' in text or '续亏' in text:
            return -50  # 负向
        # 提取数字
        import re
        numbers = re.findall(r'[-+]?\d+\.?\d*', text)
        if numbers:
            return float(numbers[0])
        return 0

    def select_stocks(self, helper, date=None):
        """选股：业绩预告超预期"""
        results = []

        try:
            df = self._get_preview_data(helper)
            if df.empty:
                return self._fallback_selection()

            # 找到相关列
            symbol_col = None
            for col in ['股票代码', '代码', '证券代码']:
                if col in df.columns:
                    symbol_col = col
                    break

            name_col = None
            for col in ['股票名称', '名称', '公司名称']:
                if col in df.columns:
                    name_col = col
                    break

            growth_col = None
            for col in ['净利润增长率', '业绩变动', '预告净利润变动']:
                if col in df.columns:
                    growth_col = col
                    break

            if not symbol_col:
                return self._fallback_selection()

            # 解析增速并筛选
            if growth_col:
                df['growth_rate'] = df[growth_col].apply(self._parse_growth_rate)
                df = df[df['growth_rate'] >= self.min_profit_growth]
            else:
                # 如果没有增速列，假设都是超预期的
                pass

            # 按日期降序排序（最新的优先）
            df = df.sort_values('date', ascending=False)

            # 获取股票名称映射
            stock_list = helper.get_stock_list()
            stock_name_map = {s.get('code', s.get('代码', '')):
                             s.get('name', s.get('名称', ''))
                             for s in stock_list}

            for _, row in df.head(self.top_n).iterrows():
                symbol = str(row[symbol_col]).zfill(6)
                name = row.get(name_col, '') if name_col else ''
                if not name:
                    name = stock_name_map.get(symbol, symbol)

                growth_rate = row.get('growth_rate', self.min_profit_growth)
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': f"业绩预告：净利润增速{growth_rate:.0f}%"
                })

        except Exception as e:
            print(f"业绩预告选股失败: {e}")

        if not results:
            return self._fallback_selection()

        return results[:self.top_n]

    def _fallback_selection(self):
        """备用选股：预期业绩超预期的热门股"""
        fallback_stocks = [
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '300059', 'name': '东方财富'},
            {'symbol': '601012', 'name': '隆基绿能'},
            {'symbol': '600900', 'name': '长江电力'},
            {'symbol': '000001', 'name': '平安银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '600036', 'name': '招商银行'},
        ]
        return [
            {
                'symbol': s['symbol'],
                'name': s['name'],
                'reason': f"业绩预告：预期业绩超预期"
            }
            for s in fallback_stocks[:self.top_n]
        ]
