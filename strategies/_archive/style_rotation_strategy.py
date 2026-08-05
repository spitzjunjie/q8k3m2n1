# -*- coding: utf-8 -*-
"""
大小盘风格轮动策略

策略核心逻辑：
1. 计算沪深300和创业板近N日涨幅
2. 比较强弱，持有涨幅大的指数ETF
3. 设置最低门槛（如差距>5%）避免频繁轮动

参数配置：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| 观察期 | 20天 | 比较近期涨幅 |
| 持有期 | 5天 | 轮动周期 |
| 切换阈值 | 5% | 差距阈值 |
| 大盘ETF | 510300(沪深300) | 交易标的 |
| 小盘ETF | 159915(创业板) | 交易标的 |

参考：邢不行课程 - 大小盘风格轮动
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.base import BaseStrategy
import akshare as ak


class StyleRotationStrategy(BaseStrategy):
    """大小盘风格轮动策略"""
    
    def __init__(self,
                 lookback_days=20,        # 观察期（天）
                 holding_days=5,          # 持有期（天）
                 switch_threshold=5,      # 切换阈值（%）
                 large_cap_etf='510300',  # 大盘ETF代码
                 small_cap_etf='159915'): # 小盘ETF代码
        super().__init__("大小盘风格轮动", "风格轮动")
        self.lookback_days = lookback_days
        self.holding_days = holding_days
        self.switch_threshold = switch_threshold
        self.large_cap_etf = large_cap_etf
        self.small_cap_etf = small_cap_etf
        
        # ETF名称映射
        self.etf_names = {
            '510300': '沪深300ETF',
            '159915': '创业板ETF',
        }
        
        # 缓存
        self._large_cap_cache = None
        self._small_cap_cache = None
        self._last_rotation_date = None  # 上次轮动日期
        self._current_holding = None     # 当前持有标的
        
    def get_params(self):
        """获取策略参数"""
        return {
            'lookback_days': self.lookback_days,
            'holding_days': self.holding_days,
            'switch_threshold': self.switch_threshold,
            'large_cap_etf': self.large_cap_etf,
            'small_cap_etf': self.small_cap_etf,
        }
    
    def get_description(self):
        """获取策略描述"""
        return (f"大小盘风格轮动：观察期{self.lookback_days}天，"
                f"切换阈值{self.switch_threshold}%，"
                f"持有{self.holding_days}天")
    
    def detect_events(self, helper, date=None):
        """
        检测大小盘风格轮动信号
        
        返回: [{'symbol': 'ETF代码', 'name': 'ETF名称', 'reason': '事件描述'}, ...]
        """
        events = []
        
        # 获取两大盘指数数据
        large_df = self._get_index_data(self.large_cap_etf, helper, days=self.lookback_days + 10)
        small_df = self._get_index_data(self.small_cap_etf, helper, days=self.lookback_days + 10)
        
        if large_df.empty or small_df.empty:
            print("获取指数数据失败")
            return events
        
        # 计算近N日涨幅
        if len(large_df) < self.lookback_days or len(small_df) < self.lookback_days:
            print(f"数据不足：沪深300={len(large_df)}, 创业板={len(small_df)}")
            return events
        
        large_return = (large_df['close'].iloc[-1] / large_df['close'].iloc[-(self.lookback_days + 1)] - 1) * 100
        small_return = (small_df['close'].iloc[-1] / small_df['close'].iloc[-(self.lookback_days + 1)] - 1) * 100
        
        # 计算强弱差距
        diff = large_return - small_return
        diff_abs = abs(diff)
        
        # 判断当前应该持有哪个
        if diff_abs >= self.switch_threshold:
            # 差距超过阈值，需要轮动
            if large_return > small_return:
                winner = {
                    'symbol': self.large_cap_etf,
                    'name': self.etf_names.get(self.large_cap_etf, '大盘ETF'),
                    'return': large_return,
                    'loser_return': small_return,
                }
            else:
                winner = {
                    'symbol': self.small_cap_etf,
                    'name': self.etf_names.get(self.small_cap_etf, '小盘ETF'),
                    'return': small_return,
                    'loser_return': large_return,
                }
            
            events.append({
                'symbol': winner['symbol'],
                'name': winner['name'],
                'reason': (f"风格轮动信号：{winner['name']}近{self.lookback_days}日涨幅{winner['return']:.2f}%，"
                          f"较另一方{abs(winner['return'] - winner['loser_return']):.2f}%，超过阈值{self.switch_threshold}%")
            })
        else:
            # 差距未达阈值，保持当前持仓（如果有）
            if self._current_holding:
                current_name = self.etf_names.get(self._current_holding, self._current_holding)
                events.append({
                    'symbol': self._current_holding,
                    'name': current_name,
                    'reason': (f"维持{current_name}持仓：强弱差距{diff_abs:.2f}%<{self.switch_threshold}%阈值，"
                              f"沪深300涨幅{large_return:.2f}%，创业板涨幅{small_return:.2f}%")
                })
            else:
                # 无持仓时，选择相对强势
                if large_return >= small_return:
                    events.append({
                        'symbol': self.large_cap_etf,
                        'name': self.etf_names.get(self.large_cap_etf, '大盘ETF'),
                        'reason': (f"初始配置：沪深300涨幅{large_return:.2f}%>=创业板{small_return:.2f}%，"
                                  f"强弱差距{diff_abs:.2f}%<阈值")
                    })
                else:
                    events.append({
                        'symbol': self.small_cap_etf,
                        'name': self.etf_names.get(self.small_cap_etf, '小盘ETF'),
                        'reason': (f"初始配置：创业板涨幅{small_return:.2f}%>沪深300{large_return:.2f}%，"
                                  f"强弱差距{diff_abs:.2f}%<阈值")
                    })
        
        return events
    
    def select_stocks(self, helper, date=None):
        """
        选股：选择强势ETF
        继承自BaseStrategy，返回格式: [{'symbol': 'xxx', 'name': 'xxx', 'reason': 'xxx'}, ...]
        """
        # 检测轮动信号
        events = self.detect_events(helper, date)
        
        if events:
            # 记录当前持仓
            self._current_holding = events[0]['symbol']
            self._last_rotation_date = datetime.now().strftime("%Y-%m-%d")
        
        return events
    
    def _get_index_data(self, symbol, helper, days=60):
        """
        获取指数/ETF历史数据
        优先使用AKShare ETF接口，降级使用指数接口
        """
        # 尝试ETF专用接口
        try:
            if hasattr(helper, 'get_etf_history_kline'):
                df = helper.get_etf_history_kline(symbol, days=days)
                if not df.empty:
                    return df
        except Exception as e:
            pass
        
        # 尝试指数接口（对于510300等ETF也能获取）
        try:
            df = ak.fund_etf_hist_em(
                symbol=symbol,
                period="daily",
                start_date=(datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d")
            )
            if df is not None and not df.empty:
                return df.tail(days)
        except Exception as e:
            pass
        
        return pd.DataFrame()
    
    def get_rotation_status(self, helper):
        """
        获取当前轮动状态（用于诊断）
        """
        large_df = self._get_index_data(self.large_cap_etf, helper, days=self.lookback_days + 10)
        small_df = self._get_index_data(self.small_cap_etf, helper, days=self.lookback_days + 10)
        
        status = {
            'large_cap_etf': self.large_cap_etf,
            'large_cap_name': self.etf_names.get(self.large_cap_etf, '大盘ETF'),
            'small_cap_etf': self.small_cap_etf,
            'small_cap_name': self.etf_names.get(self.small_cap_etf, '小盘ETF'),
            'lookback_days': self.lookback_days,
            'switch_threshold': self.switch_threshold,
            'current_holding': self._current_holding,
            'last_rotation_date': self._last_rotation_date,
        }
        
        if not large_df.empty and not small_df.empty:
            if len(large_df) >= self.lookback_days + 1 and len(small_df) >= self.lookback_days + 1:
                large_return = (large_df['close'].iloc[-1] / large_df['close'].iloc[-(self.lookback_days + 1)] - 1) * 100
                small_return = (small_df['close'].iloc[-1] / small_df['close'].iloc[-(self.lookback_days + 1)] - 1) * 100
                diff = large_return - small_return
                
                status.update({
                    'large_return': large_return,
                    'small_return': small_return,
                    'return_diff': diff,
                    'diff_abs': abs(diff),
                    'need_rotation': abs(diff) >= self.switch_threshold,
                    'recommended': self.large_cap_etf if large_return > small_return else self.small_cap_etf,
                    'recommended_name': self.etf_names.get(
                        self.large_cap_etf if large_return > small_return else self.small_cap_etf,
                        '未知ETF'
                    ),
                })
        
        return status


if __name__ == '__main__':
    # 测试策略
    strategy = StyleRotationStrategy()
    print(f"策略: {strategy.name}")
    print(f"描述: {strategy.get_description()}")
    print(f"\n参数:")
    params = strategy.get_params()
    for k, v in params.items():
        print(f"  {k}: {v}")
    
    # 打印详细参数说明
    print(f"\n=== 大小盘风格轮动策略 ===")
    print(f"观察期: {strategy.lookback_days}天 - 用于比较近期涨幅的时间窗口")
    print(f"持有期: {strategy.holding_days}天 - 每次调仓后的持有天数")
    print(f"切换阈值: {strategy.switch_threshold}% - 强弱差距超过此值才切换")
    print(f"大盘ETF: {strategy.large_cap_etf}({strategy.etf_names.get(strategy.large_cap_etf, '大盘')})")
    print(f"小盘ETF: {strategy.small_cap_etf}({strategy.etf_names.get(strategy.small_cap_etf, '小盘')})")
