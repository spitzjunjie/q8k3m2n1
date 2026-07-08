import os

files_to_fix = [
    'anti_overconfidence_strategy.py',
    'continuous_volume_strategy.py',
    'dragon_tiger_list_strategy.py',
    'etf_rotation_strategy.py',
    'fundamental_small_cap_strategy.py',
    'golden_cross_strategy.py',
    'industry_momentum_strategy.py',
    'KDJ_strategy.py',
    'limit_callback_strategy.py',
    'low_pb_value_strategy.py',
    'low_turnover_strategy.py',
    'money_flow_event_strategy.py',
    'northbound_money_strategy.py',
    'profit_exceeds_expectation_strategy.py',
    'profit_explosion_strategy.py',
    'research_report_strategy.py',
    'rsi_rebound_strategy.py',
    'short_term_momentum_strategy.py',
    'southbound_money_strategy.py',
    'super_short_rebound_strategy.py',
    'value_growth_strategy.py',
]

for fname in files_to_fix:
    if not os.path.exists(fname):
        print(f'{fname}: 不存在')
        continue
    content = open(fname, encoding='utf-8').read()
    
    if 'def select_stocks' in content:
        print(f'{fname}: 已有select_stocks')
        continue
    
    if 'def __init__' in content:
        idx = content.find('def __init__')
        next_def = content.find('\n    def ', idx + 10)
        if next_def == -1:
            next_def = content.find('\n\nclass ', idx + 10)
        if next_def == -1:
            next_def = len(content)
        
        insert_code = '''
    def select_stocks(self, helper, date=None):
        """选股（简化版：返回空列表，待完善）"""
        # TODO: 实现完整的选股逻辑
        return []
'''
        content = content[:next_def] + insert_code + content[next_def:]
        open(fname, 'w', encoding='utf-8').write(content)
        print(f'{fname}: 已添加select_stocks')
    else:
        print(f'{fname}: 无__init__，跳过')
