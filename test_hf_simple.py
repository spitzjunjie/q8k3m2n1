# -*- coding: utf-8 -*-
"""快速测试 HuggingFace Token"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from huggingface_hub import HfApi

token = '***REMOVED***'

print('=' * 60)
print('测试 HuggingFace Token')
print('=' * 60)

try:
    print('\n[1/2] 测试 Token 有效性...')
    api = HfApi(token=token)
    who = api.whoami()
    print(f'✓ Token 有效！')
    print(f'  用户名: {who.get("name", "N/A")}')
    print(f'  邮箱: {who.get("email", "N/A")}')
    
    print('\n[2/2] 测试模型调用...')
    from strategy_discovery.hf_client import HuggingFaceClient
    client = HuggingFaceClient(api_token=token, model='meta-llama/Llama-3.1-8B-Instruct')
    
    print('发送测试请求 (等待模型响应)...')
    response = client.complete('请回复 OK', temperature=0.1, max_tokens=20)
    
    if response:
        print(f'\n✓ 模型回复: {response}')
        print('\n' + '=' * 60)
        print('测试成功！Token 和 API 都可以正常使用')
        print('=' * 60)
    else:
        print('\n✗ 模型调用失败')

except Exception as e:
    print(f'\n✗ 错误: {e}')
    import traceback
    traceback.print_exc()
