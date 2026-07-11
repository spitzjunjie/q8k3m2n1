# -*- coding: utf-8 -*-
"""检查策略上线状态"""

# GitHub上已上线的33个策略
ONLINE_STRATEGIES = [
    "多周期共振", "高管增持", "均线多头排列", "国产替代",
    "趋势动量", "AI供应链紫苏叶", "ST摘帽潜伏", "业绩超预期",
    "量价突破", "北向资金跟投", "多因子综合", "现金流质量",
    "首板回调", "ROE选股", "高ROIC", "红利低波",
    "高股息", "动量反转", "分析师上调", "MACD金叉",
    "KDJ超卖金叉", "动量突破", "营收增长", "净利润增速",
    "北向重仓", "机构持仓", "PSR低估值", "低负债率",
    "RSI超卖反转", "低PB", "低估值修复", "低PE", "质量因子选股"
]

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from backtest import get_all_strategies

all_strategies = get_all_strategies()

print("=" * 60)
print(f"本地策略总数: {len(all_strategies)}")
print(f"已上线策略: {len(ONLINE_STRATEGIES)}")
print(f"未上线策略: {len(all_strategies) - len(ONLINE_STRATEGIES)}")
print("=" * 60)

# 分类
online = []
offline = []

for s in all_strategies:
    if s.name in ONLINE_STRATEGIES:
        online.append(s)
    else:
        offline.append(s)

print(f"\n✅ 已上线 ({len(online)}个):")
for s in online:
    print(f"  - {s.name}")

print(f"\n❌ 未上线 ({len(offline)}个):")
for s in offline:
    print(f"  - {s.name} ({s.category})")
