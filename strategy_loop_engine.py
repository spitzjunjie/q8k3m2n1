# -*- coding: utf-8 -*-
"""
策略开发 Loop Engine
基于 Loop Engineering 框架的自动化策略迭代系统

ODAEI 循环:
Observe → Decide → Act → Evaluate → Iterate

适用场景：
- 策略自动生成与优化
- 参数自动调优
- 策略组合优化
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

# 导入策略相关模块
import sys
sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from data.akshare_helper import AKShareHelper
from timing.timing import TimingEngine
from trading.simulator import TradingSimulator
from evaluation import StrategyEvaluator


class LoopState(Enum):
    """Loop 状态"""
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    MAX_ITERATIONS = "max_iterations"
    TERMINATED = "terminated"


@dataclass
class LoopConfig:
    """Loop 配置"""
    name: str = "策略开发循环"
    max_iterations: int = 10
    goal: str = "开发可上线策略"
    
    # 终止条件
    min_sharpe: float = 1.5
    max_drawdown: float = 0.15
    min_win_rate: float = 0.55
    min_trades: int = 20
    min_return: float = 0.10
    
    # 时间限制
    timeout_seconds: int = 3600


@dataclass
class IterationResult:
    """迭代结果"""
    iteration: int
    state: LoopState
    action: str
    result: Any
    evaluation: Optional[Dict] = None
    error: Optional[str] = None
    duration: float = 0
    improvement: float = 0  # 相对上次的改进


class StrategyLoopEngine:
    """策略开发 Loop 引擎
    
    实现 ODAEI 循环的自动化策略迭代
    """
    
    def __init__(self, config: LoopConfig = None):
        self.config = config or LoopConfig()
        self.helper = AKShareHelper()
        self.timing = TimingEngine()
        self.evaluator = StrategyEvaluator()
        
        # 状态
        self.iterations: List[IterationResult] = []
        self.current_iteration = 0
        self.best_strategy = None
        self.best_score = 0
        self.state = LoopState.RUNNING
        
        # 历史记录
        self.history_file = f"output/loop_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs("output", exist_ok=True)
    
    def run(self, strategy_class=None, initial_params: Dict = None) -> Dict:
        """运行 Loop
        
        Args:
            strategy_class: 策略类
            initial_params: 初始参数
        
        Returns:
            dict: 最终结果
        """
        print("=" * 60)
        print(f"启动策略 Loop: {self.config.name}")
        print(f"目标: {self.config.goal}")
        print(f"最大迭代: {self.config.max_iterations}")
        print("=" * 60)
        
        start_time = time.time()
        
        while self.current_iteration < self.config.max_iterations:
            if time.time() - start_time > self.config.timeout_seconds:
                self.state = LoopState.TERMINATED
                break
            
            self.current_iteration += 1
            print(f"\n--- 迭代 {self.current_iteration}/{self.config.max_iterations} ---")
            
            # ODAEI 循环
            iteration_result = self._run_iteration(strategy_class, initial_params)
            self.iterations.append(iteration_result)
            
            # 评估结果
            if iteration_result.evaluation:
                score = iteration_result.evaluation.get('composite_score', 0)
                
                # 更新最佳策略
                if score > self.best_score:
                    self.best_score = score
                    self.best_strategy = iteration_result.result
                    print(f"  🏆 新最佳策略! 分数: {score:.1f}")
                
                # 检查终止条件
                if self._check_termination(iteration_result.evaluation):
                    self.state = LoopState.SUCCESS
                    print(f"\n✅ 达到终止条件，Loop 结束!")
                    break
            
            # 保存历史
            self._save_history()
        
        # 检查是否达到最大迭代
        if self.state == LoopState.RUNNING:
            self.state = LoopState.MAX_ITERATIONS
            print(f"\n⚠️ 达到最大迭代次数 {self.config.max_iterations}")
        
        return self._generate_report()
    
    def _run_iteration(self, strategy_class, initial_params) -> IterationResult:
        """执行一次迭代
        
        ODAEI 循环:
        Observe → Decide → Act → Evaluate → Iterate
        """
        iter_start = time.time()
        
        # ==================== O: Observe ====================
        observation = self._observe()
        print(f"  [观察] {observation}")
        
        # ==================== D: Decide ====================
        decision = self._decide(observation)
        print(f"  [决策] {decision['action']}")
        
        # ==================== A: Act ====================
        result = self._act(decision, strategy_class, initial_params)
        
        # ==================== E: Evaluate ====================
        evaluation = self._evaluate(result)
        
        # ==================== I: Iterate ====================
        improvement = self._calculate_improvement(evaluation)
        
        duration = time.time() - iter_start
        
        return IterationResult(
            iteration=self.current_iteration,
            state=LoopState.RUNNING,
            action=decision['action'],
            result=result,
            evaluation=evaluation,
            duration=duration,
            improvement=improvement
        )
    
    def _observe(self) -> str:
        """O: 观察 - 收集环境状态"""
        observations = []
        
        # 观察当前迭代次数
        observations.append(f"迭代{self.current_iteration}")
        
        # 观察历史最佳分数
        if self.best_score > 0:
            observations.append(f"历史最佳分数={self.best_score:.1f}")
        
        # 观察最近一次的表现
        if self.iterations:
            last_eval = self.iterations[-1].evaluation
            if last_eval:
                observations.append(
                    f"上次: 夏普={last_eval.get('sharpe_ratio', 0):.2f}, "
                    f"收益={last_eval.get('total_return', 0)*100:.1f}%, "
                    f"胜率={last_eval.get('win_rate', 0)*100:.0f}%"
                )
        
        return ", ".join(observations)
    
    def _decide(self, observation: str) -> Dict:
        """D: 决策 - 基于观察决定下一步动作"""
        
        # 如果是第一次迭代，生成策略
        if self.current_iteration == 1:
            return {"action": "create_strategy", "params": {}}
        
        # 如果上次评估失败，修复策略
        if self.iterations and self.iterations[-1].error:
            return {"action": "fix_strategy", "params": {}}
        
        # 如果收益为负或回撤过大，优化参数
        if self.iterations:
            last_eval = self.iterations[-1].evaluation
            if last_eval:
                ret = last_eval.get('total_return', 0)
                dd = last_eval.get('max_drawdown', 0)
                
                if ret < 0:
                    return {"action": "optimize_parameters", "direction": "more_conservative"}
                if dd > self.config.max_drawdown:
                    return {"action": "optimize_parameters", "direction": "reduce_risk"}
        
        # 默认：继续优化
        return {"action": "optimize_parameters", "direction": "fine_tune"}
    
    def _act(self, decision: Dict, strategy_class, initial_params) -> Any:
        """A: 行动 - 执行决策"""
        action = decision['action']
        
        if action == "create_strategy":
            # 创建新策略
            if strategy_class:
                strategy = strategy_class()
                strategy.name = f"Loop策略_{self.current_iteration}"
                return strategy
            return None
        
        elif action == "fix_strategy":
            # 修复策略（简化处理）
            return self.best_strategy
        
        elif action == "optimize_parameters":
            # 优化参数
            return self.best_strategy
        
        return None
    
    def _evaluate(self, result) -> Optional[Dict]:
        """E: 评估 - 验证执行结果"""
        if result is None:
            return None
        
        try:
            # 运行回测
            from backtest import run_strategy
            backtest_result = run_strategy(result, self.helper, self.timing, date=None)
            
            # 评估
            evaluation = self.evaluator.evaluate(backtest_result)
            
            # 打印评估结果
            print(f"  [评估] 分数={evaluation.get('composite_score', 0):.1f} "
                  f"等级={evaluation.get('grade', 'N/A')} "
                  f"收益={evaluation.get('total_return', 0)*100:.1f}% "
                  f"夏普={evaluation.get('sharpe_ratio', 0):.2f}")
            
            return evaluation
            
        except Exception as e:
            print(f"  [错误] 评估失败: {e}")
            return None
    
    def _check_termination(self, evaluation: Dict) -> bool:
        """I: 检查是否满足终止条件"""
        if not evaluation:
            return False
        
        # 检查各项指标
        checks = {
            "夏普比率": evaluation.get('sharpe_ratio', 0) >= self.config.min_sharpe,
            "最大回撤": evaluation.get('max_drawdown', 1) <= self.config.max_drawdown,
            "胜率": evaluation.get('win_rate', 0) >= self.config.min_win_rate,
            "收益": evaluation.get('total_return', 0) >= self.config.min_return,
        }
        
        passed = sum(1 for v in checks.values() if v)
        print(f"  [终止检查] {passed}/{len(checks)} 项达标: {checks}")
        
        # 至少3项达标
        return passed >= 3
    
    def _calculate_improvement(self, evaluation: Dict) -> float:
        """计算改进幅度"""
        if not evaluation or not self.iterations:
            return 0
        
        current_score = evaluation.get('composite_score', 0)
        last_score = self.iterations[-1].evaluation.get('composite_score', 0) if self.iterations[-1].evaluation else 0
        
        return current_score - last_score
    
    def _save_history(self):
        """保存历史记录"""
        history = {
            "config": asdict(self.config),
            "current_iteration": self.current_iteration,
            "best_score": self.best_score,
            "state": self.state.value,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "action": it.action,
                    "state": it.state.value,
                    "score": it.evaluation.get('composite_score', 0) if it.evaluation else 0,
                    "improvement": it.improvement,
                    "duration": it.duration
                }
                for it in self.iterations
            ]
        }
        
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def _generate_report(self) -> Dict:
        """生成最终报告"""
        report = {
            "status": self.state.value,
            "iterations": self.current_iteration,
            "best_score": self.best_score,
            "best_strategy": self.best_strategy.name if self.best_strategy else None,
            "history_file": self.history_file,
            "recommendations": self._generate_recommendations()
        }
        
        print("\n" + "=" * 60)
        print("Loop 结束报告")
        print("=" * 60)
        print(f"状态: {self.state.value}")
        print(f"迭代次数: {self.current_iteration}")
        print(f"最佳分数: {self.best_score:.1f}")
        print(f"最佳策略: {report['best_strategy']}")
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if self.state == LoopState.SUCCESS:
            recommendations.append("✅ 策略已达到上线标准")
            recommendations.append("建议：可以开始实盘测试")
        elif self.state == LoopState.MAX_ITERATIONS:
            recommendations.append("⚠️ 需要更多迭代或调整策略方向")
            recommendations.append("建议：尝试不同的策略类型")
        
        if self.iterations:
            last_eval = self.iterations[-1].evaluation
            if last_eval:
                if last_eval.get('max_drawdown', 0) > self.config.max_drawdown:
                    recommendations.append("🔧 回撤过大，建议增加止损机制")
                if last_eval.get('win_rate', 0) < self.config.min_win_rate:
                    recommendations.append("🔧 胜率偏低，建议优化选股条件")
        
        return recommendations


def run_strategy_loop(strategy_class=None, config: LoopConfig = None):
    """运行策略 Loop 的便捷函数"""
    engine = StrategyLoopEngine(config)
    return engine.run(strategy_class)


# ==================== 快速使用示例 ====================

if __name__ == "__main__":
    # 示例：使用情绪冰点策略进行 Loop 优化
    from strategies.market_sentiment_strategy import SentimentIcePointStrategy
    
    # 配置
    config = LoopConfig(
        name="情绪冰点策略优化",
        max_iterations=5,
        min_sharpe=1.0,
        max_drawdown=0.20,
        min_win_rate=0.50,
        min_return=0.05,
        timeout_seconds=600
    )
    
    # 运行 Loop
    result = run_strategy_loop(SentimentIcePointStrategy, config)
    
    print("\n推荐操作:")
    for rec in result['recommendations']:
        print(f"  {rec}")
