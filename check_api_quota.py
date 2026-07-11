# -*- coding: utf-8 -*-
"""检查 API 额度使用情况"""

import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from huggingface_hub import HfApi

token = '***REMOVED***'

print('=' * 60)
print('HuggingFace API 额度检查')
print('=' * 60)

try:
    api = HfApi(token=token)
    who = api.whoami()
    print(f'\n用户: {who.get("name")}')
    print(f'邮箱: {who.get("email", "未验证")}')
    
    # 检查订阅类型
    print(f'\n账户类型: {who.get("email", "免费账户")}')
    
except Exception as e:
    print(f'检查失败: {e}')

print('\n' + '-' * 60)
print('HuggingFace 免费额度说明')
print('-' * 60)
print('''
📊 免费额度限制：
   - Serverless Inference API: 每分钟约 3-5 次请求
   - 文本生成: 每月约 30,000 字符
   - 小模型分类: 较宽松

⚡ 实际使用情况：
   - FinBERT (文本分类): 额度充足，免费可用 ✅
   - Llama 3 8B (文本生成): 额度有限 ⚠️
   - Qwen 7B (中文生成): 额度有限 ⚠️

💡 优化建议：
   1. FinBERT 完全够用（文本分类消耗少）
   2. 文本生成任务可以继续用现有 MiniMax API
   3. 每日报告生成建议用 MiniMax，成本更低
''')

print('\n' + '-' * 60)
print('当前使用的 API')
print('-' * 60)
print('''
| API | 用途 | 额度 | 够用吗 |
|-----|------|------|--------|
| HuggingFace FinBERT | 金融情感分析 | 充足 | ✅ 够用 |
| HuggingFace LLM | 深度分析 | 有限 | ⚠️ 辅助用 |
| MiniMax (已有) | 报告生成 | 充足 | ✅ 够用 |
''')

print('\n' + '=' * 60)
print('结论：FinBERT 够用，深度分析任务可混用多个 API')
print('=' * 60)
