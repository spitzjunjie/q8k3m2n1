# -*- coding: utf-8 -*-
"""
压力测试模块
模拟极端行情，测试Top 3策略在极端行情下的表现，评估最大回撤风险
"""

import json
import os
from datetime import datetime, timedelta
import numpy as np
import random


class StressTest:
    """压力测试引擎"""

    def __init__(self, strategy_data_path='output/strategy_data.json'):
        self.strategy_data_path = strategy_data_path
        self.strategies = []
        self.top_strategies = []
        self.results = {}

    def load_strategies(self):
        """加载策略数据，获取Top 3策略"""
        try:
            with open(self.strategy_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.strategies = data.get('strategies', [])
            
            # 按综合评分排序，取Top 3
            self.strategies.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
            self.top_strategies = self.strategies[:3]
            
            print(f"已加载 {len(self.strategies)} 个策略，选取Top 3进行压力测试")
            for i, s in enumerate(self.top_strategies, 1):
                print(f"  {i}. {s.get('name', 'Unknown')} (分数: {s.get('composite_score', 0):.1f})")
            
            return True
        except Exception as e:
            print(f"加载策略数据失败: {e}")
            return False

    def simulate_bear_market(self, initial_value, days=60, decline_rate=0.30):
        """模拟熊市行情（沪深300单边下跌30%）
        
        Args:
            initial_value: 初始资金
            days: 模拟天数
            decline_rate: 下跌幅度
        
        Returns:
            dict: 模拟结果
        """
        # 假设单边下跌，每天等比例下跌
        daily_decline = (1 - decline_rate) ** (1 / days) - 1
        
        values = [initial_value]
        for _ in range(days):
            new_value = values[-1] * (1 + daily_decline)
            values.append(new_value)
        
        # 计算模拟的交易收益（假设策略有一定防御能力）
        # 熊市中，假设策略能跑赢指数一半
        defensive_rate = 0.5  # 防御能力：损失减半
        strategy_decline = decline_rate * defensive_rate
        
        return {
            'type': '熊市',
            'description': f'沪深300单边下跌{decline_rate*100:.0f}%，策略防御{100-defensive_rate*100:.0f}%损失',
            'days': days,
            'benchmark_decline': decline_rate,
            'strategy_decline': strategy_decline,
            'final_value': initial_value * (1 - strategy_decline),
            'max_drawdown': strategy_decline,
            'equity_curve': values,
            'daily_returns': [daily_decline] * days
        }

    def simulate_choppy_market(self, initial_value, days=60, volatility=0.05):
        """模拟震荡市（来回波动）
        
        Args:
            initial_value: 初始资金
            days: 模拟天数
            volatility: 日波动率（默认5%）
        
        Returns:
            dict: 模拟结果
        """
        values = [initial_value]
        daily_returns = []
        
        # 随机游走
        current_value = initial_value
        for _ in range(days):
            # 随机波动，正负交替
            daily_return = np.random.normal(0, volatility)
            # 限制波动范围
            daily_return = max(-volatility * 2, min(volatility * 2, daily_return))
            daily_returns.append(daily_return)
            
            current_value = current_value * (1 + daily_return)
            values.append(current_value)
        
        # 计算最大回撤
        peak = initial_value
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
        
        # 震荡市策略收益（假设策略能在震荡中获利）
        net_return = (values[-1] - initial_value) / initial_value
        
        return {
            'type': '震荡市',
            'description': f'日波动率约{volatility*100:.0f}%，随机游走',
            'days': days,
            'volatility': volatility,
            'strategy_return': net_return,
            'final_value': values[-1],
            'max_drawdown': max_dd,
            'equity_curve': values,
            'daily_returns': daily_returns
        }

    def simulate_high_volatility(self, initial_value, days=60, extreme_vol=0.10):
        """模拟高波动行情（日涨跌5%以上）
        
        Args:
            initial_value: 初始资金
            days: 模拟天数
            extreme_vol: 极端波动率（默认10%）
        
        Returns:
            dict: 模拟结果
        """
        values = [initial_value]
        daily_returns = []
        
        current_value = initial_value
        for _ in range(days):
            # 大幅随机波动
            daily_return = np.random.normal(0, extreme_vol)
            # 限制波动范围
            daily_return = max(-extreme_vol * 2, min(extreme_vol * 2, daily_return))
            daily_returns.append(daily_return)
            
            current_value = current_value * (1 + daily_return)
            values.append(current_value)
        
        # 计算最大回撤
        peak = initial_value
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
        
        # 高波动环境下的收益
        net_return = (values[-1] - initial_value) / initial_value
        
        return {
            'type': '高波动市',
            'description': f'日波动率约{extreme_vol*100:.0f}%，极端行情',
            'days': days,
            'volatility': extreme_vol,
            'strategy_return': net_return,
            'final_value': values[-1],
            'max_drawdown': max_dd,
            'equity_curve': values,
            'daily_returns': daily_returns
        }

    def run_stress_test(self):
        """对Top 3策略运行压力测试"""
        if not self.top_strategies:
            print("没有可用的策略数据")
            return
        
        self.results = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'test_scenarios': {},
            'strategy_results': {}
        }
        
        # 定义测试场景
        scenarios = [
            ('bear_market', self.simulate_bear_market),
            ('choppy_market', self.simulate_choppy_market),
            ('high_volatility', self.simulate_high_volatility)
        ]
        
        # 运行每个场景
        for scenario_name, scenario_func in scenarios:
            scenario_result = scenario_func(initial_value=30000, days=60)
            self.results['test_scenarios'][scenario_name] = scenario_result
        
        # 对每个策略进行测试
        for strategy in self.top_strategies:
            name = strategy.get('name', 'Unknown')
            initial_capital = strategy.get('initial_capital', 30000)
            
            strategy_result = {
                'name': name,
                'category': strategy.get('category', ''),
                'composite_score': strategy.get('composite_score', 0),
                'original_metrics': {
                    'total_return': strategy.get('total_return', 0),
                    'max_drawdown': strategy.get('max_drawdown', 0),
                    'sharpe_ratio': strategy.get('sharpe_ratio', 0)
                },
                'stress_test_results': {}
            }
            
            # 在每个场景下测试
            for scenario_name, scenario_func in scenarios:
                # 获取场景参数
                if scenario_name == 'bear_market':
                    scenario_result = scenario_func(initial_capital, days=60, decline_rate=0.30)
                elif scenario_name == 'choppy_market':
                    scenario_result = scenario_func(initial_capital, days=60, volatility=0.05)
                else:
                    scenario_result = scenario_func(initial_capital, days=60, extreme_vol=0.10)
                
                # 模拟策略在极端行情下的表现
                stress_result = self._simulate_strategy_performance(
                    strategy, scenario_result
                )
                strategy_result['stress_test_results'][scenario_name] = stress_result
            
            # 计算综合压力测试评分
            strategy_result['stress_score'] = self._calculate_stress_score(
                strategy_result['stress_test_results']
            )
            
            self.results['strategy_results'][name] = strategy_result
        
        return self.results

    def _simulate_strategy_performance(self, strategy, scenario):
        """模拟策略在特定场景下的表现
        
        基于策略的历史表现和场景特征，估算压力测试结果
        """
        original_return = strategy.get('total_return', 0)
        original_dd = strategy.get('max_drawdown', 0)
        original_sharpe = strategy.get('sharpe_ratio', 0)
        
        scenario_type = scenario['type']
        
        # 根据场景类型调整表现
        if scenario_type == '熊市':
            # 熊市中，收益会大幅下降，但有止损保护
            stress_return = original_return * 0.3  # 只保留30%收益
            stress_dd = min(original_dd * 1.5, 0.5)  # 回撤可能放大
            stress_sharpe = original_sharpe * 0.4 if original_sharpe > 0 else 0
            
        elif scenario_type == '震荡市':
            # 震荡市中，收益降低但仍可获利
            stress_return = original_return * 0.6
            stress_dd = original_dd * 1.2
            stress_sharpe = original_sharpe * 0.7 if original_sharpe > 0 else 0
            
        else:  # 高波动市
            # 高波动中，收益可能为负
            stress_return = original_return * 0.2 - 0.1  # 大幅降低
            stress_dd = min(original_dd * 2, 0.6)  # 回撤可能翻倍
            stress_sharpe = max(original_sharpe * 0.3, -1)  # 夏普比率大幅下降
        
        return {
            'scenario_type': scenario_type,
            'description': scenario['description'],
            'expected_return': round(stress_return, 4),
            'expected_max_drawdown': round(stress_dd, 4),
            'expected_sharpe_ratio': round(stress_sharpe, 2),
            'final_value': scenario['final_value'],
            'max_drawdown': scenario['max_drawdown']
        }

    def _calculate_stress_score(self, stress_results):
        """计算压力测试综合评分
        
        综合考虑各场景下的表现，0-100分
        """
        scores = []
        
        for scenario, result in stress_results.items():
            # 场景评分
            scenario_score = 0
            
            # 收益评分（40%权重）
            ret = result['expected_return']
            if ret > 0:
                ret_score = min(ret / 0.3, 1) * 40
            else:
                ret_score = max(ret / -0.3, -1) * 20  # 亏损扣分
            
            # 回撤评分（40%权重）
            dd = result['expected_max_drawdown']
            dd_score = (1 - min(dd / 0.5, 1)) * 40
            
            # 夏普评分（20%权重）
            sharpe = result['expected_sharpe_ratio']
            sharpe_score = max(min(sharpe / 2, 1), 0) * 20
            
            scenario_score = ret_score + dd_score + sharpe_score
            scores.append(scenario_score)
        
        # 平均分
        avg_score = sum(scores) / len(scores) if scores else 0
        
        return round(avg_score, 1)

    def generate_report(self):
        """生成压力测试报告"""
        if not self.results:
            print("没有压力测试结果可生成报告")
            return
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("压力测试报告")
        report_lines.append(f"生成时间: {self.results.get('timestamp', '')}")
        report_lines.append("=" * 80)
        
        # 测试场景描述
        report_lines.append("\n【测试场景】")
        for scenario_name, scenario in self.results['test_scenarios'].items():
            report_lines.append(f"\n{scenario['type']}:")
            report_lines.append(f"  {scenario['description']}")
        
        # 策略测试结果
        report_lines.append("\n\n【策略压力测试结果】")
        
        for name, result in self.results['strategy_results'].items():
            report_lines.append(f"\n{'='*60}")
            report_lines.append(f"策略: {name}")
            report_lines.append(f"类别: {result.get('category', '')}")
            report_lines.append(f"综合评分: {result.get('composite_score', 0):.1f}")
            report_lines.append(f"压力测试评分: {result.get('stress_score', 0):.1f}")
            report_lines.append(f"\n原始指标:")
            report_lines.append(f"  收益: {result['original_metrics']['total_return']*100:+.2f}%")
            report_lines.append(f"  最大回撤: {result['original_metrics']['max_drawdown']*100:.2f}%")
            report_lines.append(f"  夏普比率: {result['original_metrics']['sharpe_ratio']:.2f}")
            
            report_lines.append(f"\n极端行情表现:")
            report_lines.append("-" * 50)
            
            for scenario, stress in result['stress_test_results'].items():
                report_lines.append(f"\n  {stress['scenario_type']}:")
                report_lines.append(f"    预期收益: {stress['expected_return']*100:+.2f}%")
                report_lines.append(f"    预期最大回撤: {stress['expected_max_drawdown']*100:.2f}%")
                report_lines.append(f"    预期夏普比率: {stress['expected_sharpe_ratio']:.2f}")
        
        # 风险评估
        report_lines.append("\n\n" + "=" * 80)
        report_lines.append("【风险评估总结】")
        report_lines.append("=" * 80)
        
        # 按压力测试评分排序
        sorted_strategies = sorted(
            self.results['strategy_results'].items(),
            key=lambda x: x[1].get('stress_score', 0),
            reverse=True
        )
        
        report_lines.append("\n压力测试排名（抗风险能力）:")
        for i, (name, result) in enumerate(sorted_strategies, 1):
            score = result.get('stress_score', 0)
            worst_scenario = min(
                result['stress_test_results'].items(),
                key=lambda x: x[1]['expected_return']
            )
            report_lines.append(f"\n  {i}. {name} (评分: {score:.1f})")
            report_lines.append(f"     最差场景: {worst_scenario[0]} ({worst_scenario[1]['expected_return']*100:+.2f}%)")
        
        # 生成建议
        report_lines.append("\n\n【投资建议】")
        best_strategy = sorted_strategies[0]
        report_lines.append(f"\n1. 最佳抗风险策略: {best_strategy[0]}")
        report_lines.append(f"   压力测试评分: {best_strategy[1].get('stress_score', 0):.1f}")
        
        # 风险警示
        report_lines.append("\n2. 风险警示:")
        for name, result in self.results['strategy_results'].items():
            worst = min(
                result['stress_test_results'].items(),
                key=lambda x: x[1]['expected_return']
            )
            if worst[1]['expected_return'] < -0.2:
                report_lines.append(f"   ⚠️ {name} 在{worst[0]}下预期亏损超过20%")
        
        report = "\n".join(report_lines)
        print(report)
        
        # 保存报告
        report_dir = 'reports'
        os.makedirs(report_dir, exist_ok=True)
        report_file = os.path.join(report_dir, 'stress_test_report.txt')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n报告已保存到: {report_file}")
        
        return report

    def get_risk_metrics(self):
        """获取风险评估指标"""
        if not self.results:
            return {}
        
        risk_metrics = {}
        
        for name, result in self.results['strategy_results'].items():
            stress_results = result['stress_test_results']
            
            # 找出最大回撤和最差收益
            max_dd = max(r['expected_max_drawdown'] for r in stress_results.values())
            worst_return = min(r['expected_return'] for r in stress_results.values())
            
            # 风险评级
            if max_dd > 0.4 or worst_return < -0.3:
                risk_level = "高风险"
            elif max_dd > 0.25 or worst_return < -0.15:
                risk_level = "中等风险"
            else:
                risk_level = "较低风险"
            
            risk_metrics[name] = {
                'max_drawdown_estimate': max_dd,
                'worst_return_estimate': worst_return,
                'risk_level': risk_level,
                'stress_score': result.get('stress_score', 0)
            }
        
        return risk_metrics


def main():
    """主函数"""
    print("=" * 60)
    print("策略压力测试")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    stress_tester = StressTest()
    
    if not stress_tester.load_strategies():
        print("加载策略数据失败，退出")
        return
    
    print("\n开始压力测试...")
    stress_tester.run_stress_test()
    
    print("\n生成报告...")
    stress_tester.generate_report()
    
    print("\n风险评估指标:")
    risk_metrics = stress_tester.get_risk_metrics()
    for name, metrics in risk_metrics.items():
        print(f"  {name}:")
        print(f"    预估最大回撤: {metrics['max_drawdown_estimate']*100:.1f}%")
        print(f"    最差收益: {metrics['worst_return_estimate']*100:.1f}%")
        print(f"    风险等级: {metrics['risk_level']}")


if __name__ == "__main__":
    main()
