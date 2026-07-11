# -*- coding: utf-8 -*-
"""
龙头战法简化版策略
核心逻辑：板块龙头 → 资金聚集 → 趋势延续 → 顺势而为

选股条件：
- 流通市值：30-80亿
- 股价：< 15元
- 涨停时间：早盘（9:30-10:00）
- 封单质量：封单/成交额 > 8%
- 板块强度：涨停家数 > 10家

买入条件：
1. 板块首板涨停（9:30-10:00）
2. 封单稳定，不撤单
3. 跟风股 > 3家
4. 次日开盘买入

卖出条件：
- 破5日线：减仓
- 破10日线：清仓
- 放量滞涨：止盈

止损：
- 单笔亏损 > 7%：止损
- 日内浮亏 > 3%：停止交易

参考：游资大神（章盟主、作手新一等）龙头战法
"""

import pandas as pd
from strategies.base import BaseStrategy


class LeadingStockStrategy(BaseStrategy):
    """龙头战法简化版策略"""

    def __init__(self,
                 min_circ_mv=30,          # 最低流通市值（亿）
                 max_circ_mv=80,          # 最高流通市值（亿）
                 max_price=15,            # 最高股价（元）
                 min_seal_time='093000',  # 最早涨停时间（HHMMSS）
                 max_seal_time='100000',  # 最晚涨停时间（HHMMSS）
                 min_seal_ratio=8,        # 封单/成交额最小比例（%）
                 min_sector_limit=10,     # 板块最少涨停家数
                 min_followers=3,         # 最少跟风股数量
                 stop_loss=-7,            # 止损线（%）
                 holding_days=3,          # 持有天数
                 top_n=5):
        super().__init__("龙头战法", "短线事件")
        self.min_circ_mv = min_circ_mv
        self.max_circ_mv = max_circ_mv
        self.max_price = max_price
        self.min_seal_time = min_seal_time
        self.max_seal_time = max_seal_time
        self.min_seal_ratio = min_seal_ratio
        self.min_sector_limit = min_sector_limit
        self.min_followers = min_followers
        self.stop_loss = stop_loss
        self.holding_days = holding_days
        self.top_n = top_n
        self._sector_stats = None

    def get_description(self):
        return (f"龙头战法：流通市值{self.min_circ_mv}-{self.max_circ_mv}亿, "
                f"股价<{self.max_price}元, 早盘涨停{self.min_seal_time}-{self.max_seal_time}, "
                f"封单质量>{self.min_seal_ratio}%, 止损{self.stop_loss}%")

    def _get_sector_stats(self, helper, date=None):
        """获取板块涨停统计"""
        if self._sector_stats is not None:
            return self._sector_stats

        try:
            limit_df = helper.get_limit_up_list(
                date=date.replace('-', '') if date else None
            )
            if limit_df is not None and not limit_df.empty:
                # 统计各板块涨停家数
                sector_counts = limit_df.groupby('所属行业').size().to_dict()
                self._sector_stats = sector_counts
                return sector_counts
        except Exception as e:
            print(f"获取板块涨停统计失败: {e}")
        self._sector_stats = {}
        return self._sector_stats

    def _count_sector_followers(self, limit_df, sector, exclude_symbol):
        """统计板块跟风股数量（排除龙头）"""
        if limit_df is None or limit_df.empty:
            return 0
        sector_stocks = limit_df[
            (limit_df['所属行业'] == sector) &
            (limit_df['代码'] != exclude_symbol)
        ]
        return len(sector_stocks)

    def _is_early_limit_up(self, seal_time):
        """判断是否为早盘涨停"""
        if not seal_time:
            return False
        # 转换为数字比较
        try:
            time_val = int(seal_time)
            min_val = int(self.min_seal_time)
            max_val = int(self.max_seal_time)
            return min_val <= time_val <= max_val
        except (ValueError, TypeError):
            return False

    def select_stocks(self, helper, date=None):
        """选股：龙头战法"""
        results = []

        # 获取涨停板数据
        try:
            limit_df = helper.get_limit_up_list(
                date=date.replace('-', '') if date else None
            )
        except Exception as e:
            print(f"获取涨停板失败: {e}")
            limit_df = None

        # 获取板块涨停统计
        sector_stats = self._get_sector_stats(helper, date)

        if limit_df is not None and not limit_df.empty:
            candidates = []

            for _, row in limit_df.iterrows():
                try:
                    symbol = str(row.get('代码', row.get('股票代码', '')))
                    name = str(row.get('名称', row.get('股票简称', symbol)))
                    price = float(row.get('最新价', 0))

                    # 流通市值（亿）
                    circ_mv = 0
                    circ_mv_raw = row.get('流通市值', 0)
                    if circ_mv_raw:
                        circ_mv = float(circ_mv_raw) / 1e8  # 转换为亿

                    # 成交额（万）
                    amount = float(row.get('成交额', 0))

                    # 封板资金（万）
                    seal_amount = float(row.get('封板资金', 0))

                    # 首次封板时间
                    seal_time = str(row.get('首次封板时间', ''))

                    # 所属行业
                    sector = str(row.get('所属行业', '未知'))

                    # 炸板次数
                    bomb_count = int(row.get('炸板次数', 0))

                    # === 选股条件筛选 ===
                    # 1. 流通市值：30-80亿
                    if not (self.min_circ_mv <= circ_mv <= self.max_circ_mv):
                        continue

                    # 2. 股价 < 15元
                    if price >= self.max_price:
                        continue

                    # 3. 早盘涨停（9:30-10:00）
                    if not self._is_early_limit_up(seal_time):
                        continue

                    # 4. 封单质量：封单/成交额 > 8%
                    if amount > 0:
                        seal_ratio = (seal_amount / amount) * 100
                        if seal_ratio < self.min_seal_ratio:
                            continue
                    else:
                        continue

                    # 5. 板块强度：涨停家数 > 10家
                    sector_limit_count = sector_stats.get(sector, 0)
                    if sector_limit_count < self.min_sector_limit:
                        continue

                    # 6. 封单稳定（炸板次数=0或很少）
                    if bomb_count > 1:
                        continue

                    # 7. 跟风股 > 3家
                    followers = self._count_sector_followers(limit_df, sector, symbol)
                    if followers < self.min_followers:
                        continue

                    # 综合得分计算
                    # 权重：封单质量(40%) + 板块强度(30%) + 跟风数量(30%)
                    if amount > 0:
                        seal_ratio_score = min((seal_amount / amount) * 100 / 20, 1) * 40
                    else:
                        seal_ratio_score = 0

                    sector_strength_score = min(sector_limit_count / 20, 1) * 30
                    follower_score = min(followers / 10, 1) * 30

                    total_score = seal_ratio_score + sector_strength_score + follower_score

                    candidates.append({
                        'symbol': symbol,
                        'name': name,
                        'score': total_score,
                        'price': price,
                        'circ_mv': circ_mv,
                        'seal_amount': seal_amount,
                        'amount': amount,
                        'seal_ratio': (seal_amount / amount) * 100 if amount > 0 else 0,
                        'seal_time': seal_time,
                        'sector': sector,
                        'followers': followers,
                        'sector_limit_count': sector_limit_count,
                        'bomb_count': bomb_count,
                    })

                except Exception as e:
                    continue

            # 按得分排序
            candidates.sort(key=lambda x: x['score'], reverse=True)

            # 生成结果
            for i, c in enumerate(candidates[:self.top_n]):
                if i == 0:
                    # 第一名标记为龙头
                    reason = (f"🚀龙头：{c['sector']}板块，流通市值{c['circ_mv']:.0f}亿，"
                              f"股价{c['price']:.2f}元，{c['seal_time']}涨停，"
                              f"封单/成交额={c['seal_ratio']:.1f}%，跟风{c['followers']}家，"
                              f"板块涨停{c['sector_limit_count']}家，得分{c['score']:.1f}")
                else:
                    reason = (f"{c['sector']}板块，流通市值{c['circ_mv']:.0f}亿，"
                              f"股价{c['price']:.2f}元，{c['seal_time']}涨停，"
                              f"封单/成交额={c['seal_ratio']:.1f}%，跟风{c['followers']}家，"
                              f"板块涨停{c['sector_limit_count']}家，得分{c['score']:.1f}")

                results.append({
                    'symbol': c['symbol'],
                    'name': c['name'],
                    'reason': reason,
                    # 附加信息用于后续交易判断
                    'sector': c['sector'],
                    'score': c['score'],
                    'seal_ratio': c['seal_ratio'],
                })

        # 备选：如果没有找到符合条件的龙头，返回空列表
        if not results:
            print("未找到符合条件的龙头股")
            return []

        return results[:self.top_n]

    def detect_events(self, helper, date=None):
        """检测龙头事件（复用select_stocks逻辑）"""
        return self.select_stocks(helper, date)


if __name__ == '__main__':
    s = LeadingStockStrategy()
    print(f"策略: {s.name}")
    print(f"描述: {s.get_description()}")
    print(f"选股条件:")
    print(f"  - 流通市值: {s.min_circ_mv}-{s.max_circ_mv}亿")
    print(f"  - 股价: < {s.max_price}元")
    print(f"  - 涨停时间: {s.min_seal_time}-{s.max_seal_time}")
    print(f"  - 封单/成交额: > {s.min_seal_ratio}%")
    print(f"  - 板块涨停家数: > {s.min_sector_limit}家")
    print(f"  - 跟风股: > {s.min_followers}家")
    print(f"止损: {s.stop_loss}%")
