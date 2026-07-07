# -*- coding: utf-8 -*-
"""
MiniMax LLM 客户端
提供策略发现和市场分析功能

环境变量：
- MINIMAX_API_KEY: MiniMax API密钥
- MINIMAX_GROUP_ID: MiniMax Group ID

功能：
1. MiniMax API调用（OpenAI兼容格式）
2. 策略发现：输入市场环境描述、已有策略列表，输出新的策略思路/参数建议
3. 市场分析：分析当前市场状态（趋势/震荡/高波动），推荐适合当前市场的策略组合
4. 保存API调用日志到 logs/llm_calls.json
"""

import os
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class MiniMaxClient:
    """MiniMax API客户端
    
    使用OpenAI兼容格式调用MiniMax API
    """

    def __init__(self, api_key: str = None, group_id: str = None, 
                 model: str = "abab6.5s-chat"):
        """
        Args:
            api_key: MiniMax API密钥（默认从环境变量MINIMAX_API_KEY读取）
            group_id: MiniMax Group ID（默认从环境变量MINIMAX_GROUP_ID读取）
            model: 模型名称，默认 abab6.5s-chat
        """
        self.api_key = api_key or os.environ.get('MINIMAX_API_KEY')
        self.group_id = group_id or os.environ.get('MINIMAX_GROUP_ID')
        self.model = model
        
        if not self.api_key:
            print("警告: 未设置MINIMAX_API_KEY环境变量")
        if not self.group_id:
            print("警告: 未设置MINIMAX_GROUP_ID环境变量")
        
        # MiniMax API endpoint (OpenAI兼容格式)
        self.base_url = "https://api.minimax.chat/v1"
        
        self.client = None
        if self.api_key and OpenAI:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

    def complete(self, prompt: str, system_prompt: str = None,
                 temperature: float = 0.7, max_tokens: int = 2000) -> Optional[str]:
        """调用MiniMax API生成文本
        
        Args:
            prompt: 用户输入的提示
            system_prompt: 系统提示（可选）
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成token数
        
        Returns:
            str: 生成的文本，失败返回None
        """
        if not self.client:
            print("错误: MiniMax客户端未初始化（缺少API密钥）")
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
            content = response.choices[0].message.content
            
            # 记录API调用
            self._log_call(prompt, content, system_prompt)
            
            return content
        except Exception as e:
            print(f"MiniMax API调用失败: {e}")
            self._log_call(prompt, str(e), system_prompt, error=True)
            return None

    def _log_call(self, prompt: str, response: str, 
                  system_prompt: str = None, error: bool = False):
        """记录API调用到日志文件"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'llm_calls.json')
        
        log_entry = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'model': self.model,
            'system_prompt': system_prompt,
            'prompt': prompt[:500] + '...' if len(prompt) > 500 else prompt,
            'response': response[:500] + '...' if len(response) > 500 else response,
            'error': error
        }
        
        # 读取现有日志
        logs = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except:
                pass
        
        # 添加新日志
        logs.append(log_entry)
        
        # 只保留最近1000条日志
        logs = logs[-1000:]
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)


class StrategyDiscovery:
    """基于LLM的策略发现器"""

    def __init__(self, llm_client: MiniMaxClient):
        """
        Args:
            llm_client: MiniMaxClient实例
        """
        self.llm = llm_client

    def discover_strategy(self, market_context: str, existing_strategies: List[str]) -> Optional[Dict]:
        """发现新策略
        
        Args:
            market_context: 市场环境描述
            existing_strategies: 已有策略列表
        
        Returns:
            dict: 新策略建议，包含 name, hypothesis, select_rule, timing_rule
        """
        existing_str = '\n'.join(f"- {s}" for s in existing_strategies)
        
        prompt = f"""你是A股量化策略研究员。基于以下市场环境和已有策略，提出一个创新的策略假设。

## 当前市场环境
{market_context}

## 已有策略（请避免重复）
{existing_str}

## A股特性
- T+1交易制度
- 涨跌停限制（主板±10%，创业板/科创板±20%）
- 行业轮动频繁
- 北向资金影响显著
- 散户占比高，容易出现过度反应

## 输出要求
请输出一个JSON格式的策略建议：
{{
    "name": "策略名称（2-6个字）",
    "category": "策略类别（因子/事件/趋势/综合）",
    "hypothesis": "策略的核心假设和逻辑",
    "select_rule": "量化选股规则（具体、可执行）",
    "timing_rule": "买卖择时规则",
    "expected_market": "适合的市场环境（牛市/熊市/震荡/高波动）",
    "risk_factors": ["风险因素1", "风险因素2"]
}}

只输出JSON，不要其他文字：
"""
        
        response = self.llm.complete(
            prompt,
            system_prompt="你是一个专业的A股量化策略研究员，擅长发现创新的alpha因子和交易策略。",
            temperature=0.8,
            max_tokens=1500
        )
        
        if not response:
            return None
        
        # 解析JSON
        import re
        try:
            # 尝试直接解析
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试从响应中提取JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except:
                    pass
        return None

    def suggest_parameters(self, strategy: Dict, market_context: str) -> Optional[Dict]:
        """为策略建议优化参数
        
        Args:
            strategy: 策略字典
            market_context: 市场环境描述
        
        Returns:
            dict: 优化后的参数建议
        """
        prompt = f"""分析以下策略在当前市场环境下的参数优化建议。

## 策略信息
名称: {strategy.get('name')}
类别: {strategy.get('category')}
选股规则: {strategy.get('select_rule')}
择时规则: {strategy.get('timing_rule')}

## 当前市场环境
{market_context}

## 任务
请建议针对当前市场环境的参数调整：
1. 哪些参数需要收紧/放松？
2. 建议的具体参数值
3. 仓位管理建议
4. 风险控制建议

输出JSON格式：
{{
    "parameter_adjustments": [
        {{"parameter": "参数名", "current": "当前值", "suggested": "建议值", "reason": "调整原因"}}
    ],
    "position_management": "仓位管理建议",
    "risk_control": "风险控制建议"
}}

只输出JSON：
"""
        
        response = self.llm.complete(prompt, temperature=0.6, max_tokens=1000)
        
        if not response:
            return None
        
        import re
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except:
            pass
        return None


class MarketAnalyzer:
    """基于LLM的市场分析器"""

    def __init__(self, llm_client: MiniMaxClient):
        """
        Args:
            llm_client: MiniMaxClient实例
        """
        self.llm = llm_client

    def analyze_market(self, market_data: Dict) -> Optional[Dict]:
        """分析市场状态
        
        Args:
            market_data: 市场数据，包含指数点位、涨跌幅、成交量、波动率等信息
        
        Returns:
            dict: 市场分析结果
        """
        # 构建市场描述
        market_desc = self._format_market_data(market_data)
        
        prompt = f"""分析当前A股市场状态并给出策略建议。

## 市场数据
{market_desc}

## 分析任务
1. 判断当前市场状态（趋势/震荡/高波动/低波动）
2. 识别主要驱动因素
3. 评估市场情绪
4. 推荐适合当前市场的策略类型

## 输出格式
请输出JSON格式：
{{
    "market_state": "市场状态（上涨趋势/下跌趋势/震荡/高波动/低波动）",
    "confidence": "判断置信度（高/中/低）",
    "main_drivers": ["驱动因素1", "驱动因素2"],
    "sentiment": "市场情绪（乐观/中性/悲观）",
    "recommended_strategies": ["策略类型1", "策略类型2"],
    "risk_level": "风险等级（高/中/低）",
    "time_horizon": "预期持续时间（短期/中期/长期）",
    "analysis": "详细分析说明"
}}

只输出JSON：
"""
        
        response = self.llm.complete(
            prompt,
            system_prompt="你是一个专业的A股市场分析师，擅长判断市场趋势和状态。",
            temperature=0.5,
            max_tokens=1200
        )
        
        if not response:
            return None
        
        import re
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except:
            pass
        return None

    def _format_market_data(self, data: Dict) -> str:
        """格式化市场数据为文本描述"""
        lines = []
        
        if 'indices' in data:
            lines.append("### 主要指数")
            for name, info in data['indices'].items():
                change = info.get('change_pct', 0)
                direction = "↑" if change > 0 else "↓" if change < 0 else "→"
                lines.append(f"- {name}: {info.get('price', 'N/A')} ({direction}{abs(change):.2f}%)")
        
        if 'volume' in data:
            lines.append(f"\n### 成交量")
            lines.append(f"- 今日成交量: {data['volume']}")
            if 'volume_change' in data:
                lines.append(f"- 成交量变化: {data['volume_change']:.2f}%")
        
        if 'volatility' in data:
            lines.append(f"\n### 波动率")
            lines.append(f"- 历史波动率: {data['volatility']:.2f}%")
        
        if 'market_cap' in data:
            lines.append(f"\n### 市值")
            lines.append(f"- 总市值: {data['market_cap']}")
        
        if 'north_flow' in data:
            lines.append(f"\n### 北向资金")
            lines.append(f"- 净流入: {data['north_flow']}")
        
        if 'sector_performance' in data:
            lines.append(f"\n### 行业表现")
            for sector, change in data['sector_performance']:
                direction = "↑" if change > 0 else "↓"
                lines.append(f"- {sector}: {direction}{abs(change):.2f}%")
        
        return '\n'.join(lines) if lines else "暂无数据"

    def recommend_portfolio(self, market_analysis: Dict, available_strategies: List[Dict]) -> Optional[Dict]:
        """基于市场分析推荐策略组合
        
        Args:
            market_analysis: analyze_market() 返回的分析结果
            available_strategies: 可用策略列表，每个包含name, category, description
        
        Returns:
            dict: 推荐的策略组合和权重
        """
        strategies_desc = '\n'.join(
            f"- {s['name']} ({s.get('category', '未知')}): {s.get('description', '')}"
            for s in available_strategies
        )
        
        prompt = f"""基于市场分析结果，从以下策略中选择最优组合。

## 市场分析结果
市场状态: {market_analysis.get('market_state', '未知')}
推荐策略类型: {', '.join(market_analysis.get('recommended_strategies', []))}
风险等级: {market_analysis.get('risk_level', '未知')}
市场情绪: {market_analysis.get('sentiment', '未知')}

## 可用策略
{strategies_desc}

## 任务
1. 从可用策略中选择适合当前市场状态的组合
2. 给出每个策略的权重建议
3. 说明选择理由

## 输出格式
请输出JSON格式：
{{
    "selected_strategies": [
        {{"name": "策略名", "weight": 0.3, "reason": "选择理由"}}
    ],
    "portfolio_notes": "组合说明和注意事项",
    "expected_performance": "预期表现描述"
}}

只输出JSON：
"""
        
        response = self.llm.complete(
            prompt,
            system_prompt="你是一个专业的量化投资组合经理，擅长根据市场状态选择最优策略组合。",
            temperature=0.6,
            max_tokens=1000
        )
        
        if not response:
            return None
        
        import re
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except:
            pass
        return None


# === 便捷函数 ===

def create_minimax_client() -> MiniMaxClient:
    """创建MiniMax客户端（从环境变量读取配置）"""
    return MiniMaxClient()


def discover_new_strategy(market_context: str, existing_strategies: List[str]) -> Optional[Dict]:
    """发现新策略的便捷函数"""
    client = create_minimax_client()
    discovery = StrategyDiscovery(client)
    return discovery.discover_strategy(market_context, existing_strategies)


def analyze_current_market(market_data: Dict) -> Optional[Dict]:
    """分析市场的便捷函数"""
    client = create_minimax_client()
    analyzer = MarketAnalyzer(client)
    return analyzer.analyze_market(market_data)


if __name__ == "__main__":
    # 使用示例
    print("MiniMax LLM 客户端使用示例：")
    print()
    print("=" * 60)
    
    # 1. 创建客户端
    client = create_minimax_client()
    
    if not client.api_key:
        print("请先设置环境变量:")
        print("  set MINIMAX_API_KEY=your_api_key")
        print("  set MINIMAX_GROUP_ID=your_group_id")
    else:
        # 2. 策略发现示例
        print("\n策略发现示例:")
        existing = ["低PE策略", "RSI超卖策略", "MACD金叉策略"]
        market = "上证指数在3000点附近震荡，成交量萎缩，市场情绪谨慎"
        
        strategy = client.discover_strategy(market, existing)
        if strategy:
            print(f"发现新策略: {strategy.get('name')}")
            print(f"假设: {strategy.get('hypothesis')}")
        
        # 3. 市场分析示例
        print("\n市场分析示例:")
        market_data = {
            'indices': {
                '上证指数': {'price': 3015, 'change_pct': 0.5},
                '深证成指': {'price': 9215, 'change_pct': 0.8},
                '创业板': {'price': 1665, 'change_pct': 1.2}
            },
            'volume': '较昨日减少15%',
            'volatility': 12.5,
            'north_flow': '净流入30亿'
        }
        
        analyzer = MarketAnalyzer(client)
        analysis = analyzer.analyze_market(market_data)
        if analysis:
            print(f"市场状态: {analysis.get('market_state')}")
            print(f"推荐策略: {', '.join(analysis.get('recommended_strategies', []))}")
