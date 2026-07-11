# -*- coding: utf-8 -*-
"""测试 HuggingFace Token"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from strategy_discovery.hf_client import test_hf_token, HuggingFaceClient

token = '***REMOVED***'

print('=' * 60)
print('测试 HuggingFace Token')
print('=' * 60)

# 测试 Token
print('\n[1/2] 测试 Token 有效性...')
result = test_hf_token(token)
print(f'成功: {result["success"]}')
print(f'消息: {result["message"]}')

if result['success']:
    print(f'邮箱: {result.get("email", "N/A")}')
    print(f'\n可用模型示例 (前10个):')
    for m in result['models'][:10]:
        print(f'  - {m}')

    # 测试实际调用
    print('\n[2/2] 测试模型调用...')
    client = HuggingFaceClient(api_token=token, model='meta-llama/Llama-3.1-8B-Instruct')
    
    print('发送测试请求 (可能需要10-30秒)...')
    response = client.complete(
        '请用一句话介绍自己',
        temperature=0.7,
        max_tokens=100
    )
    
    if response:
        print(f'\n模型回复: {response}')
        print('\n✓ Token 测试成功！可以正常使用 HuggingFace API')
    else:
        print('\n✗ 模型调用失败')
else:
    print('\n✗ Token 无效，请检查或重新获取')
