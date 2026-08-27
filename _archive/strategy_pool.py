# -*- coding: utf-8 -*-
"""
策略池管理模块
管理策略生命周期：active → candidate → retired
基于评估结果自动淘汰降级，候选策略自动提升
"""

import json
import os
from datetime import datetime, timedelta


class StrategyPool:
    """策略池管理器

    池结构：
        active: 当前运行的策略列表 [{name, category, version, added_date, consecutive_d_days}]
        candidate: 候选策略列表 [{name, code, score, added_date}]
        retired: 已淘汰策略列表 [{name, retired_date, reason, final_score}]
        history: 评估历史 [{date, rankings}]
    """

    def __init__(self, pool_file='data/strategy_pool.json'):
        self.pool_file = pool_file
        os.makedirs(os.path.dirname(pool_file), exist_ok=True)
        self.pool = self._load()

    def _load(self):
        if os.path.exists(self.pool_file):
            try:
                with open(self.pool_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            'active': [],
            'candidate': [],
            'retired': [],
            'history': []
        }

    def save(self):
        with open(self.pool_file, 'w', encoding='utf-8') as f:
            json.dump(self.pool, f, ensure_ascii=False, indent=2, default=str)

    def init_active(self, strategy_names):
        """初始化active策略池（首次运行时调用）

        Args:
            strategy_names: 策略名列表
        """
        if self.pool['active']:
            return  # 已初始化
        today = datetime.now().strftime('%Y-%m-%d')
        for name in strategy_names:
            self.pool['active'].append({
                'name': name,
                'version': '1.0.0',
                'added_date': today,
                'consecutive_d_days': 0,
                'last_grade': 'B',
                'best_score': 0,
            })
        self.save()

    def update_ranking(self, evaluations):
        """根据评估结果更新策略状态

        规则：
        - D级 → consecutive_d_days + 1，连续30天D级则降级到retired
        - A级以上 → consecutive_d_days 重置为0
        - 候选池中连续3次A级 → 提升到active

        Args:
            evaluations: 评估结果列表（来自StrategyEvaluator.evaluate_batch）
        """
        today = datetime.now().strftime('%Y-%m-%d')

        # 记录历史
        self.pool['history'].append({
            'date': today,
            'rankings': [{'name': e['name'], 'score': e['composite_score'], 'grade': e['grade']}
                         for e in evaluations]
        })
        # 只保留最近30天历史
        if len(self.pool['history']) > 30:
            self.pool['history'] = self.pool['history'][-30:]

        # 更新active策略状态
        eval_map = {e['name']: e for e in evaluations}
        for active in self.pool['active']:
            name = active['name']
            e = eval_map.get(name)
            if not e:
                continue

            grade = e['grade']
            score = e['composite_score']
            active['last_grade'] = grade
            active['last_score'] = score
            if score > active.get('best_score', 0):
                active['best_score'] = score

            # 连续D级计数
            if grade == 'D':
                active['consecutive_d_days'] = active.get('consecutive_d_days', 0) + 1
                # 连续30天D级 → 降级
                if active['consecutive_d_days'] >= 30:
                    self._retire(name, f"连续{active['consecutive_d_days']}天D级")
            else:
                active['consecutive_d_days'] = 0

        # 检查候选提升
        for candidate in self.pool['candidate'][:]:
            name = candidate['name']
            e = eval_map.get(name)
            if not e:
                continue
            if e['grade'] in ['S', 'A']:
                candidate['consecutive_a_days'] = candidate.get('consecutive_a_days', 0) + 1
                # 连续3次A级 → 提升
                if candidate['consecutive_a_days'] >= 3:
                    self._promote(name)
            else:
                candidate['consecutive_a_days'] = 0

        self.save()

    def _retire(self, name, reason):
        """淘汰策略"""
        # 从active移除
        self.pool['active'] = [a for a in self.pool['active'] if a['name'] != name]
        # 加入retired
        self.pool['retired'].append({
            'name': name,
            'retired_date': datetime.now().strftime('%Y-%m-%d'),
            'reason': reason,
        })
        print(f"策略 {name} 已淘汰：{reason}")

    def _promote(self, name):
        """提升候选策略到active"""
        # 从candidate移除
        candidate = None
        new_candidates = []
        for c in self.pool['candidate']:
            if c['name'] == name:
                candidate = c
            else:
                new_candidates.append(c)
        self.pool['candidate'] = new_candidates

        if candidate:
            # 加入active
            self.pool['active'].append({
                'name': name,
                'version': candidate.get('version', '1.0.0'),
                'added_date': datetime.now().strftime('%Y-%m-%d'),
                'consecutive_d_days': 0,
                'last_grade': 'A',
                'best_score': candidate.get('score', 0),
            })
            print(f"候选策略 {name} 已提升为active")

    def add_candidate(self, name, strategy_code=None, score=0, version='1.0.0'):
        """添加候选策略（来自LLM发现或ML合成）

        Args:
            name: 策略名
            strategy_code: 策略代码（可选，用于动态加载）
            score: 初始评分
            version: 版本号
        """
        # 检查重名
        existing_names = {a['name'] for a in self.pool['active']}
        existing_names |= {c['name'] for c in self.pool['candidate']}
        existing_names |= {r['name'] for r in self.pool['retired']}
        if name in existing_names:
            print(f"策略 {name} 已存在，跳过添加")
            return False

        self.pool['candidate'].append({
            'name': name,
            'code': strategy_code,
            'score': score,
            'version': version,
            'added_date': datetime.now().strftime('%Y-%m-%d'),
            'consecutive_a_days': 0,
        })
        self.save()
        print(f"候选策略 {name} 已添加")
        return True

    def get_active_names(self):
        """获取当前active策略名列表"""
        return [a['name'] for a in self.pool['active']]

    def get_status(self):
        """获取策略池状态摘要"""
        return {
            'active_count': len(self.pool['active']),
            'candidate_count': len(self.pool['candidate']),
            'retired_count': len(self.pool['retired']),
            'active_names': self.get_active_names(),
            'warning_strategies': [a['name'] for a in self.pool['active']
                                   if a.get('consecutive_d_days', 0) >= 7],
        }

    def print_status(self):
        """打印策略池状态"""
        status = self.get_status()
        print("\n" + "=" * 60)
        print("策略池状态")
        print("=" * 60)
        print(f"Active策略：{status['active_count']}个")
        print(f"Candidate候选：{status['candidate_count']}个")
        print(f"Retired已淘汰：{status['retired_count']}个")
        if status['warning_strategies']:
            print(f"\n⚠️ 警告（连续7天D级）：")
            for name in status['warning_strategies']:
                print(f"  - {name}")
        print("=" * 60)


if __name__ == "__main__":
    # 测试策略池
    pool = StrategyPool()

    # 初始化（如果还没初始化）
    from backtest import get_all_strategies
    strategies = get_all_strategies()
    strategy_names = [s.name for s in strategies]
    pool.init_active(strategy_names)

    pool.print_status()
