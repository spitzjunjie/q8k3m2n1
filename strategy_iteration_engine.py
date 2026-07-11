# -*- coding: utf-8 -*-
"""
策略迭代优化引擎
基于 Loop Engineering 的 ODAEI 循环

Observe → Decide → Act → Evaluate → Iterate

自动对策略进行迭代优化，直到收敛或达到终止条件
"""

import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import sys

sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

from data.akshare_helper import AKShareHelper
from timing.timing import TimingEngine
from evaluation import StrategyEvaluator


@dataclass
class IterationConfig:
    """迭代配置"""
    max_iterations: int = 10           # 单策略最大迭代次数
    min_improvement: float = 5.0       # 最小改进分数
    consecutive_failures: int = 3       # 收敛判定（连续失败次数）
    time_limit_seconds: int = 1800      # 时间限制（30分钟）
    optimization_threshold: float = 35.0  # 需要优化的评分阈值


@dataclass
class OptimizationRecord:
    """优化记录"""
    strategy_name: str
    iteration: int
    action_type: str          # fix/optimize/fine_tune/eliminate
    old_score: float
    new_score: float
    improvement: float
    action_detail: str
    timestamp: str


class StrategyIterationEngine:
    """策略迭代优化引擎
    
    实现 ODAEI 循环的自动化策略迭代
    """
    
    def __init__(self, config: IterationConfig = None):
        self.config = config or IterationConfig()
        self.helper = AKShareHelper()
        self.timing = TimingEngine()
        self.evaluator = StrategyEvaluator()
        
        # 状态
        self.records: List[OptimizationRecord] = []
        self.optimization_history_file = "output/optimization_history.json"
        self.iteration_count = 0
        self.consecutive_failures = 0
        
        # 读取历史优化记录
        self._load_history()
        
    def _load_history(self):
        """加载历史优化记录"""
        if os.path.exists(self.optimization_history_file):
            try:
                with open(self.optimization_history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = [OptimizationRecord(**r) for r in data.get('records', [])]
            except:
                self.records = []
    
    def _save_history(self):
        """保存优化记录"""
        os.makedirs("output", exist_ok=True)
        with open(self.optimization_history_file, 'w', encoding='utf-8') as f:
            json.dump({
                'records': [asdict(r) for r in self.records],
                'last_update': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def run(self, strategy_name: str, strategy_class=None) -> Dict:
        """运行 ODAEI 循环优化单个策略
        
        Args:
            strategy_name: 策略名称
            strategy_class: 策略类（可选）
        
        Returns:
            dict: 优化结果
        """
        print("=" * 60)
        print(f"启动策略迭代: {strategy_name}")
        print(f"配置: 最大迭代={self.config.max_iterations}, 最小改进={self.config.min_improvement}")
        print("=" * 60)
        
        start_time = time.time()
        results = []
        
        for i in range(self.config.max_iterations):
            # 检查时间限制
            if time.time() - start_time > self.config.time_limit_seconds:
                print(f"\n⚠️ 达到时间限制，终止迭代")
                break
            
            self.iteration_count = i + 1
            print(f"\n--- 迭代 {self.iteration_count}/{self.config.max_iterations} ---")
            
            # ==================== O: Observe ====================
            state = self._observe(strategy_name)
            print(f"  [观察] 评分={state['score']:.1f} 等级={state['grade']} 收益={state['return']*100:.1f}%")
            
            # ==================== D: Decide ====================
            action = self._decide(state)
            
            if action is None:
                print(f"  [决策] 无需优化（A级策略）")
                break
                
            print(f"  [决策] {action['type']}: {action['reason']}")
            
            # ==================== A: Act ====================
            result = self._act(action, strategy_name, strategy_class)
            
            # ==================== E: Evaluate ====================
            evaluation = self._evaluate(result, state['score'])
            
            # ==================== I: Iterate ====================
            print(f"  [评估] 改进={evaluation['improvement']:+.1f}分")
            
            if evaluation['passed']:
                self.consecutive_failures = 0
                print(f"  [迭代] ✅ 继续优化")
            else:
                self.consecutive_failures += 1
                print(f"  [迭代] ❌ 连续失败: {self.consecutive_failures}/{self.config.consecutive_failures}")
                
                if self.consecutive_failures >= self.config.consecutive_failures:
                    print(f"\n📊 达到收敛条件，停止迭代")
                    break
        
        # 生成报告
        report = self._generate_report(strategy_name, results, start_time)
        return report
    
    def run_all(self, strategy_pool: List[Dict]) -> Dict:
        """批量优化所有策略
        
        Args:
            strategy_pool: 策略池 [{'name': xxx, 'score': xxx, 'grade': xxx}, ...]
        
        Returns:
            dict: 批量优化结果
        """
        print("=" * 60)
        print(f"批量优化 {len(strategy_pool)} 个策略")
        print("=" * 60)
        
        start_time = time.time()
        optimized = []
        converged = []
        eliminated = []
        
        # 按评分排序，D级优先
        sorted_pool = sorted(strategy_pool, key=lambda x: x.get('score', 0))
        
        for strategy_info in sorted_pool:
            name = strategy_info['name']
            score = strategy_info.get('score', 0)
            grade = strategy_info.get('grade', 'D')
            
            # 跳过A级
            if grade == 'A':
                print(f"\n⏭️ {name}: A级，无需优化")
                continue
            
            # 检查是否已收敛
            recent_optimizations = [r for r in self.records if r.strategy_name == name][-3:]
            if all(r.improvement < self.config.min_improvement for r in recent_optimizations):
                print(f"\n⏭️ {name}: 已收敛，跳过")
                converged.append(name)
                continue
            
            # 执行优化
            print(f"\n{'='*50}")
            print(f"优化: {name} (当前评分: {score:.1f})")
            result = self.run(name)
            
            if result['status'] == 'optimized':
                optimized.append(result)
            elif result['status'] == 'eliminated':
                eliminated.append(result)
        
        # 汇总报告
        report = {
            'total_strategies': len(strategy_pool),
            'optimized': len(optimized),
            'converged': len(converged),
            'eliminated': len(eliminated),
            'total_time': time.time() - start_time,
            'optimization_details': optimized,
            'converged_strategies': converged,
            'eliminated_strategies': eliminated
        }
        
        print("\n" + "=" * 60)
        print("批量优化完成!")
        print(f"优化: {len(optimized)} 个")
        print(f"收敛: {len(converged)} 个")
        print(f"淘汰: {len(eliminated)} 个")
        print(f"耗时: {report['total_time']:.1f} 秒")
        print("=" * 60)
        
        return report
    
    def _observe(self, strategy_name: str) -> Dict:
        """O: 观察策略当前状态"""
        # 读取回测结果
        data_file = "output/strategy_data.json"
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
                strategy = all_data.get(strategy_name, {})
        else:
            strategy = {}
        
        return {
            'name': strategy_name,
            'score': strategy.get('composite_score', 0),
            'grade': strategy.get('grade', 'D'),
            'return': strategy.get('total_return', 0),
            'sharpe': strategy.get('sharpe_ratio', 0),
            'drawdown': strategy.get('max_drawdown', 0),
            'win_rate': strategy.get('win_rate', 0),
        }
    
    def _decide(self, state: Dict) -> Optional[Dict]:
        """D: 根据状态决定下一步行动"""
        grade = state['grade']
        score = state['score']
        
        if grade == 'A':
            return None  # 无需优化
        
        if grade == 'D' or score < 35:
            if state['return'] < -0.05:
                return {
                    'type': 'eliminate',
                    'reason': '严重亏损(>5%)，建议淘汰'
                }
            return {
                'type': 'fix',
                'reason': 'D级策略，需要修复选股逻辑'
            }
        
        if grade == 'C' or score < 50:
            return {
                'type': 'optimize',
                'reason': 'C级策略，尝试参数优化'
            }
        
        if grade == 'B' or score < 65:
            return {
                'type': 'fine_tune',
                'reason': 'B级策略，进行精细调参'
            }
        
        return None
    
    def _act(self, action: Dict, strategy_name: str, strategy_class) -> Dict:
        """A: 执行优化行动"""
        action_type = action['type']
        
        if action_type == 'eliminate':
            return {
                'type': 'eliminate',
                'new_score': 0,
                'detail': '标记为待淘汰'
            }
        
        # 对于其他类型，需要实际修改策略参数并回测
        # 这里简化处理，实际使用时需要读取策略代码、修改参数、重新回测
        
        # 模拟优化效果（实际使用时需要真正执行）
        old_state = self._observe(strategy_name)
        simulated_improvement = self._simulate_optimization(action_type, old_state)
        
        new_score = old_state['score'] + simulated_improvement
        
        return {
            'type': action_type,
            'old_score': old_state['score'],
            'new_score': new_score,
            'improvement': simulated_improvement,
            'detail': f'{action_type} 完成'
        }
    
    def _simulate_optimization(self, action_type: str, state: Dict) -> float:
        """模拟优化效果（实际使用时需要真正回测）"""
        import random
        
        if action_type == 'fix':
            # 修复类优化，效果较大
            return random.uniform(5, 15)
        elif action_type == 'optimize':
            # 参数优化，效果中等
            return random.uniform(2, 8)
        elif action_type == 'fine_tune':
            # 精细调参，效果较小
            return random.uniform(0, 3)
        
        return 0
    
    def _evaluate(self, result: Dict, old_score: float) -> Dict:
        """E: 评估优化效果"""
        improvement = result.get('improvement', 0)
        
        evaluation = {
            'improvement': improvement,
            'passed': improvement >= self.config.min_improvement,
            'grade_changed': self._get_grade(old_score) != self._get_grade(old_score + improvement)
        }
        
        return evaluation
    
    def _get_grade(self, score: float) -> str:
        """根据评分获取等级"""
        if score >= 80:
            return 'S'
        elif score >= 65:
            return 'A'
        elif score >= 50:
            return 'B'
        elif score >= 35:
            return 'C'
        else:
            return 'D'
    
    def _generate_report(self, strategy_name: str, results: List, start_time: float) -> Dict:
        """生成优化报告"""
        strategy_records = [r for r in self.records if r.strategy_name == strategy_name]
        
        if not strategy_records:
            return {
                'strategy': strategy_name,
                'status': 'no_optimization',
                'iterations': 0
            }
        
        best_score = max(r.new_score for r in strategy_records)
        final_score = strategy_records[-1].new_score if strategy_records else 0
        
        return {
            'strategy': strategy_name,
            'status': 'optimized' if final_score > strategy_records[0].old_score else 'converged',
            'iterations': len(strategy_records),
            'initial_score': strategy_records[0].old_score,
            'final_score': final_score,
            'best_score': best_score,
            'total_improvement': final_score - strategy_records[0].old_score,
            'converged': self.consecutive_failures >= self.config.consecutive_failures,
            'time_elapsed': time.time() - start_time
        }


# ==================== 快速使用示例 ====================

if __name__ == "__main__":
    # 示例：对指定策略运行迭代优化
    engine = StrategyIterationEngine()
    
    # 单策略优化
    result = engine.run("低PE")
    
    print("\n优化结果:")
    print(f"  策略: {result['strategy']}")
    print(f"  状态: {result['status']}")
    print(f"  迭代次数: {result['iterations']}")
    print(f"  初始评分: {result['initial_score']:.1f}")
    print(f"  最终评分: {result['final_score']:.1f}")
    print(f"  总改进: {result['total_improvement']:+.1f}分")
