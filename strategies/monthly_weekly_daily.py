"""
多时间框架共振策略

策略逻辑：
- 日线、周线、月线趋势同向（多头排列）
- 三周期共振确认趋势
- 适用于趋势明确的市场

参考：多周期共振是多周期共振策略的升级版
"""

from strategies.base import BaseStrategy


class MonthlyWeeklyDailyStrategy(BaseStrategy):
    """多时间框架共振策略"""
    
    def __init__(self, 
                 holding_days=10):
        super().__init__("多周期共振Pro", "趋势策略")
        self.holding_days = holding_days
        
    def get_description(self):
        return f"多时间框架共振：日周月三周期同向，持有{self.holding_days}天"

    def select_stocks(self, helper, date=None):
        """选股：日周月三周期共振"""
        results = []
        
        # 使用沪深300成分股
        try:
            pool = helper.get_stock_pool("hs300", sorted_by_market_value=True)[:60]
        except:
            pool = [
                '600519', '600036', '601318', '300750', '000858',
                '002475', '600887', '000333', '000001', '600030',
                '601166', '600900', '601012', '002594', '600276',
                '000725', '002422', '000100', '300059', '601899'
            ]
        
        for symbol in pool:
            try:
                # 获取日线数据
                daily = helper.get_history_kline(symbol, days=70)
                if daily.empty or len(daily) < 60:
                    continue
                
                # 计算日线均线
                ma5_d = daily['close'].iloc[-5:].mean()
                ma20_d = daily['close'].tail(20).mean()
                price_d = daily['close'].iloc[-1]
                
                # 日线趋势判断（多头排列）
                daily_bullish = ma5_d > ma20_d and price_d > ma5_d
                
                if not daily_bullish:
                    continue
                
                # 获取周线数据（用日线模拟周线）
                weekly = daily.iloc[::5]  # 每5天取一个点模拟周线
                if len(weekly) < 10:
                    continue
                ma5_w = weekly['close'].iloc[-5:].mean()
                ma20_w = weekly['close'].tail(5).mean()
                price_w = weekly['close'].iloc[-1]
                
                # 周线趋势判断
                weekly_bullish = ma5_w > ma20_w and price_w > ma5_w
                
                if not weekly_bullish:
                    continue
                
                # 获取月线数据（用周线模拟月线）
                monthly = weekly.iloc[::4]  # 每4周取一个点模拟月线
                if len(monthly) < 3:
                    continue
                ma5_m = monthly['close'].iloc[-3:].mean()
                ma20_m = monthly['close'].tail(2).mean()
                price_m = monthly['close'].iloc[-1]
                
                # 月线趋势判断
                monthly_bullish = ma5_m > ma20_m and price_m > ma5_m
                
                if not monthly_bullish:
                    continue
                
                # 三周期共振
                if daily_bullish and weekly_bullish and monthly_bullish:
                    try:
                        name = helper.get_realtime_quote(symbol)
                        name = name.get('名称', symbol) if name else symbol
                    except:
                        name = symbol
                    
                    results.append({
                        'symbol': symbol,
                        'name': name,
                        'reason': f"多周期共振Pro：三周期多头，日涨{((price_d/ma20_d-1)*100):.1f}%，周涨{((price_w/ma20_w-1)*100):.1f}%"
                    })
                    
                    if len(results) >= 5:
                        break
                        
            except Exception as e:
                continue
                
        return results[:5]
