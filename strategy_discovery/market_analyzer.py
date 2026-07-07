# -*- coding: utf-8 -*-
"""
市场环境分析器
分析当前市场环境，为LLM提供上下文
"""


class MarketAnalyzer:
    """市场环境分析器

    分析维度：
    1. 大盘涨跌幅（沪深300近20日）
    2. 行业涨跌幅排名
    3. 北向资金净流入
    4. 涨停板数量/跌停板数量
    5. 市场风格（大盘vs小盘、价值vs成长）
    """

    def analyze(self, helper):
        """分析当前市场环境

        Args:
            helper: AKShareHelper实例

        Returns:
            str: 市场环境描述文本（供LLM prompt使用）
        """
        sections = []

        # 1. 大盘走势
        index_info = self._analyze_index(helper)
        sections.append(index_info)

        # 2. 市场风格
        style_info = self._analyze_market_style(helper)
        sections.append(style_info)

        # 3. 北向资金
        north_info = self._analyze_north_flow(helper)
        sections.append(north_info)

        # 4. 涨停情况
        limit_up_info = self._analyze_limit_up(helper)
        sections.append(limit_up_info)

        # 5. 热点板块
        sector_info = self._analyze_sectors(helper)
        sections.append(sector_info)

        return "\n\n".join(sections)

    def _analyze_index(self, helper):
        """分析大盘指数"""
        try:
            df = helper.get_history_kline("000300", days=30)
            if df.empty or len(df) < 20:
                return "## 大盘走势\n数据获取失败"

            close = df['close']
            ret_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100
            ret_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100
            current = close.iloc[-1]

            trend = "上涨" if ret_20d > 2 else ("下跌" if ret_20d < -2 else "震荡")

            return f"""## 大盘走势
- 沪深300当前: {current:.2f}
- 近5日涨幅: {ret_5d:+.2f}%
- 近20日涨幅: {ret_20d:+.2f}%
- 趋势判断: {trend}"""
        except Exception as e:
            return f"## 大盘走势\n分析失败: {e}"

    def _analyze_market_style(self, helper):
        """分析市场风格（大盘vs小盘，价值vs成长）"""
        try:
            # 用沪深300 vs 中证500判断大小盘风格
            hs300 = helper.get_history_kline("000300", days=20)
            zz500 = helper.get_history_kline("000905", days=20)

            if hs300.empty or zz500.empty:
                return "## 市场风格\n数据不足"

            hs300_ret = (hs300['close'].iloc[-1] / hs300['close'].iloc[0] - 1) * 100
            zz500_ret = (zz500['close'].iloc[-1] / zz500['close'].iloc[0] - 1) * 100

            if hs300_ret > zz500_ret:
                style = "大盘占优"
            else:
                style = "小盘占优"

            return f"""## 市场风格
- 沪深300近20日: {hs300_ret:+.2f}%
- 中证500近20日: {zz500_ret:+.2f}%
- 风格判断: {style}"""
        except Exception as e:
            return f"## 市场风格\n分析失败: {e}"

    def _analyze_north_flow(self, helper):
        """分析北向资金"""
        try:
            df = helper.get_north_flow()
            if df.empty:
                return "## 北向资金\n数据获取失败"

            # 近5日净流入
            recent = df.tail(5)
            if '当日成交净买额' in recent.columns:
                net_flow = recent['当日成交净买额'].sum()
                flow_desc = "净流入" if net_flow > 0 else "净流出"
                return f"""## 北向资金
- 近5日{flow_desc}: {abs(net_flow)/1e8:.2f}亿元"""
            else:
                return f"## 北向资金\n数据列: {list(df.columns)}"
        except Exception as e:
            return f"## 北向资金\n分析失败: {e}"

    def _analyze_limit_up(self, helper):
        """分析涨停板情况"""
        try:
            df = helper.get_limit_up_list()
            count = len(df) if not df.empty else 0

            if count > 50:
                heat = "火热"
            elif count > 20:
                heat = "活跃"
            elif count > 5:
                heat = "温和"
            else:
                heat = "低迷"

            return f"""## 涨停板情况
- 今日涨停数: {count}
- 市场情绪: {heat}"""
        except Exception as e:
            return f"## 涨停板情况\n分析失败: {e}"

    def _analyze_sectors(self, helper):
        """分析热点板块（简化版）"""
        try:
            # 用批量估值数据中的行业分布近似
            df = helper.get_hs300_valuation_batch()
            if df.empty or 'pct_change' not in df.columns:
                return "## 热点板块\n数据不足"

            # 按涨跌幅排序
            if 'name' in df.columns:
                top = df.nlargest(5, 'pct_change')[['name', 'pct_change']]
                bottom = df.nsmallest(5, 'pct_change')[['name', 'pct_change']]

                top_str = "\n".join([f"  - {row['name']}: {row['pct_change']:+.2f}%"
                                    for _, row in top.iterrows()])
                bottom_str = "\n".join([f"  - {row['name']}: {row['pct_change']:+.2f}%"
                                       for _, row in bottom.iterrows()])

                return f"""## 个股涨跌分布
### 涨幅前5:
{top_str}

### 跌幅前5:
{bottom_str}"""
            return "## 热点板块\n数据不足"
        except Exception as e:
            return f"## 热点板块\n分析失败: {e}"


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from data.akshare_helper import AKShareHelper

    helper = AKShareHelper()
    analyzer = MarketAnalyzer()
    report = analyzer.analyze(helper)
    print(report)
