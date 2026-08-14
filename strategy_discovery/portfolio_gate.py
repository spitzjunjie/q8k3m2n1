# -*- coding: utf-8 -*-
"""
组合经理拍板（借鉴 TradingAgents 的 Portfolio Manager 设计）

解决：各策略各自下注，缺少一个聚合"所有信号 + 风控意见"的最终决策层。
方案：独立"组合经理"角色，聚合信号 + 风控意见，做最终"买不买、买多少"的拍板。

用法：
    from strategy_discovery.portfolio_gate import PortfolioDecisionGate
    pm = PortfolioDecisionGate(llm_client)
    final = pm.decide(signals, risk_review, market_context)
    # final: {'action': 'approve'/'reject', 'position': 0.0~1.0, 'reason': '...'}
"""

import json
import re


class PortfolioDecisionGate:
    """组合经理最终拍板"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def decide(self, signals, risk_review, market_context=""):
        """最终拍板。

        Args:
            signals: 策略/选股信号（dict 或 str）
            risk_review: RiskVetoGate.review() 的输出（含 approved/risk_level/reasons）
            market_context: 市场环境描述（可选）
        """
        # 风控否决直接拒绝，不进入 LLM
        if isinstance(risk_review, dict) and risk_review.get("approved") is False:
            return {
                "action": "reject",
                "position": 0.0,
                "reason": "风控否决：" + "；".join(risk_review.get("reasons", ["高风险"])),
            }

        if not self.llm:
            return {"action": "approve", "position": 0.5, "reason": "无 LLM，按默认半仓放行"}

        if isinstance(signals, str):
            signals_text = signals[:2000]
        else:
            try:
                signals_text = json.dumps(signals, ensure_ascii=False, indent=2, default=str)[:2000]
            except Exception:
                signals_text = str(signals)[:2000]

        try:
            risk_text = json.dumps(risk_review or {}, ensure_ascii=False, indent=2, default=str)[:1000]
        except Exception:
            risk_text = str(risk_review or "")[:1000]

        prompt = f"""你是A股量化组合经理，做最终"买不买、买多少"的拍板，仓位偏保守。

## 信号/分析
{signals_text}

## 风控意见
{risk_text}

## 市场环境
{market_context or "(未提供)"}

请输出严格 JSON（不要其他文字）：
{{"action": "approve 或 reject", "position": 0.0到1.0之间的仓位比例, "reason": "一句话理由"}}
"""
        resp = self._complete(prompt, "你是组合经理，综合信号与风控做最终决策，仓位保守。")
        parsed = self._parse_json(resp)
        if parsed:
            parsed.setdefault("action", "reject")
            parsed.setdefault("position", 0.0)
            parsed.setdefault("reason", "")
            return parsed
        return {"action": "reject", "position": 0.0, "reason": "决策生成失败，默认不通过"}

    def _complete(self, prompt, system_prompt):
        try:
            return self.llm.complete(
                prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=400
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
