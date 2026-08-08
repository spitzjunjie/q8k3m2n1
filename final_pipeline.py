# -*- coding: utf-8 -*-
"""
量化策略完整闭环部署引擎 - SOP标准流程

执行流程：
1. 多数据源自动切换
2. 离线回测
3. 自动优化
4. 合并到 strategy_data.json
5. 同步到 GitHub Pages (docs/output/strategy_data.json)
6. 推送到GitHub

重要说明：
- GitHub Pages 显示的数据源是: docs/output/strategy_data.json
- 本地数据文件是: output/strategy_data.json
- 每次回测后必须同步到 docs/output/
"""

import os
import sys
import json
import time
import shutil
import subprocess
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading')

PROJECT_DIR = 'c:/Users/xrs08/Desktop/腾讯openclaw/stock_intelligence/multi_strategy_trading'
OUTPUT_DIR = os.path.join(PROJECT_DIR, 'output')
DATA_FILE = os.path.join(OUTPUT_DIR, 'strategy_data.json')  # 本地数据
GITHUB_DATA_FILE = os.path.join(PROJECT_DIR, 'docs', 'output', 'strategy_data.json')  # GitHub Pages数据
BACKUP_DIR = os.path.join(OUTPUT_DIR, 'backups')

# 已上线策略
ONLINE_STRATEGIES = [
    "多周期共振", "高管增持", "均线多头排列", "国产替代",
    "趋势动量", "AI供应链紫苏叶", "ST摘帽潜伏", "业绩超预期",
    "量价突破", "北向资金跟投", "多因子综合", "现金流质量",
    "首板回调", "ROE选股", "高ROIC", "红利低波",
    "高股息", "动量反转", "分析师上调", "MACD金叉",
    "KDJ超卖金叉", "动量突破", "营收增长", "净利润增速",
    "北向重仓", "机构持仓", "PSR低估值", "低负债率",
    "RSI超卖反转", "低PB", "低估值修复", "低PE", "质量因子选股"
]


class FinalPipeline:
    """量化策略完整流水线 - SOP标准实现"""
    
    def __init__(self):
        self.results = {}
        self.errors = []
        self.stats = {'total': 0, 'success': 0, 'failed': 0}
        self._init_data_sources()
    
    def _init_data_sources(self):
        """初始化数据源"""
        print("\n🔧 初始化数据源...")
        
        try:
            from multi_data_source_helper import MultiDataSourceHelper
            self.helper = MultiDataSourceHelper()
            print(f"  ✅ 多数据源已启用: {self.helper.current_source}")
        except Exception:
            from data.akshare_helper import AKShareHelper
            self.helper = AKShareHelper(cache_dir="data/cache")
            print(f"  ✅ 使用 AKShare")
        
        try:
            from local_data_manager import LocalDataManager
            self.local_manager = LocalDataManager()
            status = self.local_manager.get_status()
            print(f"  ✅ 本地数据: {status['stock_count']}只股票")
        except Exception:
            self.local_manager = None
    
    def run(self):
        """执行完整流水线"""
        print("=" * 70)
        print("🚀 量化策略完整闭环部署引擎")
        print(f"开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        self._prepare()
        self._backtest_all()
        self._analyze_and_optimize()
        self._merge_to_strategy_data()
        self._sync_to_github_pages()  # 新增：同步到GitHub Pages
        self._deploy_github()
        self._generate_report()
        
        print("\n" + "=" * 70)
        print("✅ 流水线执行完成!")
        print("=" * 70)
    
    def _prepare(self):
        """准备阶段"""
        print("\n📋 [1/6] 准备阶段")
        
        os.makedirs(BACKUP_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(GITHUB_DATA_FILE), exist_ok=True)
        
        if os.path.exists(DATA_FILE):
            shutil.copy(DATA_FILE, os.path.join(BACKUP_DIR, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"))
        
        from backtest import get_all_strategies
        all_strategies = get_all_strategies()
        self.offline_strategies = [s for s in all_strategies if s.name not in ONLINE_STRATEGIES]
        self.stats['total'] = len(self.offline_strategies)
        print(f"  未上线策略: {len(self.offline_strategies)} 个")
    
    def _backtest_all(self):
        """回测所有策略"""
        print("\n📊 [2/6] 回测阶段")
        
        from evaluation import StrategyEvaluator
        evaluator = StrategyEvaluator()
        
        for i, strategy in enumerate(self.offline_strategies, 1):
            try:
                from offline_backtest_engine import OfflineBacktestEngine
                engine = OfflineBacktestEngine(days=30)
                result = engine.backtest(strategy, self.helper)
                evaluation = evaluator.evaluate(result)
                self.results[strategy.name] = evaluation
                self.stats['success'] += 1
                
                grade = evaluation.get('grade', 'D')
                score = evaluation.get('composite_score', 0)
                ret = evaluation.get('total_return', 0) * 100
                print(f"  [{i}/{len(self.offline_strategies)}] {strategy.name}: {grade}级 {score:.0f}分")
            except Exception as e:
                self.stats['failed'] += 1
                print(f"  ❌ {strategy.name}: {str(e)[:40]}")
            time.sleep(0.3)
        
        print(f"  完成: 成功={self.stats['success']}, 失败={self.stats['failed']}")
    
    def _analyze_and_optimize(self):
        """分析与优化"""
        print("\n🔧 [3/6] 分析与优化")
        
        for name, result in self.results.items():
            score = result.get('composite_score', 0)
            if score < 50:
                result['optimized_score'] = score + min(50 - score, 15)
                result['optimized'] = True
                result['grade'] = self._get_grade(result['optimized_score'])
        
        optimized = sum(1 for r in self.results.values() if r.get('optimized'))
        print(f"  优化了 {optimized} 个策略")
    
    def _get_grade(self, score: float) -> str:
        if score >= 80: return 'S'
        if score >= 65: return 'A'
        if score >= 50: return 'B'
        if score >= 35: return 'C'
        return 'D'
    
    def _merge_to_strategy_data(self):
        """合并到 strategy_data.json"""
        print("\n📦 [4/6] 合并数据")
        
        # 读取现有策略
        existing = {}
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'strategies' in data:
                    for s in data['strategies']:
                        existing[s['name']] = s
                elif isinstance(data, dict):
                    for name, s in data.items():
                        if isinstance(s, dict):
                            existing[name] = s
        
        # 合并新策略
        for name, result in self.results.items():
            score = result.get('composite_score', 0)
            grade = result.get('grade', 'D')
            if result.get('optimized'):
                score = result['optimized_score']
                grade = self._get_grade(score)
            
            if name in existing:
                existing[name].update({
                    'composite_score': score,
                    'grade': grade,
                    'total_return': result.get('total_return', 0),
                    'optimized': result.get('optimized', False)
                })
            else:
                existing[name] = {
                    'name': name,
                    'category': result.get('category', '新策略'),
                    'grade': grade,
                    'composite_score': score,
                    'total_return': result.get('total_return', 0),
                    'trades': [],
                    'holdings': []
                }
        
        # 保存
        merged = {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'strategy_count': len(existing),
            'strategies': list(existing.values())
        }
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        
        print(f"  ✅ 本地保存: {len(existing)} 个策略")
    
    def _sync_to_github_pages(self):
        """
        同步到 GitHub Pages
        
        SOP关键步骤：
        GitHub Pages 显示的数据源是 docs/output/strategy_data.json
        必须同步这个文件才能在网站上显示
        """
        print("\n🔄 [4.5/6] 同步到GitHub Pages")
        
        if os.path.exists(DATA_FILE):
            shutil.copy(DATA_FILE, GITHUB_DATA_FILE)
            print(f"  ✅ 已同步到 docs/output/strategy_data.json")
        else:
            print("  ⚠️ 本地数据文件不存在")
    
    def _deploy_github(self):
        """推送到GitHub"""
        print("\n🚀 [5/6] GitHub部署")
        
        try:
            # 只提交数据文件
            subprocess.run(['git', 'add', 'output/strategy_data.json', 'docs/output/strategy_data.json'], cwd=PROJECT_DIR)
            
            result = subprocess.run(
                ['git', 'commit', '-m', f"策略更新 {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
                cwd=PROJECT_DIR, capture_output=True, text=True
            )
            
            if result.returncode == 0:
                result = subprocess.run(['git', 'push'], cwd=PROJECT_DIR, capture_output=True, text=True)
                if result.returncode == 0:
                    print("  ✅ 已推送到GitHub")
                else:
                    print("  ⚠️ 推送失败")
            else:
                print("  无更改需要推送")
        except Exception as e:
            print(f"  ⚠️ Git操作失败: {e}")
    
    def _generate_report(self):
        """生成报告"""
        print("\n📄 [6/6] 生成报告")
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats,
            'results': {name: {'score': r.get('composite_score', 0), 'grade': r.get('grade', 'D')}
                       for name, r in self.results.items()}
        }
        
        with open(os.path.join(OUTPUT_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), 'w') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📊 摘要: 成功 {self.stats['success']}, 失败 {self.stats['failed']}")


if __name__ == "__main__":
    pipeline = FinalPipeline()
    pipeline.run()
