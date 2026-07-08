import os
import re

# 所有需要检查的文件
files = [
    'anti_overconfidence_strategy.py',
    'continuous_volume_strategy.py',
    'dragon_tiger_list_strategy.py',
    'etf_rotation_strategy.py',
    'fundamental_small_cap_strategy.py',
    'golden_cross_strategy.py',
    'industry_momentum_strategy.py',
    'KDJ_strategy.py',
    'limit_callback_strategy.py',
    'low_turnover_strategy.py',
    'low_pb_value_strategy.py',
    'money_flow_event_strategy.py',
    'northbound_money_strategy.py',
    'profit_explosion_strategy.py',
    'profit_exceeds_expectation_strategy.py',
    'research_report_strategy.py',
    'rsi_rebound_strategy.py',
    'short_term_momentum_strategy.py',
    'southbound_money_strategy.py',
    'super_short_rebound_strategy.py',
    'value_growth_strategy.py',
    'high_dividend_strategy.py',
]

fixed_count = 0
for fname in files:
    if not os.path.exists(fname):
        print(f'{fname}: 不存在')
        continue
    
    content = open(fname, encoding='utf-8').read()
    
    # 修复模式: "holding['hold_days'] = ..." 后面紧跟 "def select_stocks" (没有正确的缩进)
    # 正确应该是: 4个空格缩进的 def
    pattern = r"(holding\['hold_days'\]\s*=\s*holding\.get\('hold_days',\s*0\)\s*\+\s*1\s+)def select_stocks"
    replacement = r"\1\n    def select_stocks"
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        open(fname, 'w', encoding='utf-8').write(new_content)
        print(f'{fname}: 已修复')
        fixed_count += 1
    else:
        print(f'{fname}: 无需修复')

print(f'\n共修复 {fixed_count} 个文件')

# 然后测试是否能正常导入
print('\n测试导入...')
os.system('cd .. && python -c "from strategies.new_strategies import *; print(\'导入成功!\')"')
