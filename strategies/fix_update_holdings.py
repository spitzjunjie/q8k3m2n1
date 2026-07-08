import os

# 所有需要修复的策略文件
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
    'high_dividend_strategy.py',
]

for fname in files_to_fix:
    if not os.path.exists(fname):
        print(f'{fname}: 不存在')
        continue
    content = open(fname, encoding='utf-8').read()
    
    if 'def update_holdings' in content:
        print(f'{fname}: 已有update_holdings')
        continue
    
    if 'def select_stocks' in content:
        idx = content.find('def select_stocks')
        insert_code = '''
    def update_holdings(self, prices):
        """更新持仓状态"""
        for holding in self.holdings:
            symbol = holding['symbol']
            if symbol in prices:
                holding['current_price'] = prices[symbol]
                holding['profit'] = (prices[symbol] - holding['buy_price']) * holding['quantity']
                holding['profit_pct'] = (prices[symbol] - holding['buy_price']) / holding['buy_price'] * 100
                holding['hold_days'] = holding.get('hold_days', 0) + 1
'''
        content = content[:idx] + insert_code + content[idx:]
        open(fname, 'w', encoding='utf-8').write(content)
        print(f'{fname}: 已添加update_holdings')
    else:
        print(f'{fname}: 无select_stocks，跳过')
