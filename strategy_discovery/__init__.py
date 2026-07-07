# -*- coding: utf-8 -*-
"""
LLM驱动策略发现模块
基于论文笔记（Alpha-R1、QuantEvolve、Automate-Strategy-Finding-with-LLM）
建立"假设生成→代码生成→回测验证→自动上线"流水线
"""

from .discoverer import StrategyDiscoverer, GLMClient, DeepSeekClient
from .market_analyzer import MarketAnalyzer

__all__ = ['StrategyDiscoverer', 'MarketAnalyzer', 'GLMClient', 'DeepSeekClient']
