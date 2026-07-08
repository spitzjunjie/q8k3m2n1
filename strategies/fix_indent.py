import os
import re

# 修复缩进问题的文件
files = [
    'anti_overconfidence_strategy.py',
    'continuous_volume_strategy.py',
    'dragon_tiger_list_strategy.py',
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
    lines = content.split('\n')
    
    # 找到 update_holdings 后面紧跟的 def select_stocks
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # 检查是否有 "    def select_stocks" 前面缺少空格的情况
        if '    def select_stocks' in line or 'def select_stocks' in line:
            # 检查前一行是否是 update_holdings 的结束
            if i > 0:
                prev_line = lines[i-1]
                # 如果前一行是方法内的内容，但当前 def 前面没有足够的缩进
                if prev_line.strip() and not prev_line.startswith('    '):
                    # 这可能是错误的情况
                    print(f'{fname}: 发现可能的缩进问题在行 {i+1}')
        
        i += 1
    
    # 用正则表达式修复 update_holdings 后面紧跟的 def (没有正确缩进)
    # 匹配: "    }" + "def select_stocks" 或 "    }" + "    def select_stocks" (错误的)
    pattern = r'(\s{4}holding\[.hold_days.\\] = holding\.get\(.hold_days., 0\) \+ 1\s+)(def select_stocks)'
    replacement = r'\1\n    \2'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        open(fname, 'w', encoding='utf-8').write(new_content)
        print(f'{fname}: 已修复')
        fixed_count += 1
    else:
        print(f'{fname}: 无需修复')

print(f'\n共修复 {fixed_count} 个文件')
