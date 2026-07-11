# -*- coding: utf-8 -*-
"""
HuggingFace 客户端
使用 HuggingFace Inference API 调用开源金融模型

安装依赖：
    pip install huggingface_hub requests

使用方法：
    from hf_client import HuggingFaceClient, create_hf_client
    client = create_hf_client()
    response = client.complete("分析这条财经新闻...")
"""

import os
import json
from typing import Optional, List, Dict, Any

try:
    from huggingface_hub import InferenceClient
except ImportError:
    InferenceClient = None


# 可用的金融模型列表
AVAILABLE_MODELS = {
    # === 专业金融模型 (通过 HuggingFace Inference API) ===
    "finbert": "ProsusAI/finbert",  # ✅ 已验证可用 - 金融情感分析
    
    # === 通用对话模型（可用于金融分析）===
    "llama": "meta-llama/Llama-3.1-8B-Instruct",
    "mistral": "mistralai/Mistral-7B-Instruct-v0.2",
    "qwen": "Qwen/Qwen2.5-7B-Instruct",
    
    # === 中文模型 ===
    "qwen_cn": "Qwen/Qwen2.5-7B-Instruct",
    "yi": "01-ai/Yi-1.5-6B-Chat",
    
    # === FinGPT 系列 (需要本地部署) ===
    # "fingpt_llama3": "FinGPT/fingpt-mt_llama3-8b_lora",  # 需要 Llama-3 基础模型
}


class HuggingFaceClient:
    """HuggingFace Inference API 客户端
    
    支持免费额度：每分钟60次请求，适合个人使用
    """

    def __init__(self, api_token: str = None, model: str = "meta-llama/Llama-3.1-8B-Instruct"):
        """
        Args:
            api_token: HuggingFace API Token（默认从环境变量 HF_TOKEN 读取）
            model: 模型名称，默认为 Llama 3.1 8B
        """
        self.api_token = api_token or os.environ.get('HF_TOKEN')
        if not self.api_token and not InferenceClient:
            print("警告: 未安装 huggingface_hub，请运行: pip install huggingface_hub")
        elif not self.api_token:
            print("警告: 未设置 HF_TOKEN 环境变量")
        
        self.model = model
        self.client = None
        
        if self.api_token and InferenceClient:
            self.client = InferenceClient(token=self.api_token)
        
        # FinBERT 模型（专用金融情感分析）
        self.finbert_client = None
        if self.client:
            self.finbert_client = InferenceClient(token=self.api_token)

    def complete(self, prompt: str, system_prompt: str = None,
                 temperature: float = 0.7, max_tokens: int = 2000) -> Optional[str]:
        """调用 HuggingFace API 生成文本
        
        Args:
            prompt: 用户输入的提示
            system_prompt: 系统提示（可选）
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成 token 数
        
        Returns:
            str: 生成的文本，失败返回 None
        """
        if not self.client:
            print("错误: HuggingFace 客户端未初始化（缺少 API Token）")
            return None

        # 构建消息格式
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            # 使用聊天补全格式
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"HuggingFace API 调用失败: {e}")
            return None

    def analyze_financial_news(self, news_text: str) -> Optional[Dict]:
        """分析财经新闻（使用 FinBERT 专业金融情感分析）
        
        Args:
            news_text: 新闻内容
        
        Returns:
            dict: 分析结果 {sentiment, sentiment_score, confidence}
        """
        if not self.finbert_client:
            print("错误: FinBERT 客户端未初始化")
            return None

        try:
            # 使用 FinBERT 进行情感分析
            response = self.finbert_client.text_classification(
                text=news_text,
                model="ProsusAI/finbert"
            )
            
            # 解析结果
            if response and len(response) > 0:
                # 按 score 排序
                sorted_results = sorted(response, key=lambda x: x['score'], reverse=True)
                
                sentiment_map = {
                    'positive': '看多',
                    'neutral': '中性',
                    'negative': '看空'
                }
                
                top_result = sorted_results[0]
                sentiment = sentiment_map.get(top_result['label'], top_result['label'])
                
                # 将 score 转换为 -1 到 1 的分数
                if top_result['label'] == 'positive':
                    sentiment_score = top_result['score']
                elif top_result['label'] == 'negative':
                    sentiment_score = -top_result['score']
                else:
                    sentiment_score = 0
                
                return {
                    'sentiment': sentiment,
                    'sentiment_score': round(sentiment_score, 3),
                    'confidence': round(top_result['score'], 3),
                    'all_scores': {r['label']: round(r['score'], 3) for r in response},
                    'raw_result': response
                }
        except Exception as e:
            print(f"FinBERT 情感分析失败: {e}")
        
        return None

    def analyze_financial_news_deep(self, news_text: str) -> Optional[Dict]:
        """深度分析财经新闻（使用 LLM + FinBERT）
        
        先用 FinBERT 分析情感，再用 LLM 深度解读
        
        Args:
            news_text: 新闻内容
        
        Returns:
            dict: 深度分析结果
        """
        # 第一步：FinBERT 情感分析
        finbert_result = self.analyze_financial_news(news_text)
        
        # 第二步：LLM 深度分析
        prompt = f"""分析以下财经新闻，给出详细的投资分析。

新闻内容：
{news_text}

## 情感分析初步结果（FinBERT）
{finbert_result}

请输出JSON格式：
{{
    "summary": "核心内容摘要(50字内)",
    "sentiment": "看多/中性/看空",
    "sentiment_score": 情绪分数(-1到1之间),
    "affected_sectors": ["受影响板块1", "受影响板块2"],
    "risk_level": "高/中/低",
    "investment_suggestion": "投资建议",
    "key_points": ["要点1", "要点2"]
}}

只输出JSON，不要其他文字："""

        response = self.complete(
            prompt,
            system_prompt="你是一个专业的金融分析师，擅长从财经新闻中提取投资机会和风险。",
            temperature=0.3,
            max_tokens=800
        )

        if not response:
            return finbert_result  # 返回 FinBERT 结果

        import re
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
                result['finbert_result'] = finbert_result
                return result
        except:
            pass
        
        return finbert_result

    def generate_strategy_idea(self, market_context: str, existing_strategies: List[str]) -> Optional[Dict]:
        """生成策略思路
        
        Args:
            market_context: 市场环境描述
            existing_strategies: 已有策略列表
        
        Returns:
            dict: 策略建议
        """
        existing_str = '\n'.join(f"- {s}" for s in existing_strategies)

        prompt = f"""你是A股量化策略研究员。基于以下信息提出一个新策略假设。

## 当前市场环境
{market_context}

## 已有策略（避免重复）
{existing_str}

## A股特性
- T+1交易（当日买入次日才能卖出）
- 涨跌停限制（主板±10%，创业板/科创板±20%）
- 行业轮动明显
- 北向资金影响大

## 要求
1. 提出与现有策略不同的假设
2. 说明逻辑（为什么这个因子/事件能预测收益）
3. 给出可量化的选股规则
4. 给出择时规则（何时买何时卖）

输出严格的JSON格式：
{{
    "name": "策略名（4-6字）",
    "category": "类别（如：因子/事件/趋势/ML）",
    "hypothesis": "策略假设描述",
    "select_rule": "选股规则（具体量化条件）",
    "timing_rule": "择时规则（买卖时机）",
    "expected_market": "适合的市场环境",
    "risk_factors": ["风险因素"]
}}

只输出JSON，不要其他文字："""

        response = self.complete(
            prompt,
            system_prompt="你是一个专业的A股量化策略研究员，擅长发现创新的alpha因子和交易策略。",
            temperature=0.8,
            max_tokens=1500
        )

        if not response:
            return None

        import re
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except:
            pass
        return None

    def test_connection(self) -> bool:
        """测试 API 连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            response = self.complete(
                "你好，请回复 'OK'",
                temperature=0.1,
                max_tokens=50
            )
            return response is not None and ("OK" in response or "ok" in response)
        except:
            return False


def create_hf_client(model: str = "meta-llama/Llama-3.1-8B-Instruct") -> HuggingFaceClient:
    """创建 HuggingFace 客户端（从环境变量读取 token）
    
    环境变量:
        HF_TOKEN: HuggingFace API Token
    """
    api_token = os.environ.get('HF_TOKEN')
    if not api_token:
        print("请先设置环境变量: $env:HF_TOKEN='your_token'")
    return HuggingFaceClient(api_token=api_token, model=model)


def test_hf_token(token: str) -> Dict:
    """测试 HuggingFace Token 是否有效
    
    Args:
        token: HuggingFace API Token
    
    Returns:
        dict: {success: bool, message: str, models: list}
    """
    try:
        from huggingface_hub import HfApi
        
        api = HfApi(token=token)
        
        # 尝试获取用户信息
        who = api.whoami()
        
        # 获取可用模型
        models = api.list_models(full=True)
        model_names = [m.id for m in list(models)[:20]]
        
        return {
            "success": True,
            "message": f"Token 有效！用户: {who.get('name', 'N/A')}",
            "email": who.get('email', 'N/A'),
            "models": model_names
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Token 无效或过期: {str(e)}",
            "models": []
        }


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("HuggingFace 客户端测试")
    print("=" * 60)
    
    # 测试 Token
    test_token = os.environ.get('HF_TOKEN')
    if not test_token:
        print("\n未设置 HF_TOKEN 环境变量")
        print("请运行: $env:HF_TOKEN='your_token'")
    else:
        print(f"\n测试 Token: {test_token[:10]}...")
        result = test_hf_token(test_token)
        
        if result['success']:
            print(f"✓ {result['message']}")
            print(f"  邮箱: {result.get('email', 'N/A')}")
            print(f"  可用模型示例: {result['models'][:5]}")
        else:
            print(f"✗ {result['message']}")
    
    print("\n" + "=" * 60)
    print("使用示例")
    print("=" * 60)
    print("""
# 创建客户端
from hf_client import HuggingFaceClient
client = HuggingFaceClient(api_token="your_token")

# 分析新闻
result = client.analyze_financial_news("某公司发布业绩预告...")

# 生成策略
strategies = client.generate_strategy_idea(
    market_context="上证指数在3000点附近震荡...",
    existing_strategies=["低PE策略", "MACD金叉策略"]
)
""")
