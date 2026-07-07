# -*- coding: utf-8 -*-
# 清除缓存
import shutil, os
cache_dir = 'data/cache'
if os.path.exists(cache_dir):
    for f in os.listdir(cache_dir):
        os.remove(os.path.join(cache_dir, f))
print('缓存已清除')

from data.akshare_helper import AKShareHelper
from strategies.special_strategies import MaBreakStrategy
from strategies.event_strategies import ExecutiveBuyStrategy

helper = AKShareHelper()

print('\n=== 测试均线多头排列 ===')
strategy1 = MaBreakStrategy()
result1 = strategy1.calculate_factor(helper)
if result1 is None or result1.empty:
    print('选股为空')
else:
    print('选出 %d 只股票' % len(result1))
    print(result1.head(3))

print('\n=== 测试高管增持 ===')
strategy2 = ExecutiveBuyStrategy()
result2 = strategy2.detect_events(helper)
if not result2:
    print('选股为空')
else:
    print('选出 %d 只股票' % len(result2))
    for r in result2[:3]:
        sym = r['symbol']
        reason = r['reason']
        print('  %s: %s' % (sym, reason))
