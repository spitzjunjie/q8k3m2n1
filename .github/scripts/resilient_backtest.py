#!/usr/bin/env python3
"""
GitHub Actions 弹性回测脚本

特性：
1. 自动重试机制（快速失败可重试，超时不重试）
2. 数据源自动切换（Tushare → AKShare）
3. 网络超时处理（回测本身耗时约 40 分钟，超时必须给足）
4. 详细的错误日志

使用方法：
    python resilient_backtest.py --source tushare --strategies "策略1,策略2"
"""

import os
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime
from typing import Optional, Tuple

# 配置参数
MAX_RETRIES = 2
RETRY_DELAY = 30  # 秒
# backtest.py 全量回测 60+ 个策略，冷缓存实测约 40 分钟（2026-07-07 实测 43m47s）。
# 120 秒超时会把回测杀掉，导致每日数据从未真正更新（7/25 起的“成功”全是超时假成功）。
# CI 实测：GitHub 服务器访问 Tushare 在晚间可能 50 分钟跑不完（8/7 三次超时），
# 给到 70 分钟；job 级 timeout-minutes 同步提高到 180。
NETWORK_TIMEOUT = 4200  # 秒

class ResilientBacktest:
    """弹性回测执行器"""
    
    def __init__(self, source: str = 'tushare', strategies: str = '',
                 max_retries: int = MAX_RETRIES, timeout: int = NETWORK_TIMEOUT):
        self.source = source
        self.strategies = strategies
        self.max_retries = max_retries
        self.timeout = timeout
        self.attempts = 0
        self.errors = []
        self.last_was_timeout = False
        
    def log(self, message: str, level: str = 'info'):
        """统一日志输出"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prefix = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'success': '✅',
            'retry': '🔄'
        }.get(level, '•')
        print(f"[{timestamp}] {prefix} {message}")
        
        # 记录错误用于最终报告
        if level == 'error':
            self.errors.append(f"[{timestamp}] {message}")
    
    def run_command(self, cmd: list, timeout: Optional[int] = None) -> Tuple[bool, str]:
        """
        执行命令，带超时和重试
        返回: (成功标志, 输出信息)
        """
        timeout = timeout or self.timeout
        self.log(f"执行命令: {' '.join(cmd)}", 'info')
        self.last_was_timeout = False
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            )
            
            if result.returncode == 0:
                self.log("命令执行成功", 'success')
                return True, result.stdout
            else:
                error_msg = result.stderr or result.stdout
                self.log(f"命令执行失败: {error_msg[:500]}", 'error')
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            self.last_was_timeout = True
            self.log(f"命令超时（{timeout}秒）", 'error')
            return False, f"Timeout after {timeout} seconds"
        except Exception as e:
            self.log(f"命令执行异常: {str(e)}", 'error')
            return False, str(e)
    
    def check_data_source_health(self, source: str) -> bool:
        """检查数据源健康状态"""
        self.log(f"检查数据源 {source} 健康状态...", 'info')
        
        if source == 'tushare':
            # 检查 Tushare Token
            token = os.environ.get('TUSHARE_TOKEN')
            if not token:
                self.log("TUSHARE_TOKEN 未设置", 'error')
                return False
            self.log(f"TUSHARE_TOKEN 已配置: {token[:10]}...", 'success')
            return True
            
        elif source == 'akshare':
            # AKShare 不需要密钥，简单检查
            self.log("AKShare 无需密钥", 'success')
            return True
        
        return False
    
    def execute_backtest(self, source: str) -> bool:
        """执行单次回测"""
        self.attempts += 1
        
        self.log(f"第 {self.attempts}/{MAX_RETRIES} 次尝试 ({source})", 'retry')
        
        # 构建命令
        cmd = ['python', 'backtest.py']
        if self.strategies:
            cmd.extend(['--strategies', self.strategies])
        
        env = os.environ.copy()
        env['DATA_SOURCE'] = source
        
        if source == 'tushare':
            token = os.environ.get('TUSHARE_TOKEN')
            if token:
                env['TUSHARE_TOKEN'] = token
        
        # 执行回测
        success, output = self.run_command(cmd)
        
        # 检查输出文件
        if success:
            output_file = 'output/strategy_data.json'
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                if file_size > 1000:  # 文件大于1KB认为有效
                    self.log(f"输出文件有效: {output_file} ({file_size} bytes)", 'success')
                    return True
                else:
                    self.log(f"输出文件过小: {file_size} bytes", 'error')
                    return False
            else:
                self.log(f"输出文件不存在: {output_file}", 'error')
                return False
        
        return False
    
    def should_switch_source(self) -> bool:
        """判断是否应该切换数据源"""
        if self.source == 'tushare':
            self.log("Tushare 连续失败，准备切换到 AKShare", 'warning')
            return True
        return False
    
    def run(self) -> bool:
        """
        主执行流程
        1. 先尝试当前数据源（最多3次）
        2. 如果失败，切换到备用数据源
        3. 记录详细日志
        """
        self.log("="*50, 'info')
        self.log("弹性回测开始", 'info')
        self.log(f"初始数据源: {self.source}", 'info')
        self.log(f"策略: {self.strategies or '全部'}", 'info')
        self.log("="*50, 'info')
        
        # 阶段1: 尝试主数据源
        for attempt in range(1, self.max_retries + 1):
            self.attempts = attempt
            
            # 健康检查
            if not self.check_data_source_health(self.source):
                self.log("健康检查失败，等待后重试...", 'warning')
                time.sleep(RETRY_DELAY)
                continue
            
            # 执行回测
            if self.execute_backtest(self.source):
                self.log(f"✅ 回测成功！共尝试 {attempt} 次", 'success')
                return True

            # 超时不重试：回测是固定耗时任务，重试只会再超时一次，白白烧掉 job 预算
            if self.last_was_timeout:
                self.log("本次失败是超时，不再重试（回测为固定耗时任务）", 'warning')
                break
            
            # 失败后等待
            if attempt < self.max_retries:
                self.log(f"等待 {RETRY_DELAY} 秒后重试...", 'warning')
                time.sleep(RETRY_DELAY)
        
        # 阶段2: 切换到备用数据源
        if self.should_switch_source():
            backup_source = 'akshare'
            self.log(f"切换到备用数据源: {backup_source}", 'warning')
            
            # 重置计数
            self.attempts = 0
            
            for attempt in range(1, self.max_retries + 1):
                self.attempts = attempt
                
                # 健康检查
                if not self.check_data_source_health(backup_source):
                    time.sleep(RETRY_DELAY)
                    continue
                
                # 执行回测
                if self.execute_backtest(backup_source):
                    self.log(f"✅ AKShare 回测成功！共尝试 {attempt} 次", 'success')
                    return True

                if self.last_was_timeout:
                    self.log("本次失败是超时，不再重试（回测为固定耗时任务）", 'warning')
                    break
                
                if attempt < self.max_retries:
                    self.log(f"等待 {RETRY_DELAY} 秒后重试...", 'warning')
                    time.sleep(RETRY_DELAY)
        
        # 所有尝试都失败
        self.log("="*50, 'error')
        self.log("❌ 所有数据源和重试都失败了", 'error')
        self.log("错误记录:", 'error')
        for err in self.errors[-5:]:  # 只显示最后5条
            print(f"  {err}")
        self.log("="*50, 'error')
        return False
    
    def generate_report(self) -> dict:
        """生成回测报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'success': os.path.exists('output/strategy_data.json'),
            'attempts': self.attempts,
            'errors': self.errors[-10:],  # 最近10条错误
            'strategy_count': 0
        }


def main():
    parser = argparse.ArgumentParser(
        description='弹性回测脚本 - 自动重试和数据源切换'
    )
    parser.add_argument(
        '--source',
        choices=['tushare', 'akshare'],
        default='tushare',
        help='数据源（默认: tushare）'
    )
    parser.add_argument(
        '--strategies',
        type=str,
        default='',
        help='策略名称（逗号分隔，留空则全部）'
    )
    parser.add_argument(
        '--max-retries',
        type=int,
        default=MAX_RETRIES,
        help=f'最大重试次数（默认: {MAX_RETRIES}）'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=NETWORK_TIMEOUT,
        help=f'单次回测命令超时秒数（默认: {NETWORK_TIMEOUT}）'
    )
    
    args = parser.parse_args()
    
    # 创建执行器
    runner = ResilientBacktest(
        source=args.source,
        strategies=args.strategies,
        max_retries=args.max_retries,
        timeout=args.timeout
    )
    
    # 执行
    success = runner.run()
    
    # 生成报告
    report = runner.generate_report()
    report_path = 'output/backtest_report.json'
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n报告已保存: {report_path}")
    
    # 返回状态码
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
