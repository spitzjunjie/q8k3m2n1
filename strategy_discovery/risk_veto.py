# -*- coding: utf-8 -*-
"""
风控否决闸（借鉴 TradingAgents 的 Risk Management Team 设计）

解决：风险散落在各个策略里，交易员出决策后没有独立的一票否决。
方案：独立的"风控"角色，只评估风险、不关心收益，对高风险决策有否决权。

用法：
    from strategy_discovery.risk_veto import RiskVetoGate
    gate = RiskVetoGate(llm_client)   # llm_client 可选，缺省走规则兜底
    review = gate.review(decision, market_context)
    # review: {'approved': bool, 'risk_level': 'low/medium/high', 'reasons': [...]}
"""

import json
import re


class RiskVetoGate:
    """独立风控否决闸"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def review(self, decision, market_context=""):
        """评估决策风险，返回是否放行。

        Args:
            decision: dict，可含 stocks(候选)、strategy、backtest_result 等
            market_context: 市场环境描述（可选）
        """
        rule = self._rule_based(decision)
        llm = self._llm_review(decision, market_context)
        if llm and isinstance(llm, dict):
            llm.setdefault("risk_level", rule.get("risk_level", "medium"))
            return llm
        return rule

    def _rule_based(self, decision):
        decision = decision or {}
        reasons = []
        bt = decision.get("backtest_result") or {}
        max_dd = bt.get("max_drawdown", 0)
        win_rate = bt.get("win_rate", 1.0)
        n_stocks = len(decision.get("stocks") or [])

        if isinstance(max_dd, (int, float)) and max_dd > 20:
            reasons.append(f"最大回撤 {max_dd}% 过高")
        if isinstance(win_rate, (int, float)) and win_rate < 0.4:
            reasons.append(f"胜率 {win_rate:.0%} 过低")
        if n_stocks == 1:
            reasons.append("持仓过度集中（仅 1 只）")

        risk_level = "high" if reasons else "medium"
        return {
            "approved": not reasons,
            "risk_level": risk_level,
            "reasons": reasons or ["未发现明显风险"],
        }

    def _llm_review(self, decision, market_context):
        if not self.llm:
            return None
        try:
            decision_text = json.dumps(decision or {}, ensure_ascii=False, indent=2, default=str)[:2000]
        except Exception:
            decision_text = str(decision)[:2000]

        prompt = f"""你是A股量化系统的独立风控官。你只评估风险、不关心收益，对高风险决策有一票否决权。

## 决策内容
{decision_text}

## 市场环境
{market_context or "(未提供)"}

请输出严格 JSON（不要其他文字）：
{{"approved": true 或 false, "risk_level": "low/medium/high", "reasons": ["风险点..."]}}
"""
        resp = self._complete(prompt, "你是独立风控官，只评估风险，有权否决。")
        return self._parse_json(resp)

    def _complete(self, prompt, system_prompt):
        try:
            return self.llm.complete(
                prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=500
            )
        except TypeError:
            try:
                return self.llm.complete(prompt)
            except Exception:
                return None
        except Exception:
            return None

    def _parse_json(self, text):
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    return None
        return None
