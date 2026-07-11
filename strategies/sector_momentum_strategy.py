# -*- coding: utf-8 -*-
"""
行业动量策略

策略核心逻辑：
1. 选取近N日涨幅最大的行业板块
2. 在强势板块中选取龙头股（成交额最大）
3. 等权持有，等待板块轮动

买入信号：
- 行业近5日涨幅排名Top 3
- 个股在板块中成交额最大
- 股价站上20日均线

卖出信号：
- 行业跌破20日均线
- 持仓超过5个交易日
- 行业轮动到其他板块

参数配置：
| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| 行业排名天数 | 5 | 3-20 | 统计近几日涨幅 |
| 持仓数量 | 3 | 1-5 | 每次持仓数量 |
| 持有天数 | 5 | 3-10 | 最长持有时间 |

参考：c:\Users\xrs08\Documents\Obsidian Vault\2-阅读\研究\A股量化策略研究\01-策略详情\行业动量.md
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.base import BaseStrategy
import akshare as ak


class SectorMomentumStrategy(BaseStrategy):
    """行业动量策略"""
    
    def __init__(self,
                 momentum_days=5,          # 行业排名天数（统计近几日涨幅）
                 top_n_sectors=3,          # 强势行业数量
                 top_n_stocks=1,           # 每个行业选股数量
                 holding_days=5,           # 最长持有时间
                 ma_period=20):            # 均线周期
        super().__init__("行业动量", "轮动策略")
        self.momentum_days = momentum_days
        self.top_n_sectors = top_n_sectors
        self.top_n_stocks = top_n_stocks
        self.holding_days = holding_days
        self.ma_period = ma_period
        
        # 缓存
        self._industry_cache = None
        self._industry_ranking = {}  # 行业动量排名缓存
        
    def get_params(self):
        """获取策略参数"""
        return {
            'momentum_days': self.momentum_days,
            'top_n_sectors': self.top_n_sectors,
            'top_n_stocks': self.top_n_stocks,
            'holding_days': self.holding_days,
            'ma_period': self.ma_period,
        }
    
    def get_description(self):
        return (f"行业动量：近{self.momentum_days}日涨幅Top{self.top_n_sectors}行业, "
                f"选龙头股(成交额最大), 站上{self.ma_period}日均线, "
                f"持有≤{self.holding_days}日")
    
    def detect_events(self, helper, date=None):
        """
        检测行业动量事件：识别强势行业及其龙头股
        
        返回: [{'symbol': '000001', 'name': 'xxx', 'reason': '事件描述'}, ...]
        """
        events = []
        
        # 1. 获取行业板块列表
        industry_list = self._get_industry_list()
        if not industry_list:
            return events
        
        # 2. 计算各行业近N日涨幅并排序
        industry_momentum = self._calculate_industry_momentum(industry_list)
        
        if not industry_momentum:
            return events
        
        # 按涨幅排序，选取Top N强势行业
        industry_momentum.sort(key=lambda x: x['return_pct'], reverse=True)
        top_industries = industry_momentum[:self.top_n_sectors]
        
        print(f"\n=== 行业动量 Top{self.top_n_sectors} ===")
        for ind in top_industries:
            print(f"  {ind['industry']}: 近{self.momentum_days}日涨幅 {ind['return_pct']:.2f}%")
        
        # 3. 在强势行业中选取龙头股（成交额最大且站上均线）
        for ind in top_industries:
            industry_name = ind['industry']
            stocks = self._get_sector_leaders(industry_name)
            
            for stock in stocks:
                # 检查是否已持仓
                existing = [h for h in self.holdings if h['symbol'] == stock['symbol']]
                if existing:
                    continue
                
                # 检查股价是否站上20日均线
                if self._check_price_above_ma(stock['symbol']):
                    events.append({
                        'symbol': stock['symbol'],
                        'name': stock['name'],
                        'reason': (f"行业动量：{industry_name} "
                                  f"(近{self.momentum_days}日涨幅{ind['return_pct']:.1f}%, "
                                  f"成交额第1)")
                    })
                else:
                    print(f"  {stock['name']} 未站上{self.ma_period}日均线，跳过")
                
                if len(events) >= self.top_n_sectors:
                    break
            
            if len(events) >= self.top_n_sectors:
                break
        
        return events
    
    def select_stocks(self, helper, date=None):
        """选股：基于行业动量选择龙头股"""
        # 使用 detect_events 的结果
        events = self.detect_events(helper, date)
        return events[:self.top_n_sectors]
    
    def _get_industry_list(self):
        """获取行业板块列表"""
        if self._industry_cache is not None:
            return self._industry_cache
        
        try:
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                self._industry_cache = df.to_dict('records')
                return self._industry_cache
        except Exception as e:
            print(f"获取行业板块失败: {e}")
        
        return []
    
    def _calculate_industry_momentum(self, industry_list):
        """
        计算各行业近N日涨幅
        返回: [{'industry': '行业名', 'return_pct': 涨幅}, ...]
        """
        momentum = []
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=self.momentum_days * 4)).strftime("%Y%m%d")
        
        for industry in industry_list[:50]:  # 限制处理数量
            if isinstance(industry, dict):
                industry_name = industry.get('板块名称', industry.get('行业', ''))
            else:
                industry_name = str(industry)
            
            if not industry_name:
                continue
            
            try:
                # 获取行业历史K线
                df = ak.stock_board_industry_hist_em(
                    symbol=industry_name,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df is not None and not df.empty and len(df) >= self.momentum_days:
                    # 计算近N日涨幅
                    df = df.tail(self.momentum_days)
                    start_price = df['收盘'].iloc[0]
                    end_price = df['收盘'].iloc[-1]
                    
                    if start_price > 0:
                        return_pct = (end_price / start_price - 1) * 100
                        momentum.append({
                            'industry': industry_name,
                            'return_pct': return_pct,
                            'history_df': df
                        })
            except Exception as e:
                continue
        
        return momentum
    
    def _get_sector_leaders(self, industry_name, top_n=1):
        """
        获取行业中成交额最大的龙头股
        """
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry_name)
            if df is not None and not df.empty:
                # 按成交额排序（降序）
                if '成交额' in df.columns:
                    df = df.sort_values('成交额', ascending=False)
                
                stocks = []
                for _, row in df.head(top_n).iterrows():
                    symbol = str(row.get('代码', ''))
                    name = str(row.get('名称', symbol))
                    turnover = row.get('成交额', 0)
                    change_pct = row.get('涨跌幅', 0)
                    stocks.append({
                        'symbol': symbol,
                        'name': name,
                        'turnover': turnover,
                        'change_pct': change_pct,
                    })
                return stocks
        except Exception as e:
            print(f"获取行业成分股失败 {industry_name}: {e}")
        return []
    
    def _check_price_above_ma(self, symbol, period=None):
        """
        检查股价是否站上均线
        period: 均线周期，默认使用 self.ma_period
        """
        period = period or self.ma_period
        
        try:
            # 获取历史K线
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=period * 3)).strftime("%Y%m%d")
            
            # 尝试新浪源
            prefix = 'sh' if symbol.startswith('6') else 'sz'
            sina_symbol = f"{prefix}{symbol}"
            df = ak.stock_zh_a_daily(symbol=sina_symbol, start_date=start_date,
                                      end_date=end_date, adjust="qfq")
            
            if df is None or df.empty:
                # 降级用东财
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                        start_date=start_date, end_date=end_date,
                                        adjust="qfq")
            
            if df is not None and not df.empty and len(df) >= period:
                # 计算均线
                df = df.tail(period + 5)
                if '收盘' in df.columns:
                    ma = df['收盘'].rolling(window=period).mean().iloc[-1]
                    current_price = df['收盘'].iloc[-1]
                    return current_price > ma
                elif 'close' in df.columns:
                    ma = df['close'].rolling(window=period).mean().iloc[-1]
                    current_price = df['close'].iloc[-1]
                    return current_price > ma
        except Exception as e:
            print(f"检查均线失败 {symbol}: {e}")
        return False
    
    def should_sell(self, holding, current_data=None):
        """
        判断是否应该卖出持仓
        
        卖出信号：
        1. 行业跌破20日均线
        2. 持仓超过N个交易日
        3. 行业轮动到其他板块
        
        holding: 持仓信息
        current_data: 当前市场数据（包含行业信息）
        """
        # 1. 检查持有天数
        if holding.get('hold_days', 0) >= self.holding_days:
            return True, "持有超过最大期限"
        
        # 2. 检查行业是否跌破均线
        industry_name = holding.get('timing_reason', '')
        if industry_name and '行业动量' in industry_name:
            # 提取行业名
            try:
                parts = industry_name.split('：')
                if len(parts) > 1:
                    ind_name = parts[1].split('(')[0].strip()
                    if self._check_industry_below_ma(ind_name):
                        return True, f"{ind_name}跌破{self.ma_period}日均线"
            except Exception:
                pass
        
        return False, ""
    
    def _check_industry_below_ma(self, industry_name, period=None):
        """
        检查行业指数是否跌破均线
        """
        period = period or self.ma_period
        
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=period * 4)).strftime("%Y%m%d")
            
            df = ak.stock_board_industry_hist_em(
                symbol=industry_name,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and not df.empty and len(df) >= period:
                df = df.tail(period + 5)
                if '收盘' in df.columns:
                    ma = df['收盘'].rolling(window=period).mean().iloc[-1]
                    current_price = df['收盘'].iloc[-1]
                    return current_price < ma
        except Exception as e:
            print(f"检查行业均线失败 {industry_name}: {e}")
        return False
    
    def check_sector_rotation(self, current_top_industries):
        """
        检查行业是否轮动（当前强势行业与持仓不同）
        
        current_top_industries: 当前强势行业列表
        """
        if not self.holdings:
            return False, None
        
        # 提取持仓中的行业
        holding_industries = set()
        for h in self.holdings:
            reason = h.get('timing_reason', '')
            if '行业动量' in reason:
                try:
                    parts = reason.split('：')
                    if len(parts) > 1:
                        ind_name = parts[1].split('(')[0].strip()
                        holding_industries.add(ind_name)
                except Exception:
                    pass
        
        # 检查是否仍有持仓在强势行业中
        current_inds = set([ind['industry'] for ind in current_top_industries[:self.top_n_sectors]])
        
        still_strong = holding_industries & current_inds
        if not still_strong and holding_industries:
            return True, list(holding_industries)[0]
        
        return False, None


if __name__ == '__main__':
    strategy = SectorMomentumStrategy()
    print(f"策略: {strategy.name}")
    print(f"描述: {strategy.get_description()}")
    print(f"\n参数配置:")
    print(f"  行业排名天数: {strategy.momentum_days} (范围: 3-20)")
    print(f"  持仓数量: {strategy.top_n_sectors} (范围: 1-5)")
    print(f"  持有天数: {strategy.holding_days} (范围: 3-10)")
    print(f"  均线周期: {strategy.ma_period}")
