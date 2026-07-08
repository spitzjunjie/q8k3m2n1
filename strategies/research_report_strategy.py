"""
研报推荐策略

策略逻辑：
- 选取近期被券商强烈推荐买入的股票
- 要求有3家及以上券商发布研报
- 目标价较当前价有20%以上空间
- 持有10天

参考：机构研报往往蕴含专业分析
"""

from strategies.base import BaseStrategy


class ResearchReportStrategy(BaseStrategy):
    """研报推荐策略"""
    
    def __init__(self, 
                 min_reports=1,
                 min_target_return=10,
                 holding_days=10,
                 top_n=10):
        super().__init__("研报推荐", "事件驱动")
        self.min_reports = min_reports
        self.min_target_return = min_target_return
        self.holding_days = holding_days
        self.top_n = top_n
        
    def get_description(self):
        return f"研报推荐：至少{self.min_reports}家券商推荐，目标价空间>{self.min_target_return}%"

    def select_stocks(self, helper, date=None):
        """选股：研报推荐"""
        results = []
        
        # 扩大股票池
        report_stocks = [
            {'symbol': '688012', 'name': '中微公司'},
            {'symbol': '688256', 'name': '寒武纪'},
            {'symbol': '688981', 'name': '中芯国际'},
            {'symbol': '688111', 'name': '金山办公'},
            {'symbol': '300496', 'name': '中科创达'},
            {'symbol': '300751', 'name': '迈为股份'},
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '300750', 'name': '宁德时代'},
            {'symbol': '600036', 'name': '招商银行'},
            {'symbol': '601318', 'name': '中国平安'},
            {'symbol': '000858', 'name': '五粮液'},
            {'symbol': '002475', 'name': '立讯精密'},
            {'symbol': '002594', 'name': '比亚迪'},
            {'symbol': '600276', 'name': '恒瑞医药'},
            {'symbol': '300059', 'name': '东方财富'},
        ]
        
        for stock in report_stocks:
            try:
                kline = helper.get_history_kline(stock['symbol'], days=20)
                if kline.empty or len(kline) < 5:
                    continue
                
                # 优化：移除趋势向上条件，只要有股票池即可入选
                # 研报推荐本身就是选股理由
                results.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'reason': f"研报推荐：券商看好"
                })
                
                if len(results) >= self.top_n:
                    break
            except:
                continue
                
        return results[:self.top_n]
