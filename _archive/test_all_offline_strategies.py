# -*- coding: utf-8 -*-
"""回测所有未上线策略"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from backtest import get_all_strategies

# 已上线的33个策略
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

# 获取所有策略
all_strategies = get_all_strategies()

# 筛选未上线策略
offline_strategies = [s for s in all_strategies if s.name not in ONLINE_STRATEGIES]

print("=" * 60)
print(f"总策略数: {len(all_strategies)}")
print(f"已上线: {len(ONLINE_STRATEGIES)}")
print(f"未上线: {len(offline_strategies)}")
print("=" * 60)

print("\n未上线策略列表:")
for i, s in enumerate(offline_strategies, 1):
    print(f"{i:2d}. {s.name} ({s.category})")

# 保存到文件供后续使用
with open("output/offline_strategies.txt", "w", encoding="utf-8") as f:
    f.write(f"未上线策略列表 ({len(offline_strategies)}个)\n")
    f.write("=" * 50 + "\n")
    for i, s in enumerate(offline_strategies, 1):
        f.write(f"{i:2d}. {s.name}\n")

print(f"\n已保存到: output/offline_strategies.txt")
