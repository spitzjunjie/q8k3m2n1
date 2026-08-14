# -*- coding: utf-8 -*-
"""
多空对抗辩论器（借鉴 TradingAgents 的 Researcher Team 设计）

解决：单边策略信号容易"过度自信"，只看到支持自己的证据。
方案：让"看多研究员"和"看空研究员"两个角色对同一份信号/假设互相挑刺，
      再综合出"共识 + 分歧点 + 最终倾向"，交下游决策。

这是三条"值得抄"中的第 1 条（优先级最高、改动最小）。
另外两条（风控否决闸、组合经理拍板）见 docs/待办清单.md，暂未实现。

用法：
    from strategy_discovery.bull_bear_debate import BullBearDebater

    debater = BullBearDebater(llm_client)   # llm_client 实现 complete(prompt, ...) -> str
    result = debater.debate(market_context, hypothesis)
    # result: {'bull_case', 'bear_case', 'consensus', 'disagreements', 'verdict', 'refined_hypothesis'}

接入点建议（不改现有逻辑，仅在需要时调用）：
    在 StrategyDiscoverer.discover() 的"生成假设"之后、"生成代码"之前，
    用 debate() 的结果决定：verdict 为 bearish 时可直接放弃该假设，避免生成无谓代码。
"""

import json
import re


class BullBearDebater:
    """多空对抗辩论器"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def debate(self, market_context, hypothesis):
        """对策略假设做多空辩论。

        Args:
            market_context: 市场环境描述文本
            hypothesis: 策略假设（dict 或 str）

        Returns:
            dict 或 None（LLM 全部失败时）
        """
        hyp_text = self._fmt(hypothesis)

        bull = self._bull_case(market_context, hyp_text)
        bear = self._bear_case(market_context, hyp_text)

        if not bull and not bear:
            return None

        synthesis = self._synthesize(hyp_text, bull, bear)

        return {
            "bull_case": bull,
            "bear_case": bear,
            "consensus": synthesis.get("consensus", ""),
            "disagreements": synthesis.get("disagreements", []),
            "verdict": synthesis.get("verdict", "neutral"),
            "refined_hypothesis": synthesis.get("refined_hypothesis", hypothesis),
        }

    # ---- 内部 ----

    def _fmt(self, hypothesis):
        if isinstance(hypothesis, dict):
            try:
                return json.dumps(hypothesis, ensure_ascii=False, indent=2)
            except Exception:
                return str(hypothesis)
        return str(hypothesis)

    def _bull_case(self, market_context, hyp_text):
        prompt = f"""你是A股量化策略的"看多研究员"。请为下面的策略假设找出最强有力的支持论据，并指出它最可能跑赢的场景。

## 市场环境
{market_context}

## 策略假设
{hyp_text}

输出（中文，直接文字）：
1. 3-5 条看多论据（每条一句话）
2. 该策略最可能跑赢的场景
"""
        return self._complete(prompt, "你是看多研究员，为策略找支持论据，保持客观、不回避风险。")

    def _bear_case(self, market_context, hyp_text):
        prompt = f"""你是A股量化策略的"看空研究员"。请为下面的策略假设找出最致命的漏洞和反例，重点指出它可能失效的场景。

## 市场环境
{market_context}

## 策略假设
{hyp_text}

输出（中文，直接文字）：
1. 3-5 条看空论据（每条一句话）
2. 该策略最可能失效的场景
"""
        return self._complete(prompt, "你是看空研究员，为策略找漏洞和反例，保持客观、不夸大。")

    def _synthesize(self, hyp_text, bull, bear):
        prompt = f"""以下是同一策略假设的多空双方辩论结果，请综合出结论。

## 策略假设
{hyp_text}

## 看多观点
{bull or "(无)"}

## 看空观点
{bear or "(无)"}

请输出严格 JSON（不要其他文字）：
{{
  "consensus": "双方共识（一句话）",
  "disagreements": ["分歧点1", "分歧点2"],
  "verdict": "bullish / bearish / neutral",
  "refined_hypothesis": "综合辩论后修正的策略假设（一句话；若无需修正，原样复述原假设）"
}}
"""
        resp = self._complete(prompt, "你是首席研究员，综合多空观点给出客观结论。")
        return self._parse_json(resp)

    def _complete(self, prompt, system_prompt):
        try:
            return self.llm.complete(
                prompt, system_prompt=system_prompt, temperature=0.4, max_tokens=800
            )
        except TypeError:
            # 兼容只支持 complete(prompt) 的 client
            try:
                return self.llm.complete(prompt)
            except Exception as e:
                return f"(LLM调用失败: {e})"
        except Exception as e:
            return f"(LLM调用失败: {e})"

    def _parse_json(self, text):
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
        return {}
