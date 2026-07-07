# -*- coding: utf-8 -*-
"""
策略相关性分析模块
计算策略间的收益相关性，生成相关性热力图，识别高度相关策略组
"""

import json
import os
from datetime import datetime
import numpy as np


class StrategyCorrelation:
    """策略相关性分析器"""

    def __init__(self, strategy_data_path='output/strategy_data.json'):
        self.strategy_data_path = strategy_data_path
        self.strategies = []
        self.correlation_matrix = None
        self.strategy_names = []
        self.results = {}

    def load_strategies(self):
        """加载策略数据"""
        try:
            with open(self.strategy_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.strategies = data.get('strategies', [])
            
            # 筛选有权益曲线的策略
            valid_strategies = [
                s for s in self.strategies 
                if s.get('equity_curve') and len(s.get('equity_curve', [])) > 5
            ]
            
            print(f"已加载 {len(self.strategies)} 个策略，{len(valid_strategies)} 个有有效权益曲线")
            return valid_strategies
        except Exception as e:
            print(f"加载策略数据失败: {e}")
            return []

    def calculate_returns(self, equity_curve):
        """从权益曲线计算收益率序列"""
        if not equity_curve or len(equity_curve) < 2:
            return []
        
        curve = np.array(equity_curve)
        returns = np.diff(curve) / curve[:-1]
        # 过滤无效值
        returns = returns[~np.isnan(returns) & ~np.isinf(returns)]
        return returns.tolist()

    def calculate_correlation_matrix(self, strategies):
        """计算策略间的相关性矩阵"""
        if not strategies:
            return None
        
        # 获取所有策略的收益率序列
        returns_data = []
        self.strategy_names = []
        
        for strategy in strategies:
            name = strategy.get('name', f'Strategy_{len(self.strategy_names)}')
            returns = self.calculate_returns(strategy.get('equity_curve', []))
            if len(returns) > 0:
                returns_data.append(returns)
                self.strategy_names.append(name)
        
        if len(returns_data) < 2:
            print("有效策略数量不足，无法计算相关性")
            return None
        
        # 找到最短的收益率序列长度
        min_length = min(len(r) for r in returns_data)
        
        # 截断到相同长度
        aligned_returns = np.array([r[:min_length] for r in returns_data])
        
        # 计算相关性矩阵
        self.correlation_matrix = np.corrcoef(aligned_returns)
        
        return self.correlation_matrix

    def find_high_correlation_pairs(self, threshold=0.7):
        """找出高度相关的策略对（相关性 > threshold）
        
        Args:
            threshold: 相关性阈值，默认0.7
        
        Returns:
            list: 高度相关策略对列表
        """
        if self.correlation_matrix is None:
            return []
        
        high_corr_pairs = []
        n = len(self.correlation_matrix)
        
        for i in range(n):
            for j in range(i+1, n):
                corr = self.correlation_matrix[i][j]
                if corr > threshold:
                    high_corr_pairs.append({
                        'strategy1': self.strategy_names[i],
                        'strategy2': self.strategy_names[j],
                        'correlation': round(corr, 4)
                    })
        
        # 按相关性降序排序
        high_corr_pairs.sort(key=lambda x: x['correlation'], reverse=True)
        
        return high_corr_pairs

    def find_correlation_groups(self, threshold=0.7):
        """识别高度相关的策略组（使用并查集思想）
        
        Args:
            threshold: 相关性阈值，默认0.7
        
        Returns:
            list: 策略组列表，每个组是策略名列表
        """
        if self.correlation_matrix is None:
            return []
        
        n = len(self.correlation_matrix)
        parent = list(range(n))
        
        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # 根据相关性合并
        for i in range(n):
            for j in range(i+1, n):
                if self.correlation_matrix[i][j] > threshold:
                    union(i, j)
        
        # 收集每个组
        groups = {}
        for i in range(n):
            root = find(i)
            if root not in groups:
                groups[root] = []
            groups[root].append(self.strategy_names[i])
        
        # 转换为列表，排除单策略组
        correlation_groups = [g for g in groups.values() if len(g) > 1]
        
        return correlation_groups

    def generate_heatmap_html(self, output_path='reports/strategy_correlation_heatmap.html'):
        """生成相关性热力图HTML
        
        Args:
            output_path: 输出HTML文件路径
        """
        if self.correlation_matrix is None:
            print("没有相关性矩阵，无法生成热力图")
            return
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        n = len(self.correlation_matrix)
        
        # 生成颜色矩阵（基于相关性值）
        colors = []
        for i in range(n):
            row_colors = []
            for j in range(n):
                corr = self.correlation_matrix[i][j]
                if i == j:
                    # 对角线（自相关=1）
                    color = 'rgb(50, 50, 150)'
                elif corr > 0.7:
                    color = 'rgb(255, 50, 50)'  # 高正相关-红色
                elif corr > 0.4:
                    color = 'rgb(255, 150, 50)'  # 中等正相关-橙色
                elif corr > 0:
                    color = 'rgb(255, 255, 150)'  # 低正相关-浅黄
                elif corr > -0.4:
                    color = 'rgb(200, 200, 255)'  # 低负相关-浅蓝
                elif corr > -0.7:
                    color = 'rgb(100, 150, 255)'  # 中等负相关-蓝色
                else:
                    color = 'rgb(50, 50, 255)'  # 高负相关-深蓝
                row_colors.append(color)
            colors.append(row_colors)
        
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>策略相关性热力图</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            text-align: center;
        }}
        .info {{
            text-align: center;
            color: #666;
            margin-bottom: 20px;
        }}
        .heatmap-container {{
            display: flex;
            justify-content: center;
            overflow-x: auto;
        }}
        table {{
            border-collapse: collapse;
            margin: 0 auto;
        }}
        th, td {{
            width: 60px;
            height: 40px;
            text-align: center;
            font-size: 10px;
            border: 1px solid #ddd;
        }}
        th {{
            background-color: #f0f0f0;
            font-weight: bold;
            position: sticky;
            top: 0;
        }}
        .row-header {{
            position: sticky;
            left: 0;
            background-color: #f0f0f0;
            z-index: 1;
        }}
        .col-header {{
            position: sticky;
            top: 0;
            background-color: #f0f0f0;
            z-index: 2;
        }}
        .corner {{
            position: sticky;
            top: 0;
            left: 0;
            background-color: #e0e0e0;
            z-index: 3;
        }}
        .legend {{
            display: flex;
            justify-content: center;
            margin-top: 20px;
            gap: 20px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border: 1px solid #ccc;
        }}
        .high-corr {{
            background-color: #ffcccc;
            padding: 15px;
            margin: 20px auto;
            max-width: 600px;
            border-radius: 5px;
        }}
        .high-corr h3 {{
            margin-top: 0;
            color: #c00;
        }}
        .high-corr ul {{
            list-style-type: none;
            padding: 0;
        }}
        .high-corr li {{
            padding: 5px 0;
        }}
        .suggestion {{
            background-color: #e8f4e8;
            padding: 15px;
            margin: 20px auto;
            max-width: 600px;
            border-radius: 5px;
        }}
        .suggestion h3 {{
            margin-top: 0;
            color: #2a7;
        }}
    </style>
</head>
<body>
    <h1>策略相关性热力图</h1>
    <div class="info">
        生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
        策略数量: {n}
    </div>
    
    <div class="heatmap-container">
        <table>
            <tr>
                <td class="corner"></td>
'''
        
        # 添加列标题
        for name in self.strategy_names:
            short_name = name[:8] + '..' if len(name) > 10 else name
            html_content += f'                <th class="col-header">{short_name}</th>\n'
        
        html_content += '            </tr>\n'
        
        # 添加数据和行标题
        for i in range(n):
            short_name = self.strategy_names[i][:8] + '..' if len(self.strategy_names[i]) > 10 else self.strategy_names[i]
            html_content += f'            <tr>\n                <th class="row-header">{short_name}</th>\n'
            
            for j in range(n):
                corr = self.correlation_matrix[i][j]
                color = colors[i][j]
                html_content += f'                <td style="background-color: {color}">{corr:.2f}</td>\n'
            
            html_content += '            </tr>\n'
        
        html_content += '''        </table>
    </div>
    
    <div class="legend">
        <div class="legend-item">
            <div class="legend-color" style="background-color: rgb(50, 50, 150);"></div>
            <span>自身相关</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: rgb(255, 50, 50);"></div>
            <span>高正相关(>0.7)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: rgb(255, 150, 50);"></div>
            <span>中正相关(0.4-0.7)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: rgb(255, 255, 150);"></div>
            <span>低正相关(0-0.4)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: rgb(100, 150, 255);"></div>
            <span>负相关(<-0.4)</span>
        </div>
    </div>
'''
        
        # 添加高度相关策略对
        high_corr_pairs = self.find_high_correlation_pairs(0.7)
        if high_corr_pairs:
            html_content += '''
    <div class="high-corr">
        <h3>⚠️ 高度相关策略对 (相关性 > 0.7)</h3>
        <ul>
'''
            for pair in high_corr_pairs:
                html_content += f'''            <li>{pair['strategy1']} ↔ {pair['strategy2']}: {pair['correlation']:.2f}</li>
'''
            html_content += '''        </ul>
    </div>
'''
        
        # 添加分散化建议
        correlation_groups = self.find_correlation_groups(0.7)
        if correlation_groups:
            html_content += '''
    <div class="suggestion">
        <h3>💡 分散化建议</h3>
        <p>以下策略组存在高度相关性，建议从中选择代表性策略：</p>
        <ul>
'''
            for i, group in enumerate(correlation_groups, 1):
                html_content += f'            <li><strong>组{i}:</strong> {", ".join(group)}</li>\n'
            html_content += '''        </ul>
        </div>
'''
        
        html_content += '''
</body>
</html>
'''
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"热力图已保存到: {output_path}")
        return output_path

    def get_diversification_suggestions(self):
        """生成策略分散化建议
        
        Returns:
            dict: 包含分散化建议
        """
        if self.correlation_matrix is None:
            return {}
        
        suggestions = {
            'high_correlation_pairs': self.find_high_correlation_pairs(0.7),
            'correlation_groups': self.find_correlation_groups(0.7),
            'selected_strategies': [],
            'reasoning': ''
        }
        
        # 如果有相关性组，选择每组的代表性策略
        groups = self.find_correlation_groups(0.7)
        
        if groups:
            # 收集所有在组中的策略
            grouped_strategies = set()
            for group in groups:
                grouped_strategies.update(group)
            
            # 从每组选择代表性策略（选择夏普比率最高的）
            selected = []
            for group in groups:
                # 获取每个策略的夏普比率
                best_strategy = None
                best_sharpe = -float('inf')
                
                for strategy in self.strategies:
                    if strategy.get('name') in group:
                        sharpe = strategy.get('sharpe_ratio', 0)
                        if sharpe > best_sharpe:
                            best_sharpe = sharpe
                            best_strategy = strategy.get('name')
                
                if best_strategy:
                    selected.append(best_strategy)
            
            suggestions['selected_strategies'] = selected
            suggestions['reasoning'] = (
                f"从{len(groups)}个高度相关策略组中，各选择1个代表性策略，"
                f"共{len(selected)}个策略可在保持收益的同时降低组合相关性。"
            )
        else:
            suggestions['reasoning'] = "所有策略间相关性较低，无需特别分散化处理。"
            suggestions['selected_strategies'] = [s['name'] for s in self.strategies[:5]]
        
        return suggestions

    def run_analysis(self):
        """执行完整的相关性分析"""
        print("=" * 60)
        print("策略相关性分析")
        print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        strategies = self.load_strategies()
        if not strategies:
            return None
        
        print("\n计算相关性矩阵...")
        self.calculate_correlation_matrix(strategies)
        
        if self.correlation_matrix is not None:
            print(f"\n相关性矩阵维度: {self.correlation_matrix.shape}")
            
            # 找出高度相关的策略对
            high_corr_pairs = self.find_high_correlation_pairs(0.7)
            print(f"\n高度相关策略对 (相关性 > 0.7): {len(high_corr_pairs)}对")
            for pair in high_corr_pairs[:5]:
                print(f"  {pair['strategy1']} ↔ {pair['strategy2']}: {pair['correlation']:.2f}")
            
            # 识别策略组
            groups = self.find_correlation_groups(0.7)
            print(f"\n相关性策略组: {len(groups)}组")
            for i, group in enumerate(groups, 1):
                print(f"  组{i}: {', '.join(group)}")
            
            # 生成热力图
            print("\n生成相关性热力图...")
            self.generate_heatmap_html()
            
            # 生成分散化建议
            print("\n分散化建议:")
            suggestions = self.get_diversification_suggestions()
            print(f"  {suggestions['reasoning']}")
            if suggestions['selected_strategies']:
                print(f"  推荐组合: {', '.join(suggestions['selected_strategies'])}")
            
            self.results = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'strategy_count': len(strategies),
                'high_correlation_pairs': high_corr_pairs,
                'correlation_groups': groups,
                'diversification_suggestions': suggestions
            }
        
        return self.results


def main():
    """主函数"""
    analyzer = StrategyCorrelation()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()
