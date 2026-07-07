# -*- coding: utf-8 -*-
"""
策略组合优化器
根据评级和相关性自动配置策略权重
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class StrategyPortfolio:
    """策略组合管理器"""

    def __init__(self, config_path='data/portfolio_config.json'):
        self.config_path = config_path
        self.weights = {}
        self.load_config()

    def load_config(self):
        """加载配置"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.weights = config.get('weights', {})
                self.method = config.get('method', 'rating')
        else:
            self.method = 'rating'
            self.weights = {}

    def save_config(self):
        """保存配置"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        config = {
            'method': self.method,
            'weights': self.weights,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def optimize_by_rating(self, strategies: List[Dict]) -> Dict[str, float]:
        """根据评级优化权重
        A级: 30%, B级: 20%, C级: 10%, D级: 5%
        """
        weights = {}

        # 按评级分组
        grade_weights = {'A': 0.30, 'B': 0.20, 'C': 0.10, 'D': 0.05}
        grade_groups = {'A': [], 'B': [], 'C': [], 'D': []}

        for s in strategies:
            grade = s.get('grade', 'D')
            if grade not in grade_groups:
                grade_groups['D'].append(s)
            else:
                grade_groups[grade].append(s)

        # 计算每个评级的平均权重
        for grade, group in grade_groups.items():
            if group:
                base_weight = grade_weights.get(grade, 0.05)
                equal_weight = base_weight / len(group)
                for s in group:
                    weights[s['name']] = round(equal_weight, 4)

        self.weights = weights
        self.method = 'rating'
        self.save_config()
        return weights

    def optimize_by_sharpe(self, strategies: List[Dict], min_sharpe: float = 1.0) -> Dict[str, float]:
        """根据夏普比率优化权重
        只选取夏普>min_sharpe的策略，按夏普比例分配权重
        """
        weights = {}

        # 过滤有效策略
        valid_strategies = [s for s in strategies if s.get('sharpe_ratio', 0) >= min_sharpe]

        if not valid_strategies:
            print(f"[警告] 没有夏普比率>={min_sharpe}的策略")
            return self.optimize_by_rating(strategies)

        # 计算总夏普
        total_sharpe = sum(s.get('sharpe_ratio', 0) for s in valid_strategies)

        # 按夏普比例分配
        for s in valid_strategies:
            sharpe = s.get('sharpe_ratio', 0)
            weight = sharpe / total_sharpe
            weights[s['name']] = round(weight, 4)

        self.weights = weights
        self.method = 'sharpe'
        self.save_config()
        return weights

    def optimize_by_returns(self, strategies: List[Dict], top_n: int = 10) -> Dict[str, float]:
        """根据收益率优化权重
        只选取收益率最高的top_n策略，等权分配
        """
        # 按收益率排序
        sorted_strategies = sorted(strategies, key=lambda x: x.get('total_pnl_pct', 0), reverse=True)
        top_strategies = sorted_strategies[:top_n]

        if not top_strategies:
            return self.optimize_by_rating(strategies)

        equal_weight = 1.0 / len(top_strategies)
        weights = {s['name']: round(equal_weight, 4) for s in top_strategies}

        self.weights = weights
        self.method = 'returns'
        self.save_config()
        return weights

    def optimize_by_correlation(self, strategies: List[Dict], min_correlation: float = 0.5) -> Dict[str, float]:
        """根据相关性优化权重
        降低高相关性策略的权重，提高低相关性策略的权重
        """
        weights = {}

        # 简化的相关性计算：基于策略类型
        category_weights = {
            '趋势策略': 0.25,
            '价值策略': 0.20,
            '事件驱动': 0.20,
            '技术策略': 0.15,
            '资金流策略': 0.10,
            '轮动策略': 0.10,
            '逆向策略': 0.10,
            '价值策略': 0.15,
            '紫苏叶': 0.20,
            '其他': 0.10
        }

        for s in strategies:
            category = s.get('category', '其他')
            weight = category_weights.get(category, 0.10)
            weights[s['name']] = round(weight, 4)

        # 归一化
        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v / total, 4) for k, v in weights.items()}

        self.weights = weights
        self.method = 'correlation'
        self.save_config()
        return weights

    def get_weight(self, strategy_name: str) -> float:
        """获取策略权重"""
        return self.weights.get(strategy_name, 0.0)

    def get_portfolio_return(self, strategies: List[Dict]) -> float:
        """计算组合收益率"""
        if not self.weights:
            return 0.0

        total_return = 0.0
        for s in strategies:
            name = s.get('name', '')
            weight = self.weights.get(name, 0.0)
            ret = s.get('total_pnl_pct', 0.0) / 100
            total_return += weight * ret

        return total_return * 100

    def get_portfolio_sharpe(self, strategies: List[Dict]) -> float:
        """计算组合夏普比率"""
        if not self.weights:
            return 0.0

        # 简化计算：加权平均夏普
        total_sharpe = 0.0
        total_weight = 0.0
        for s in strategies:
            name = s.get('name', '')
            weight = self.weights.get(name, 0.0)
            sharpe = s.get('sharpe_ratio', 0.0)
            total_sharpe += weight * sharpe
            total_weight += weight

        if total_weight > 0:
            return total_sharpe / total_weight
        return 0.0


def run_portfolio_optimization(data_path: str = 'output/strategy_data.json',
                              output_path: str = 'data/portfolio_weights.json'):
    """运行组合优化"""
    # 加载数据
    if not os.path.exists(data_path):
        print(f"[错误] 数据文件不存在: {data_path}")
        return None

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    strategies = data.get('strategies', [])
    if not strategies:
        print("[错误] 没有策略数据")
        return None

    print(f"=" * 60)
    print("策略组合优化器")
    print(f"=" * 60)
    print(f"策略总数: {len(strategies)}")

    # 创建组合管理器
    portfolio = StrategyPortfolio()

    # 方法1: 按评级优化
    weights_rating = portfolio.optimize_by_rating(strategies)
    print(f"\n方法1: 按评级优化")
    print(f"  A级策略: {sum(1 for s in strategies if s.get('grade') == 'A')}个")
    print(f"  B级策略: {sum(1 for s in strategies if s.get('grade') == 'B')}个")
    print(f"  C级策略: {sum(1 for s in strategies if s.get('grade') == 'C')}个")
    print(f"  D级策略: {sum(1 for s in strategies if s.get('grade') == 'D')}个")

    # 方法2: 按夏普优化
    weights_sharpe = portfolio.optimize_by_sharpe(strategies, min_sharpe=1.0)
    sharpe_return = portfolio.get_portfolio_return(strategies)
    sharpe_ratio = portfolio.get_portfolio_sharpe(strategies)
    print(f"\n方法2: 按夏普优化")
    print(f"  组合收益率: {sharpe_return:.2f}%")
    print(f"  组合夏普: {sharpe_ratio:.2f}")

    # 方法3: 按收益率优化
    weights_returns = portfolio.optimize_by_returns(strategies, top_n=10)
    returns_return = portfolio.get_portfolio_return(strategies)
    print(f"\n方法3: 按收益率优化(Top 10)")
    print(f"  组合收益率: {returns_return:.2f}%")

    # 保存结果
    result = {
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'strategy_count': len(strategies),
        'methods': {
            'rating': {
                'weights': weights_rating,
                'portfolio_return': portfolio.get_portfolio_return(strategies),
                'portfolio_sharpe': portfolio.get_portfolio_sharpe(strategies)
            },
            'sharpe': {
                'weights': weights_sharpe,
                'portfolio_return': sharpe_return,
                'portfolio_sharpe': sharpe_ratio
            },
            'returns': {
                'weights': weights_returns,
                'portfolio_return': returns_return,
                'portfolio_sharpe': portfolio.get_portfolio_sharpe(strategies)
            }
        },
        'recommended': 'sharpe' if sharpe_ratio > 1 else 'rating'
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {output_path}")
    print(f"推荐方法: {result['recommended']}")

    return result


if __name__ == '__main__':
    run_portfolio_optimization()
