#!/usr/bin/env python3
"""
自动修复脚本

功能：
1. 分析回测失败原因
2. 生成修复指令
3. 调用 Codex CLI 执行修复
4. 验证修复结果

使用方式：
    python auto-fix.py --error-log "错误日志文件"
    python auto-fix.py --last-error "错误信息"
"""

import os
import sys
import json
import argparse
import subprocess
import re
from datetime import datetime
from typing import Optional, List, Dict

# 常见错误模式与修复策略
ERROR_PATTERNS = {
    # 数据源错误
    r'tushare.*failed|akshare.*failed': {
        'type': 'data_source',
        'strategy': '数据源连接失败，尝试：1) 检查API密钥 2) 切换备用数据源 3) 增加重试次数'
    },
    r'connection.*timeout|request.*timeout': {
        'type': 'network',
        'strategy': '网络超时，尝试：1) 增加超时时间 2) 检查网络 3) 使用代理'
    },
    r'rate.*limit|too.*many.*request': {
        'type': 'api_limit',
        'strategy': 'API频率限制，尝试：1) 减少并发 2) 增加延迟 3) 等待后重试'
    },
    
    # 代码错误
    r'SyntaxError|IndentationError': {
        'type': 'syntax',
        'strategy': '语法错误，需要修复Python代码语法'
    },
    r'ImportError|ModuleNotFoundError': {
        'type': 'import',
        'strategy': '模块导入错误，尝试：1) 安装缺失模块 2) 检查import路径 3) 修复模块名'
    },
    r'AttributeError': {
        'type': 'attribute',
        'strategy': '属性访问错误，检查：1) 对象类型 2) 属性名称 3) API变更'
    },
    r'TypeError': {
        'type': 'type',
        'strategy': '类型错误，检查：1) 参数类型 2) 返回值类型 3) 类型转换'
    },
    r'KeyError': {
        'type': 'key',
        'strategy': '字典键错误，检查：1) 键名拼写 2) 数据结构 3) 默认值处理'
    },
    r'IndexError': {
        'type': 'index',
        'strategy': '索引错误，检查：1) 列表长度 2) 索引范围 3) 空列表处理'
    },
    r'ValueError': {
        'type': 'value',
        'strategy': '值错误，检查：1) 参数范围 2) 数据格式 3) 边界条件'
    },
    
    # 策略错误
    r'select_stocks.*return.*empty|empty.*list': {
        'type': 'strategy_empty',
        'strategy': '策略返回空列表，需要：1) 检查选股逻辑 2) 验证数据源 3) 调整筛选条件'
    },
    r'No.*module.*named.*strategy|strategy.*not.*found': {
        'type': 'strategy_not_found',
        'strategy': '策略模块未找到，检查：1) 文件路径 2) 类名 3) import语句'
    },
    
    # 数据错误
    r'no.*data|empty.*data|data.*none': {
        'type': 'no_data',
        'strategy': '数据为空，检查：1) 日期范围 2) 数据源状态 3) 缓存过期'
    },
    r'invalid.*date|date.*error': {
        'type': 'date_error',
        'strategy': '日期格式错误，检查：1) 日期格式 2) 时区处理 3) 字符串解析'
    }
}


class AutoFixer:
    """自动修复器"""
    
    def __init__(self):
        self.errors = []
        self.fixes = []
        self.codex_available = self._check_codex()
    
    def _check_codex(self) -> bool:
        """检查 Codex CLI 是否可用"""
        try:
            result = subprocess.run(
                ['codex', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def log(self, message: str, level: str = 'info'):
        """日志输出"""
        prefix = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'success': '✅',
            'fix': '🔧'
        }.get(level, '•')
        print(f"{prefix} {message}")
    
    def analyze_error(self, error_log: str) -> List[Dict]:
        """分析错误日志，识别错误模式"""
        detected = []
        
        for pattern, solution in ERROR_PATTERNS.items():
            matches = re.findall(pattern, error_log, re.IGNORECASE)
            if matches:
                detected.append({
                    'pattern': pattern,
                    'type': solution['type'],
                    'strategy': solution['strategy'],
                    'matches': matches
                })
                self.log(f"发现错误模式: {solution['type']}", 'warning')
        
        return detected
    
    def generate_fix_instruction(self, errors: List[Dict]) -> str:
        """生成 Codex 修复指令"""
        if not errors:
            return "分析错误日志，未识别到已知错误模式。请人工检查。"
        
        instruction = """# 代码修复任务

## 错误分析

"""
        for i, err in enumerate(errors, 1):
            instruction += f"### 错误 {i}: {err['type']}\n"
            instruction += f"- 匹配模式: `{err['pattern']}`\n"
            instruction += f"- 修复策略: {err['strategy']}\n"
            instruction += f"- 匹配内容: {'; '.join(err['matches'][:3])}\n\n"
        
        instruction += """## 修复要求

1. 分析错误根本原因
2. 修复相关代码
3. 确保修复后不回退其他功能
4. 验证修复有效

## 重要约束

- 不要修改与错误无关的代码
- 保持现有代码风格一致
- 添加必要的异常处理
- 更新相关注释
"""
        return instruction
    
    def call_codex(self, instruction: str) -> bool:
        """调用 Codex CLI 执行修复"""
        if not self.codex_available:
            self.log("Codex CLI 不可用，跳过自动修复", 'warning')
            return False
        
        self.log("调用 Codex CLI 进行代码修复...", 'fix')
        
        try:
            # 构建 Codex 命令
            cmd = [
                'codex', 'exec',
                '--profile', 'm21',
                '--dangerously-bypass-approvals-and-sandbox',
                '--skip-git-repo-check',
                instruction
            ]
            
            # 执行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10分钟超时
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            )
            
            if result.returncode == 0:
                self.log("Codex 修复完成", 'success')
                self.fixes.append({
                    'instruction': instruction[:200],
                    'status': 'success',
                    'output': result.stdout[:1000]
                })
                return True
            else:
                self.log(f"Codex 执行失败: {result.stderr[:500]}", 'error')
                self.fixes.append({
                    'instruction': instruction[:200],
                    'status': 'failed',
                    'error': result.stderr[:500]
                })
                return False
                
        except subprocess.TimeoutExpired:
            self.log("Codex 执行超时（10分钟）", 'error')
            return False
        except Exception as e:
            self.log(f"Codex 调用异常: {str(e)}", 'error')
            return False
    
    def verify_fix(self) -> bool:
        """验证修复结果"""
        self.log("验证修复结果...", 'info')
        
        # 运行 verify_strategies.py
        try:
            result = subprocess.run(
                ['python', 'verify_strategies.py'],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            )
            
            if result.returncode == 0:
                self.log("策略验证通过", 'success')
                return True
            else:
                self.log(f"策略验证失败: {result.stdout}", 'error')
                return False
        except Exception as e:
            self.log(f"验证过程异常: {str(e)}", 'error')
            return False
    
    def run(self, error_log: str = None, last_error: str = None) -> bool:
        """主执行流程"""
        self.log("="*50, 'info')
        self.log("自动修复开始", 'info')
        self.log("="*50, 'info')
        
        # 获取错误信息
        if error_log and os.path.exists(error_log):
            with open(error_log, 'r', encoding='utf-8') as f:
                error_content = f.read()
        elif last_error:
            error_content = last_error
        else:
            # 尝试读取最近的错误日志
            log_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'output'
            )
            log_file = os.path.join(log_dir, 'error.log')
            
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    error_content = f.read()
            else:
                self.log("未找到错误日志", 'error')
                return False
        
        self.log(f"错误日志长度: {len(error_content)} 字符", 'info')
        
        # 分析错误
        errors = self.analyze_error(error_content)
        
        if not errors:
            self.log("未识别到可自动修复的错误", 'warning')
            return False
        
        # 生成修复指令
        instruction = self.generate_fix_instruction(errors)
        
        # 调用 Codex 修复
        success = self.call_codex(instruction)
        
        if success:
            # 验证修复
            if self.verify_fix():
                self.log("✅ 修复成功并验证通过", 'success')
                return True
            else:
                self.log("⚠️ 修复完成但验证未通过", 'warning')
                return False
        else:
            self.log("❌ 修复失败，请人工处理", 'error')
            return False
    
    def generate_report(self) -> dict:
        """生成修复报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'codex_available': self.codex_available,
            'errors_detected': len(self.errors),
            'fixes_applied': len(self.fixes),
            'fixes': self.fixes
        }


def main():
    parser = argparse.ArgumentParser(
        description='自动修复脚本 - 分析错误并调用 Codex 修复'
    )
    parser.add_argument(
        '--error-log',
        type=str,
        help='错误日志文件路径'
    )
    parser.add_argument(
        '--last-error',
        type=str,
        help='最近的错误信息'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅分析不执行修复'
    )
    
    args = parser.parse_args()
    
    if not args.error_log and not args.last_error:
        parser.print_help()
        sys.exit(1)
    
    # 创建修复器
    fixer = AutoFixer()
    
    if args.dry_run:
        # 仅分析模式
        print("=== 干运行模式 - 仅分析错误 ===")
        error_content = args.last_error or open(args.error_log).read()
        errors = fixer.analyze_error(error_content)
        print(f"\n发现 {len(errors)} 个错误模式:")
        for err in errors:
            print(f"  - {err['type']}: {err['strategy']}")
        sys.exit(0)
    
    # 执行修复
    success = fixer.run(
        error_log=args.error_log,
        last_error=args.last_error
    )
    
    # 生成报告
    report = fixer.generate_report()
    report_path = os.path.join('output', 'fix_report.json')
    
    os.makedirs('output', exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n报告已保存: {report_path}")
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
