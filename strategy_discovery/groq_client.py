# -*- coding: utf-8 -*-
"""
Groq API 客户端
超快速 LLM 推理，适合深度分析任务

安装：pip install groq

免费额度：每分钟 30 次请求
模型：llama-3.1-8b-instant (推荐), llama-3.1-70b, mixtral-8x7b
"""

import os
import json
from typing import Optional, List, Dict, Any

try:
    from groq import Groq
except ImportError:
    Groq = None


class GroqClient:
    """Groq API 客户端
    
    特点：极速推理（比普通 API 快 10 倍）
    适合：深度分析、报告生成等需要高质量输出的任务
    """

    def __init__(self, api_key: str = None, model: str = "llama-3.1-8b-instant"):
        """
        Args:
            api_key: Groq API Key（默认从环境变量 GROQ_API_KEY 读取）
            model: 模型名称，默认 llama-3.1-8b-instant
                   其他选项：llama-3.1-70b-versatile, mixtral-8x7b-32768
        """
        self.api_key = api_key or os.environ.get('GROQ_API_KEY')
        if not self.api_key and not Groq:
            print("警告: 未安装 groq，请运行: pip install groq")
        elif not self.api_key:
            print("警告: 未设置 GROQ_API_KEY 环境变量")
        
        self.model = model
        self.client = None
        
        if self.api_key and Groq:
            self.client = Groq(api_key=self.api_key)

    def complete(self, prompt: str, system_prompt: str = None,
                 temperature: float = 0.7, max_tokens: int = 2000) -> Optional[str]:
        """调用 Groq API 生成文本
        
        Args:
            prompt: 用户输入的提示
            system_prompt: 系统提示（可选）
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成 token 数
        
        Returns:
            str: 生成的文本，失败返回 None
        """
        if not self.client:
            print("错误: Groq 客户端未初始化（缺少 API Key）")
            return None

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Groq API 调用失败: {e}")
            return None

    def analyze_financial_news(self, news_text: str) -> Optional[Dict]:
        """分析财经新闻
        
        Args:
            news_text: 新闻内容
        
        Returns:
            dict: 分析结果
        """
        prompt = f"""分析以下财经新闻，判断其对A股市场的影响。

新闻内容：
{news_text}

请输出严格的JSON格式：
{{
    "sentiment": "看多/中性/看空",
    "sentiment_score": 情绪分数(-1到1之间),
    "summary": "核心内容摘要(50字内)",
    "affected_sectors": ["受影响板块1", "受影响板块2"],
    "risk_level": "高/中/低",
    "investment_suggestion": "投资建议"
}}

只输出JSON，不要其他文字："""

        response = self.complete(
            prompt,
            system_prompt="你是一个专业的金融分析师，擅长从财经新闻中提取投资机会和风险。",
            temperature=0.3,
            max_tokens=500
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

    def analyze_failed_strategy(self, strategy_info: Dict, backtest_result: Dict) -> Optional[Dict]:
        """分析失败策略原因
        
        Args:
            strategy_info: 策略信息
            backtest_result: 回测结果
        
        Returns:
            dict: 改进建议
        """
        prompt = f"""分析以下量化策略失败的原因，并给出具体改进建议。

## 策略信息
名称: {strategy_info.get('name', 'Unknown')}
假设: {strategy_info.get('hypothesis', 'N/A')}
选股规则: {strategy_info.get('select_rule', 'N/A')}
择时规则: {strategy_info.get('timing_rule', 'N/A')}

## 回测结果
总收益: {backtest_result.get('total_return', 'N/A')}%
夏普比率: {backtest_result.get('sharpe', 'N/A')}
胜率: {backtest_result.get('win_rate', 'N/A')}%
最大回撤: {backtest_result.get('max_drawdown', 'N/A')}%
评分: {backtest_result.get('grade', 'N/A')}

## 分析任务
1. 分析策略失败的核心原因
2. 提出2-3个具体的改进方向
3. 针对每个方向给出具体参数调整建议

请输出JSON格式：
{{
    "failure_reasons": ["原因1", "原因2"],
    "improvements": [
        {{
            "direction": "改进方向名称",
            "problem": "当前问题",
            "suggestion": "具体修改建议",
            "expected_impact": "预期效果"
        }}
    ],
    "overall_assessment": "总体评价"
}}

只输出JSON："""

        response = self.complete(
            prompt,
            system_prompt="你是一个专业的量化策略研究员，擅长诊断策略问题并提出改进方案。",
            temperature=0.5,
            max_tokens=1000
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

    def generate_market_insight(self, market_data: Dict) -> str:
        """生成市场洞察
        
        Args:
            market_data: 市场数据
        
        Returns:
            str: 市场洞察文本
        """
        indices_info = ""
        if 'indices' in market_data:
            for name, info in market_data['indices'].items():
                change = info.get('change_pct', 0)
                indices_info += f"- {name}: {info.get('price', 'N/A')} ({'+' if change > 0 else ''}{change:.2f}%)\n"

        prompt = f"""分析当前A股市场状况，生成简短的市场洞察。

## 市场数据
{indices_info}
成交量: {market_data.get('volume', 'N/A')}
北向资金: {market_data.get('north_flow', 'N/A')}

## 要求
1. 判断当前市场状态（上涨/下跌/震荡）
2. 识别主要驱动因素
3. 给出操作建议

直接输出150字以内的市场洞察，不要JSON："""

        response = self.complete(
            prompt,
            system_prompt="你是一个专业的A股市场分析师，擅长判断市场趋势。",
            temperature=0.5,
            max_tokens=400
        )

        return response or "市场分析生成失败"

    def test_connection(self) -> bool:
        """测试 API 连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            response = self.complete(
                "请回复 'OK'",
                temperature=0.1,
                max_tokens=20
            )
            return response is not None and ("OK" in response or "ok" in response)
        except:
            return False


def create_groq_client(model: str = "llama-3.1-8b-instant") -> GroqClient:
    """创建 Groq 客户端"""
    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        print("请先设置环境变量: $env:GROQ_API_KEY='your_key'")
    return GroqClient(api_key=api_key, model=model)


if __name__ == "__main__":
    print("=" * 60)
    print("Groq 客户端测试")
    print("=" * 60)
    
    # 测试连接
    client = GroqClient(api_key="***REMOVED***")
    
    if client.client:
        print("\n[1] 测试基本连接...")
        response = client.complete("请回复 'OK'")
        if response:
            print(f"✓ 连接成功: {response}")
        else:
            print("✗ 连接失败")
        
        print("\n[2] 测试市场洞察生成...")
        market_data = {
            'indices': {
                '上证指数': {'price': 3015, 'change_pct': 0.5},
                '创业板': {'price': 1665, 'change_pct': 1.2}
            },
            'north_flow': '净流入30亿'
        }
        insight = client.generate_market_insight(market_data)
        print(f"市场洞察: {insight[:100]}...")
        
        print("\n[3] 测试失败策略分析...")
        strategy_info = {
            'name': '低PE策略',
            'hypothesis': '低PE股票有超额收益',
            'select_rule': 'PE<10',
            'timing_rule': '金叉买入'
        }
        backtest_result = {
            'total_return': -5.2,
            'sharpe': 0.3,
            'win_rate': 0.35,
            'max_drawdown': 15
        }
        suggestion = client.analyze_failed_strategy(strategy_info, backtest_result)
        if suggestion:
            print(f"失败原因: {suggestion.get('failure_reasons', [])[:2]}")
            print(f"改进方向: {[i['direction'] for i in suggestion.get('improvements', [])[:2]]}")
    else:
        print("✗ 客户端初始化失败")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
