# -*- coding: utf-8 -*-
"""
策略文件完整性验证
在push前或CI运行前检查所有策略模块是否能正常导入
用法: python verify_strategies.py
"""

import importlib
import sys
import os


# 所有策略模块
STRATEGY_MODULES = [
    'strategies.factor_strategies',
    'strategies.event_strategies',
    'strategies.special_strategies',
    'strategies.technical_strategies',
    'strategies.advanced_strategies',
    'strategies.new_strategies',
    'strategies.new_s_strategies',
    'data.tushare_helper',
    'data.akshare_helper',
    'timing.timing',
    'trading.simulator',
    'evaluation',
]


def verify():
    """验证所有模块是否能正常导入"""
    print("=" * 50)
    print("策略文件完整性验证")
    print("=" * 50)

    errors = []
    for module_name in STRATEGY_MODULES:
        try:
            importlib.import_module(module_name)
            print(f"  OK  {module_name}")
        except ImportError as e:
            print(f"  FAIL {module_name}: {e}")
            errors.append((module_name, str(e)))
        except Exception as e:
            print(f"  ERROR {module_name}: {e}")
            errors.append((module_name, str(e)))

    # 额外检查：git未跟踪的策略文件
    print("\n--- 检查未跟踪的策略文件 ---")
    import subprocess
    result = subprocess.run(
        ['git', 'status', '--short', '--', 'strategies/'],
        capture_output=True, text=True, cwd=os.path.dirname(__file__)
    )
    untracked = [l for l in result.stdout.strip().split('\n') if l.startswith('??') and l.endswith('.py')]
    if untracked:
        print("  WARNING 以下策略文件未被git跟踪：")
        for f in untracked:
            print(f"    {f}")
        print("  请运行: git add strategies/*.py")
        errors.append(('untracked_files', '\n'.join(untracked)))
    else:
        print("  OK  所有策略文件已被git跟踪")

    print("\n" + "=" * 50)
    if errors:
        print(f"FAIL  {len(errors)} 个问题需要修复：")
        for name, msg in errors:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    else:
        print("PASS  所有验证通过，可以安全push")
        sys.exit(0)


if __name__ == '__main__':
    verify()
