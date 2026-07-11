# -*- coding: utf-8 -*-
"""测试 HuggingFace 上可用的金融模型"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from huggingface_hub import InferenceClient

token = '***REMOVED***'

print('=' * 60)
print('测试 HuggingFace 金融模型')
print('=' * 60)

# 候选金融模型列表
candidate_models = [
    'ProsusAI/finbert',
    'yiyanghkust/finbert-pretrain',
    'AventIQ-AI/finbert-sentiment-analysis',
    'jaiganesan/finbert',
]

client = InferenceClient(token=token)

for model_name in candidate_models:
    print(f'\n测试模型: {model_name}')
    print('-' * 50)
    
    try:
        response = client.text_classification(
            text="The company reported strong quarterly earnings, beating expectations.",
            model=model_name
        )
        print(f'✓ API 可用')
        print(f'  结果: {response}')
    except Exception as e:
        error_msg = str(e)
        if '404' in error_msg:
            print(f'✗ 模型不在 HuggingFace API 免费列表中')
        elif 'rate' in error_msg.lower():
            print(f'⚠ 速率限制')
        else:
            print(f'✗ 错误: {error_msg[:150]}')

print('\n' + '=' * 60)
