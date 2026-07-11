# -*- coding: utf-8 -*-
"""
行业轮动策略

策略核心逻辑：
1. 三维度打分选行业：政策分(30%)、资金分(40%)、业绩分(30%)
2. 选取综合得分Top 3行业
3. 在强势行业中选取龙头股（成交额最大）
4. 月度调仓

关键指标：
- RS相对强度：板块涨幅/沪深300涨幅，连续5日>1.2
- 资金流入率：(买入额-卖出额)/总成交额 >10%
- 动量斜率：20日线性回归 >30°
- 拥挤度：板块涨跌家数集中度 <50%

参考：邢不行课程 - 风火轮策略
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.base import BaseStrategy
import akshare as ak


class SectorRotationStrategy(BaseStrategy):
    """行业轮动策略"""
    
    def __init__(self,
                 top_n_industries=3,      # 持有行业数量
                 top_n_stocks=3,          # 每个行业选股数量
                 rs_threshold=1.2,        # RS相对强度阈值
                 fund_flow_threshold=10,   # 资金流入率阈值(%)
                 momentum_threshold=30,    # 动量斜率阈值(度)
                 crowding_threshold=50,    # 拥挤度阈值(%)
                 rebalance_monthly=True,   # 月度调仓
                 stop_loss=-6,            # 止损线（%）
                 take_profit=12):        # 止盈线（%）
        super().__init__("行业轮动", "轮动策略")
        self.top_n_industries = top_n_industries
        self.top_n_stocks = top_n_stocks
        self.rs_threshold = rs_threshold
        self.fund_flow_threshold = fund_flow_threshold
        self.momentum_threshold = momentum_threshold
        self.crowding_threshold = crowding_threshold
        self.rebalance_monthly = rebalance_monthly
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        
        # 行业ETF映射（用于计算行业动量）
        self.industry_etfs = {
            '白酒': '512690.SH',
            '医疗': '512010.SH',
            '芯片': '512760.SH',
            '新能源': '515030.SH',
            '证券': '512880.SH',
            '军工': '512660.SH',
            '消费': '159928.SH',
            '科技': '515000.SH',
            '银行': '512800.SH',
            '房地产': '512200.SH',
            '煤炭': '515220.SH',
            '有色金属': '512400.SH',
            '化工': '159870.SH',
            '钢铁': '512210.SH',
            '电力': '512170.SH',
            '汽车': '516110.SH',
            '机械设备': '159886.SH',
            '电子': '512761.SH',
            '计算机': '159998.SH',
            '传媒': '159805.SH',
        }
        
        # 政策利好行业关键词
        self.policy_keywords = [
            'AI', '人工智能', '半导体', '芯片', '新能源', '汽车', '家电',
            '医药', '医疗', '消费', '数字经济', '数据要素', '国企改革',
            '专精特新', '高端制造', '工业母机', '机器人', '低空经济'
        ]
        
        self._industry_cache = None
        self._hs300_data = None
        
    def detect_events(self, helper, date=None):
        """
        检测行业轮动事件：识别强势行业轮换信号
        
        返回: [{'symbol': '行业名', 'name': '行业名', 'reason': '事件描述'}, ...]
        """
        events = []
        
        # 获取行业列表
        industry_list = self._get_industry_list()
        if not industry_list:
            industry_list = list(self.industry_etfs.keys())
        
        # 获取沪深300基准
        hs300_df = self._get_hs300_data(days=30)
        
        # 遍历行业找轮动信号
        for industry in industry_list[:50]:
            if isinstance(industry, dict):
                industry_name = industry.get('板块名称', industry.get('行业', ''))
            else:
                industry_name = str(industry)
            
            if not industry_name:
                continue
            
            try:
                industry_df = self._get_industry_historical(industry_name)
                
                # 计算关键指标
                rs = self._calculate_rs_strength(industry_df, hs300_df)
                momentum = self._calculate_momentum_slope(industry_df)
                policy_score = self._calculate_policy_score(industry_name)
                fund_score = self._calculate_fund_score(industry_name, industry_df, hs300_df)
                total_score = policy_score * 0.3 + fund_score * 0.4 + self._calculate_growth_score(industry_name, industry_df) * 0.3
                
                # 检测轮动信号：RS > 阈值 AND 动量 > 阈值
                if rs > self.rs_threshold and momentum > self.momentum_threshold:
                    events.append({
                        'symbol': industry_name,
                        'name': industry_name,
                        'reason': f"行业轮动信号：RS={rs:.2f}>阈值{momentum}，动量={momentum:.1f}°，综合{total_score:.1f}分"
                    })
            except Exception as e:
                continue
        
        # 按RS强度排序
        events.sort(key=lambda x: float(x['reason'].split('RS=')[1].split('>')[0]) if 'RS=' in x['reason'] else 0, reverse=True)
        
        return events[:self.top_n_industries]
    
    def get_description(self):
        return (f"行业轮动：三维度打分(政策30%+资金40%+业绩30%), "
                f"持有Top{self.top_n_industries}行业, "
                f"RS>{self.rs_threshold}, 资金流入>{self.fund_flow_threshold}%, "
                f"{'月度' if self.rebalance_monthly else '每周'}调仓")
    
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
    
    def _get_industry_historical(self, industry_name):
        """获取行业历史表现"""
        try:
            df = ak.stock_board_industry_hist_em(symbol=industry_name, 
                                                  start_date=(datetime.now() - timedelta(days=60)).strftime("%Y%m%d"),
                                                  end_date=datetime.now().strftime("%Y%m%d"))
            if df is not None and not df.empty:
                return df
        except Exception as e:
            print(f"获取行业历史失败 {industry_name}: {e}")
        return pd.DataFrame()
    
    def _get_hs300_data(self, days=30):
        """获取沪深300指数数据"""
        if self._hs300_data is not None and len(self._hs300_data) >= days:
            return self._hs300_data
        
        try:
            df = ak.stock_zh_index_daily(symbol='sh000300')
            if df is not None and not df.empty:
                df = df.tail(days)
                self._hs300_data = df
                return df
        except Exception as e:
            print(f"获取沪深300数据失败: {e}")
        return pd.DataFrame()
    
    def _calculate_rs_strength(self, industry_df, hs300_df):
        """计算RS相对强度：板块涨幅/沪深300涨幅"""
        if industry_df is None or industry_df.empty or hs300_df is None or hs300_df.empty:
            return 0
        
        # 取最近5日数据
        ind_5d = industry_df.tail(5)
        hs300_5d = hs300_df.tail(5)
        
        if len(ind_5d) < 3 or len(hs300_5d) < 3:
            return 0
        
        # 计算区间涨幅
        ind_return = (ind_5d['close'].iloc[-1] / ind_5d['close'].iloc[0] - 1) * 100
        hs300_return = (hs300_5d['close'].iloc[-1] / hs300_5d['close'].iloc[0] - 1) * 100
        
        if hs300_return == 0:
            return 0
        
        rs = ind_return / hs300_return if hs300_return != 0 else 0
        return rs
    
    def _calculate_momentum_slope(self, industry_df):
        """计算动量斜率：20日线性回归角度"""
        if industry_df is None or industry_df.empty or len(industry_df) < 20:
            return 0
        
        df = industry_df.tail(20)
        x = np.arange(len(df))
        y = df['close'].values
        
        # 线性回归
        try:
            coeffs = np.polyfit(x, y, 1)
            slope = coeffs[0]
            # 计算角度（度）
            angle = np.degrees(np.arctan(slope / df['close'].mean() * len(df)))
            return angle
        except Exception:
            return 0
    
    def _get_industry_fund_flow(self, industry_name):
        """获取行业资金流向"""
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry_name)
            if df is not None and not df.empty:
                # 计算整体资金流入率
                if '涨跌幅' in df.columns and '换手率' in df.columns:
                    # 简化：使用换手率和涨跌幅估算资金流向
                    avg_turnover = df['换手率'].mean() if '换手率' in df.columns else 0
                    avg_change = df['涨跌幅'].mean() if '涨跌幅' in df.columns else 0
                    return avg_turnover, avg_change
        except Exception as e:
            print(f"获取行业资金流向失败 {industry_name}: {e}")
        return 0, 0
    
    def _get_sector_stocks(self, industry_name, top_n=3):
        """获取行业中成交额最大的龙头股"""
        try:
            df = ak.stock_board_industry_cons_em(symbol=industry_name)
            if df is not None and not df.empty:
                # 按成交额排序
                if '成交额' in df.columns:
                    df = df.sort_values('成交额', ascending=False)
                elif '成交额' in df.columns:
                    df = df.sort_values('成交额', ascending=False)
                
                stocks = []
                for _, row in df.head(top_n).iterrows():
                    symbol = str(row.get('代码', ''))
                    name = str(row.get('名称', symbol))
                    stocks.append({
                        'symbol': symbol,
                        'name': name,
                        'change_pct': row.get('涨跌幅', 0),
                        'turnover': row.get('换手率', 0),
                    })
                return stocks
        except Exception as e:
            print(f"获取行业成分股失败 {industry_name}: {e}")
        return []
    
    def _calculate_policy_score(self, industry_name):
        """计算政策分（0-100）"""
        score = 50  # 基础分
        
        name_lower = industry_name.lower()
        for keyword in self.policy_keywords:
            if keyword.lower() in name_lower:
                score += 10
                if score >= 100:
                    return 100
        
        return min(score, 100)
    
    def _calculate_fund_score(self, industry_name, industry_df, hs300_df):
        """计算资金分（0-100）"""
        score = 50  # 基础分
        
        # RS相对强度得分
        rs = self._calculate_rs_strength(industry_df, hs300_df)
        if rs > self.rs_threshold:
            score += 30
        elif rs > 1.0:
            score += 15
        
        # 动量斜率得分
        slope = self._calculate_momentum_slope(industry_df)
        if slope > self.momentum_threshold:
            score += 20
        elif slope > 20:
            score += 10
        
        return min(score, 100)
    
    def _calculate_growth_score(self, industry_name, industry_df):
        """计算业绩分（0-100）"""
        score = 50  # 基础分
        
        if industry_df is not None and not industry_df.empty:
            # 计算近期涨幅作为业绩代理指标
            if len(industry_df) >= 20:
                ret_20d = (industry_df['close'].iloc[-1] / industry_df['close'].iloc[-20] - 1) * 100
                if ret_20d > 10:
                    score += 30
                elif ret_20d > 5:
                    score += 15
            
            # 计算波动率（低波动加分）
            if 'close' in industry_df.columns:
                volatility = industry_df['close'].pct_change().std() * 100
                if volatility < 2:
                    score += 20
                elif volatility < 3:
                    score += 10
        
        return min(score, 100)
    
    def select_stocks(self, helper, date=None):
        """选股：基于行业轮动选择龙头股"""
        results = []
        
        # 1. 获取行业列表
        industry_list = self._get_industry_list()
        if not industry_list:
            print("获取行业列表为空，使用ETF映射")
            industry_list = list(self.industry_etfs.keys())
        
        # 2. 获取沪深300基准数据
        hs300_df = self._get_hs300_data(days=30)
        
        # 3. 对每个行业进行三维度打分
        industry_scores = []
        
        for industry in industry_list[:50]:  # 限制处理数量
            if isinstance(industry, dict):
                industry_name = industry.get('板块名称', industry.get('行业', ''))
            else:
                industry_name = str(industry)
            
            if not industry_name:
                continue
            
            try:
                # 获取行业历史数据
                industry_df = self._get_industry_historical(industry_name)
                
                # 计算三维度得分
                policy_score = self._calculate_policy_score(industry_name)
                fund_score = self._calculate_fund_score(industry_name, industry_df, hs300_df)
                growth_score = self._calculate_growth_score(industry_name, industry_df)
                
                # 综合得分（权重：政策30% + 资金40% + 业绩30%）
                total_score = (policy_score * 0.3 + 
                              fund_score * 0.4 + 
                              growth_score * 0.3)
                
                # 获取关键指标
                rs = self._calculate_rs_strength(industry_df, hs300_df)
                momentum = self._calculate_momentum_slope(industry_df)
                
                industry_scores.append({
                    'industry': industry_name,
                    'total_score': total_score,
                    'policy_score': policy_score,
                    'fund_score': fund_score,
                    'growth_score': growth_score,
                    'rs': rs,
                    'momentum': momentum,
                    'history_df': industry_df
                })
            except Exception as e:
                print(f"评分失败 {industry_name}: {e}")
                continue
        
        # 4. 按综合得分排序
        industry_scores.sort(key=lambda x: x['total_score'], reverse=True)
        
        # 5. 选取Top N行业
        top_industries = industry_scores[:self.top_n_industries]
        
        print(f"\n=== 行业轮动 Top{self.top_n_industries} ===")
        for ind in top_industries:
            print(f"  {ind['industry']}: 综合{ind['total_score']:.1f}分 "
                  f"(政策{ind['policy_score']:.0f} + 资金{ind['fund_score']:.0f} + 业绩{ind['growth_score']:.0f}) "
                  f"RS={ind['rs']:.2f} 动量={ind['momentum']:.1f}°")
        
        # 6. 在强势行业中选取龙头股
        for ind in top_industries:
            industry_name = ind['industry']
            stocks = self._get_sector_stocks(industry_name, top_n=self.top_n_stocks)
            
            for stock in stocks:
                # 检查是否已持仓
                existing = [h for h in self.holdings if h['symbol'] == stock['symbol']]
                if existing:
                    continue
                
                results.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'reason': (f"行业轮动：{industry_name} "
                              f"(综合{ind['total_score']:.1f}分, "
                              f"政策{int(ind['policy_score'])}+资金{int(ind['fund_score'])}+业绩{int(ind['growth_score'])})")
                })
                
                if len(results) >= self.top_n_industries * self.top_n_stocks:
                    break
            
            if len(results) >= self.top_n_industries * self.top_n_stocks:
                break
        
        return results[:self.top_n_industries * self.top_n_stocks]


if __name__ == '__main__':
    strategy = SectorRotationStrategy()
    print(f"策略: {strategy.name}")
    print(f"描述: {strategy.get_description()}")
    print(f"\n关键指标:")
    print(f"  RS相对强度阈值: >{strategy.rs_threshold}")
    print(f"  资金流入率阈值: >{strategy.fund_flow_threshold}%")
    print(f"  动量斜率阈值: >{strategy.momentum_threshold}°")
    print(f"  持仓行业数: {strategy.top_n_industries}")
    print(f"  每行业选股: {strategy.top_n_stocks}")
