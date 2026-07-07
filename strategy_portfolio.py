# -*- coding: utf-8 -*-
"""
策略组合优化模块
基于回测历史数据进行策略组合优化

功能：
1. 读取30天回测结果（output/backtest_history.json）
2. 计算各策略间的相关性矩阵
3. 实现三种组合方式：等权组合、风险平价、均值-方差优化
4. 回测组合表现
5. 输出最优组合权重到 data/portfolio_weights.json
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.optimize import minimize


class StrategyPortfolio:
    """策略组合优化器"""

    def __init__(self, backtest_history_path=None):
        """
        Args:
            backtest_history_path: 回测历史JSON文件路径
        """
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.backtest_path = backtest_history_path or os.path.join(self.base_dir, 'output', 'backtest_history.json')
        self.data_dir = os.path.join(self.base_dir, 'data')
        os.makedirs(self.data_dir, exist_ok=True)

        self.strategies = []
        self.returns_df = None
        self.correlation_matrix = None
        self.portfolio_weights = {}

    def load_backtest_history(self):
        """读取回测历史数据"""
        if not os.path.exists(self.backtest_path):
            raise FileNotFoundError(f"回测历史文件不存在: {self.backtest_path}")

        with open(self.backtest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.strategies = data.get('strategies', [])
        print(f"加载了 {len(self.strategies)} 个策略的回测数据")

        # 构建收益率DataFrame
        self._build_returns_df()
        return self.strategies

    def _build_returns_df(self):
        """从权益曲线构建收益率DataFrame"""
        records = []
        for strategy in self.strategies:
            name = strategy['name']
            equity_curve = strategy.get('equity_curve', [])
            for point in equity_curve:
                records.append({
                    'date': point['date'],
                    'strategy': name,
                    'value': point['value']
                })

        if not records:
            return

        df = pd.DataFrame(records)
        df['date'] = pd.to_datetime(df['date'])
        df = df.pivot(index='date', columns='strategy', values='value')

        # 计算日收益率
        self.returns_df = df.pct_change().dropna()
        print(f"收益率数据范围: {self.returns_df.index[0]} ~ {self.returns_df.index[-1]}")

    def calculate_correlation_matrix(self):
        """计算策略间相关性矩阵"""
        if self.returns_df is None:
            self._build_returns_df()

        self.correlation_matrix = self.returns_df.corr()
        return self.correlation_matrix

    def get_top_strategies(self, min_return=0, min_win_rate=0.4, top_n=10):
        """筛选优质策略
        
        Args:
            min_return: 最小收益率要求
            min_win_rate: 最小胜率要求
            top_n: 返回前N个策略
        
        Returns:
            list: 优质策略列表
        """
        if not self.strategies:
            self.load_backtest_history()

        # 按综合评分排序
        scored = []
        for s in self.strategies:
            score = s.get('total_return', 0) * 100  # 转换为百分比
            score += s.get('sharpe_ratio', 0) * 0.1  # 夏普比率权重较低
            score += s.get('win_rate', 0) * 10  # 胜率权重
            score -= s.get('max_drawdown', 0) * 5  # 最大回撤惩罚
            
            scored.append((score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        
        # 过滤并返回top_n
        top = [s for _, s in scored[:top_n] 
               if s.get('total_return', 0) >= min_return 
               and s.get('win_rate', 0) >= min_win_rate]
        
        print(f"筛选出 {len(top)} 个优质策略 (top {top_n})")
        return top

    def equal_weight_portfolio(self, strategies=None):
        """等权组合 - 所有策略平均分配资金
        
        Args:
            strategies: 策略列表，None则使用全部
        
        Returns:
            dict: 组合权重
        """
        if strategies is None:
            strategies = self.get_top_strategies()

        n = len(strategies)
        if n == 0:
            return {}

        weight = 1.0 / n
        weights = {s['name']: weight for s in strategies}
        
        print(f"等权组合: {n} 个策略，每策略权重 {weight:.4f}")
        return weights

    def risk_parity_portfolio(self, strategies=None):
        """风险平价组合 - 按波动率倒数分配资金
        
        波动率低的策略分配更多资金，波动率高的策略分配较少资金
        
        Args:
            strategies: 策略列表，None则使用全部
        
        Returns:
            dict: 组合权重
        """
        if strategies is None:
            strategies = self.get_top_strategies()

        if self.returns_df is None:
            self._build_returns_df()

        volatilities = {}
        for s in strategies:
            name = s['name']
            if name in self.returns_df.columns:
                vol = self.returns_df[name].std()
                volatilities[name] = vol if vol > 0 else 0.001
            else:
                volatilities[name] = 0.001

        # 按波动率倒数计算权重
        inv_vols = {name: 1.0 / vol for name, vol in volatilities.items()}
        total = sum(inv_vols.values())
        weights = {name: inv_vol / total for name, inv_vol in inv_vols.items()}
        
        print(f"风险平价组合: 基于波动率倒数分配")
        for name, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            print(f"  {name}: {w:.4f} (vol={volatilities[name]:.6f})")
        
        return weights

    def mean_variance_portfolio(self, strategies=None, risk_aversion=1.0):
        """均值-方差优化组合 - 最大化夏普比率
        
        求解优化问题: max w'μ - (γ/2) * w'Σw
        其中 μ 是期望收益率向量，Σ 是协方差矩阵
        
        Args:
            strategies: 策略列表，None则使用全部
            risk_aversion: 风险厌恶系数，越大越保守
        
        Returns:
            dict: 组合权重
        """
        if strategies is None:
            strategies = self.get_top_strategies()

        if self.returns_df is None:
            self._build_returns_df()

        # 获取策略名称列表
        strategy_names = [s['name'] for s in strategies if s['name'] in self.returns_df.columns]
        
        if len(strategy_names) < 2:
            print("策略数量不足，无法进行均值-方差优化")
            return self.equal_weight_portfolio(strategies)

        # 计算均值收益率和协方差矩阵
        mean_returns = self.returns_df[strategy_names].mean() * 252  # 年化
        cov_matrix = self.returns_df[strategy_names].cov() * 252  # 年化

        n = len(strategy_names)
        
        # 优化目标: 最大化夏普比率 (或最大化收益-风险)
        def neg_sharpe(weights):
            portfolio_return = np.dot(weights, mean_returns.values)
            portfolio_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix.values, weights)))
            if portfolio_vol == 0:
                return 0
            return -(portfolio_return / portfolio_vol)  # 负的夏普比率

        # 约束: 权重和为1
        constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        
        # 边界: 每个权重在 0.05 ~ 0.5 之间
        bounds = tuple((0.05, 0.5) for _ in range(n))
        
        # 初始权重
        x0 = np.array([1.0 / n] * n)

        result = minimize(neg_sharpe, x0, method='SLSQP',
                         bounds=bounds, constraints=constraints)
        
        if result.success:
            weights = dict(zip(strategy_names, result.x))
            print(f"均值-方差优化成功 (风险厌恶系数={risk_aversion})")
            
            # 计算组合统计
            port_return = np.dot(result.x, mean_returns.values)
            port_vol = np.sqrt(np.dot(result.x, np.dot(cov_matrix.values, result.x)))
            sharpe = port_return / port_vol if port_vol > 0 else 0
            
            print(f"  预期年化收益: {port_return:.2%}")
            print(f"  预期年化波动: {port_vol:.2%}")
            print(f"  预期夏普比率: {sharpe:.2f}")
        else:
            print("优化失败，使用等权组合")
            weights = self.equal_weight_portfolio(strategies)

        return weights

    def backtest_portfolio(self, weights, initial_capital=100000):
        """回测组合表现
        
        Args:
            weights: 组合权重 dict{strategy_name: weight}
            initial_capital: 初始资金
        
        Returns:
            dict: 组合回测结果
        """
        if not weights:
            return None

        # 按日期汇总所有策略的权益曲线
        portfolio_equity = {}
        
        for strategy in self.strategies:
            name = strategy['name']
            if name not in weights:
                continue
            
            weight = weights[name]
            equity_curve = strategy.get('equity_curve', [])
            
            for point in equity_curve:
                date = point['date']
                value = point['value']
                
                if date not in portfolio_equity:
                    portfolio_equity[date] = {
                        'value': 0,
                        'contributions': {}
                    }
                
                # 该策略对组合的贡献
                contribution = value * weight / strategy.get('initial_capital', 30000) * initial_capital
                portfolio_equity[date]['value'] += contribution
                portfolio_equity[date]['contributions'][name] = contribution

        if not portfolio_equity:
            return None

        # 构建组合权益曲线
        dates = sorted(portfolio_equity.keys())
        equity_curve = [{'date': d, 'value': portfolio_equity[d]['value']} for d in dates]
        
        # 计算收益率序列
        values = [portfolio_equity[d]['value'] for d in dates]
        returns = [0] + [values[i] / values[i-1] - 1 for i in range(1, len(values))]
        
        # 计算统计指标
        total_return = (values[-1] - initial_capital) / initial_capital if values else 0
        total_days = len(dates) - 1 if len(dates) > 1 else 1
        annualized_return = (1 + total_return) ** (252 / total_days) - 1 if total_days > 0 else 0
        
        # 计算波动率
        returns_arr = np.array(returns[1:]) if len(returns) > 1 else np.array([0])
        volatility = returns_arr.std() * np.sqrt(252) if len(returns_arr) > 0 else 0
        
        # 计算夏普比率
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        
        # 计算最大回撤
        cumulative = np.cumprod(1 + returns_arr)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdowns.min()) if len(drawdowns) > 0 else 0

        result = {
            'portfolio_type': 'optimized',
            'weights': weights,
            'initial_capital': initial_capital,
            'final_value': values[-1] if values else initial_capital,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'annualized_return': annualized_return,
            'annualized_return_pct': annualized_return * 100,
            'volatility': volatility,
            'volatility_pct': volatility * 100,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'backtest_start': dates[0] if dates else None,
            'backtest_end': dates[-1] if dates else None,
            'backtest_days': total_days,
            'equity_curve': equity_curve
        }

        return result

    def compare_portfolios(self, strategies=None):
        """比较三种组合方式的表现
        
        Args:
            strategies: 策略列表
        
        Returns:
            dict: 各组合对比结果
        """
        if strategies is None:
            strategies = self.get_top_strategies()

        results = {}

        # 1. 等权组合
        print("\n" + "=" * 60)
        print("1. 等权组合")
        print("=" * 60)
        ew_weights = self.equal_weight_portfolio(strategies)
        ew_result = self.backtest_portfolio(ew_weights)
        results['equal_weight'] = ew_result

        # 2. 风险平价组合
        print("\n" + "=" * 60)
        print("2. 风险平价组合")
        print("=" * 60)
        rp_weights = self.risk_parity_portfolio(strategies)
        rp_result = self.backtest_portfolio(rp_weights)
        results['risk_parity'] = rp_result

        # 3. 均值-方差优化组合
        print("\n" + "=" * 60)
        print("3. 均值-方差优化组合")
        print("=" * 60)
        mv_weights = self.mean_variance_portfolio(strategies)
        mv_result = self.backtest_portfolio(mv_weights)
        results['mean_variance'] = mv_result

        return results

    def select_best_portfolio(self, comparison_results):
        """选择最优组合
        
        基于夏普比率和最大回撤选择最优组合
        
        Args:
            comparison_results: compare_portfolios() 返回的结果
        
        Returns:
            tuple: (最优组合名称, 最优组合权重, 最优组合结果)
        """
        best_name = None
        best_score = -float('inf')
        best_weights = None
        best_result = None

        for name, result in comparison_results.items():
            if result is None:
                continue

            # 综合评分: 夏普比率权重更高，但也要考虑回撤
            sharpe = result.get('sharpe_ratio', 0)
            mdd = result.get('max_drawdown', 1)
            
            # 调整后的夏普: 惩罚大回撤
            score = sharpe * (1 - mdd * 2)
            
            print(f"{name}: 夏普={sharpe:.2f}, 回撤={mdd:.2%}, 综合分={score:.2f}")

            if score > best_score:
                best_score = score
                best_name = name
                best_weights = result.get('weights', {})
                best_result = result

        print(f"\n最优组合: {best_name}")
        return best_name, best_weights, best_result

    def save_weights(self, weights, output_path=None):
        """保存组合权重到JSON
        
        Args:
            weights: 组合权重 dict
            output_path: 输出文件路径
        """
        if output_path is None:
            output_path = os.path.join(self.data_dir, 'portfolio_weights.json')

        data = {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'weights': weights,
            'total_weight': sum(weights.values())
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"组合权重已保存到: {output_path}")
        return output_path

    def run_full_optimization(self, top_n=8, min_return=0, min_win_rate=0.4):
        """运行完整优化流程
        
        Args:
            top_n: 筛选前N个策略
            min_return: 最小收益率要求
            min_win_rate: 最小胜率要求
        
        Returns:
            dict: 优化结果
        """
        print("=" * 60)
        print("策略组合优化")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1. 加载数据
        print("\n[1/5] 加载回测历史...")
        self.load_backtest_history()

        # 2. 计算相关性矩阵
        print("\n[2/5] 计算相关性矩阵...")
        corr_matrix = self.calculate_correlation_matrix()
        print(f"相关性矩阵维度: {corr_matrix.shape}")

        # 3. 筛选优质策略
        print("\n[3/5] 筛选优质策略...")
        top_strategies = self.get_top_strategies(min_return, min_win_rate, top_n)
        for s in top_strategies:
            print(f"  {s['name']}: 收益={s.get('total_return_pct', 0):.2f}%, "
                  f"胜率={s.get('win_rate', 0):.2%}, 夏普={s.get('sharpe_ratio', 0):.2f}")

        # 4. 比较三种组合方式
        print("\n[4/5] 比较组合方式...")
        comparison = self.compare_portfolios(top_strategies)

        # 5. 选择最优组合
        print("\n[5/5] 选择最优组合...")
        best_name, best_weights, best_result = self.select_best_portfolio(comparison)

        # 保存最优权重
        if best_weights:
            output_path = self.save_weights(best_weights)

        # 返回完整结果
        return {
            'top_strategies': top_strategies,
            'correlation_matrix': corr_matrix.to_dict(),
            'comparison': comparison,
            'best_portfolio': {
                'name': best_name,
                'weights': best_weights,
                'result': best_result
            }
        }


def main():
    """主函数"""
    optimizer = StrategyPortfolio()
    
    # 运行完整优化
    result = optimizer.run_full_optimization(
        top_n=8,       # 选取前8个优质策略
        min_return=0,  # 收益率>0
        min_win_rate=0.4  # 胜率>40%
    )
    
    # 打印最终结果
    print("\n" + "=" * 60)
    print("优化结果摘要")
    print("=" * 60)
    
    best = result['best_portfolio']
    print(f"\n最优组合: {best['name']}")
    print(f"\n权重分配:")
    for name, weight in best['weights'].items():
        print(f"  {name}: {weight:.2%}")
    
    res = best['result']
    if res:
        print(f"\n组合表现:")
        print(f"  总收益率: {res['total_return_pct']:.2f}%")
        print(f"  年化收益率: {res['annualized_return_pct']:.2f}%")
        print(f"  年化波动率: {res['volatility_pct']:.2f}%")
        print(f"  夏普比率: {res['sharpe_ratio']:.2f}")
        print(f"  最大回撤: {res['max_drawdown_pct']:.2f}%")


if __name__ == "__main__":
    main()
