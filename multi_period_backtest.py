# -*- coding: utf-8 -*-
"""
多周期回测模块
对Top 5策略进行日/周/月多周期回测，分析策略在不同周期下的表现稳定性
"""

import json
import os
from datetime import datetime, timedelta
import numpy as np


class MultiPeriodBacktest:
    """多周期回测引擎"""

    def __init__(self, strategy_data_path='output/strategy_data.json'):
        self.strategy_data_path = strategy_data_path
        self.strategies = []
        self.top_strategies = []
        self.periods = ['daily', 'weekly', 'monthly']
        self.results = {}

    def load_strategies(self):
        """加载策略数据，获取Top 5策略"""
        try:
            with open(self.strategy_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.strategies = data.get('strategies', [])
            
            # 按综合评分排序，取Top 5
            self.strategies.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
            self.top_strategies = self.strategies[:5]
            
            print(f"已加载 {len(self.strategies)} 个策略，选取Top 5进行多周期回测")
            for i, s in enumerate(self.top_strategies, 1):
                print(f"  {i}. {s.get('name', 'Unknown')} (分数: {s.get('composite_score', 0):.1f})")
            
            return True
        except Exception as e:
            print(f"加载策略数据失败: {e}")
            return False

    def resample_equity_curve(self, equity_curve, original_period='daily', target_period='weekly'):
        """重采样权益曲线到目标周期
        
        Args:
            equity_curve: 原始日线权益曲线
            original_period: 原始周期
            target_period: 目标周期 (weekly/monthly)
        """
        if not equity_curve or len(equity_curve) < 2:
            return equity_curve
        
        if target_period == 'weekly':
            # 按周聚合：每周取最后一个值
            step = 5
        elif target_period == 'monthly':
            # 按月聚合：每月取最后一个值
            step = 22
        else:
            return equity_curve
        
        # 聚合数据
        resampled = []
        for i in range(0, len(equity_curve), step):
            chunk = equity_curve[i:i+step]
            if chunk:
                resampled.append(chunk[-1])  # 取最后一个值
        
        return resampled

    def calculate_period_metrics(self, equity_curve):
        """计算指定周期的性能指标
        
        Returns:
            dict: 包含收益、夏普、最大回撤、胜率等指标
        """
        if not equity_curve or len(equity_curve) < 2:
            return {
                'total_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'volatility': 0,
                'periods': len(equity_curve)
            }
        
        curve = np.array(equity_curve)
        
        # 总收益
        total_return = (curve[-1] - curve[0]) / curve[0] if curve[0] != 0 else 0
        
        # 计算日收益率
        returns = np.diff(curve) / curve[:-1]
        returns = returns[~np.isnan(returns) & ~np.isinf(returns)]
        
        if len(returns) == 0:
            return {
                'total_return': total_return,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'volatility': 0,
                'periods': len(equity_curve)
            }
        
        # 年化收益（假设日线数据，年化252交易日）
        annualized_return = np.mean(returns) * 252
        
        # 波动率
        volatility = np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0
        
        # 夏普比率
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # 最大回撤
        peak = curve[0]
        max_dd = 0
        for value in curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # 胜率
        win_rate = np.sum(returns > 0) / len(returns) if len(returns) > 0 else 0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'volatility': volatility,
            'periods': len(equity_curve),
            'annualized_return': annualized_return
        }

    def run_multi_period_backtest(self):
        """对Top 5策略进行多周期回测"""
        if not self.top_strategies:
            print("没有可用的策略数据")
            return
        
        self.results = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'strategies': {}
        }
        
        for strategy in self.top_strategies:
            name = strategy.get('name', 'Unknown')
            equity_curve = strategy.get('equity_curve', [])
            
            strategy_result = {
                'name': name,
                'category': strategy.get('category', ''),
                'composite_score': strategy.get('composite_score', 0),
                'period_analysis': {}
            }
            
            for period in self.periods:
                # 重采样到目标周期
                resampled_curve = self.resample_equity_curve(
                    equity_curve, 
                    original_period='daily',
                    target_period=period
                )
                
                # 计算该周期的指标
                metrics = self.calculate_period_metrics(resampled_curve)
                strategy_result['period_analysis'][period] = {
                    'metrics': metrics,
                    'curve_length': len(resampled_curve)
                }
            
            # 计算周期稳定性
            strategy_result['period_stability'] = self._calculate_stability(
                strategy_result['period_analysis']
            )
            
            # 确定周期适应性
            strategy_result['period_adaptation'] = self._determine_period_adaptation(
                strategy_result['period_analysis']
            )
            
            self.results['strategies'][name] = strategy_result
        
        return self.results

    def _calculate_stability(self, period_analysis):
        """计算策略在不同周期间的稳定性
        
        稳定性指标：各周期收益的标准差，越小越稳定
        """
        returns = []
        for period, data in period_analysis.items():
            metrics = data['metrics']
            returns.append(metrics['total_return'])
        
        if len(returns) < 2:
            return 1.0
        
        # 计算变异系数（标准差/均值），越小越稳定
        std = np.std(returns)
        mean = np.mean(returns)
        
        if mean == 0:
            return 0
        
        cv = abs(std / mean)
        # 将CV转换为稳定性分数（CV越小分数越高）
        stability = max(0, 1 - cv)
        
        return round(stability, 3)

    def _determine_period_adaptation(self, period_analysis):
        """确定策略的最佳适应周期"""
        best_period = 'daily'
        best_return = -float('inf')
        
        for period, data in period_analysis.items():
            total_return = data['metrics']['total_return']
            if total_return > best_return:
                best_return = total_return
                best_period = period
        
        period_names = {
            'daily': '日线',
            'weekly': '周线',
            'monthly': '月线'
        }
        
        return period_names.get(best_period, '日线')

    def generate_report(self):
        """生成多周期对比报告"""
        if not self.results:
            print("没有回测结果可生成报告")
            return
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("多周期回测报告")
        report_lines.append(f"生成时间: {self.results.get('timestamp', '')}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        for name, result in self.results['strategies'].items():
            report_lines.append(f"\n策略: {name}")
            report_lines.append(f"类别: {result.get('category', '')}")
            report_lines.append(f"综合评分: {result.get('composite_score', 0):.1f}")
            report_lines.append(f"周期稳定性: {result.get('period_stability', 0):.3f}")
            report_lines.append(f"最佳适应周期: {result.get('period_adaptation', '未知')}")
            report_lines.append("")
            report_lines.append("-" * 60)
            report_lines.append(f"{'周期':<10} {'收益':>10} {'夏普':>8} {'最大回撤':>10} {'胜率':>8} {'波动率':>10}")
            report_lines.append("-" * 60)
            
            for period, data in result['period_analysis'].items():
                metrics = data['metrics']
                period_names = {'daily': '日线', 'weekly': '周线', 'monthly': '月线'}
                period_name = period_names.get(period, period)
                
                report_lines.append(
                    f"{period_name:<10} "
                    f"{metrics['total_return']*100:>9.2f}% "
                    f"{metrics['sharpe_ratio']:>8.2f} "
                    f"{metrics['max_drawdown']*100:>9.2f}% "
                    f"{metrics['win_rate']*100:>7.2f}% "
                    f"{metrics['volatility']*100:>9.2f}%"
                )
            
            report_lines.append("-" * 60)
        
        # 生成策略分散化建议
        report_lines.append("\n\n" + "=" * 80)
        report_lines.append("周期适应性总结")
        report_lines.append("=" * 80)
        
        adaptation_summary = {}
        for name, result in self.results['strategies'].items():
            adaptation = result.get('period_adaptation', '未知')
            if adaptation not in adaptation_summary:
                adaptation_summary[adaptation] = []
            adaptation_summary[adaptation].append(name)
        
        for period, strategies in adaptation_summary.items():
            report_lines.append(f"\n{period}适应型策略 ({len(strategies)}个):")
            for s in strategies:
                report_lines.append(f"  - {s}")
        
        report = "\n".join(report_lines)
        print(report)
        
        # 保存报告
        report_dir = 'reports'
        os.makedirs(report_dir, exist_ok=True)
        report_file = os.path.join(report_dir, 'multi_period_backtest_report.txt')
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n报告已保存到: {report_file}")
        
        return report

    def get_top_period_adaptations(self):
        """获取Top策略的周期适应性标记"""
        if not self.results:
            return {}
        
        adaptations = {}
        for name, result in self.results['strategies'].items():
            adaptations[name] = {
                'best_period': result.get('period_adaptation', '未知'),
                'stability': result.get('period_stability', 0),
                'returns': {
                    period: data['metrics']['total_return']
                    for period, data in result['period_analysis'].items()
                }
            }
        
        return adaptations


def main():
    """主函数"""
    print("=" * 60)
    print("多周期回测分析")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    backtest = MultiPeriodBacktest()
    
    if not backtest.load_strategies():
        print("加载策略数据失败，退出")
        return
    
    print("\n开始多周期回测...")
    backtest.run_multi_period_backtest()
    
    print("\n生成报告...")
    backtest.generate_report()
    
    print("\n周期适应性标记:")
    adaptations = backtest.get_top_period_adaptations()
    for name, data in adaptations.items():
        print(f"  {name}: {data['best_period']} (稳定性: {data['stability']:.3f})")


if __name__ == "__main__":
    main()
