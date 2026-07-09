"""
新策略注册 - 集成到主回测系统

25个新开发的策略（新增3个S级策略）
"""

from strategies.etf_rotation_strategy import ETFRotationStrategy
from strategies.fundamental_small_cap_strategy import FundamentalSmallCapStrategy
from strategies.money_flow_event_strategy import MoneyFlowEventStrategy
from strategies.anti_overconfidence_strategy import AntiOverconfidenceStrategy
from strategies.industry_momentum_strategy import IndustryMomentumStrategy
from strategies.research_report_strategy import ResearchReportStrategy
from strategies.super_short_rebound_strategy import SuperShortReboundStrategy
from strategies.short_term_momentum_strategy import ShortTermMomentumStrategy
from strategies.low_turnover_strategy import LowVolatilityStrategy
from strategies.southbound_money_strategy import SouthboundMoneyStrategy
from strategies.dragon_tiger_list_strategy import DragonTigerListStrategy
from strategies.northbound_money_strategy import NorthboundMoneyStrategy
from strategies.value_growth_strategy import ValueGrowthStrategy
from strategies.profit_explosion_strategy import ProfitExplosionStrategy
from strategies.continuous_volume_strategy import ContinuousVolumeStrategy
from strategies.limit_callback_strategy import LimitCallbackStrategy
from strategies.golden_cross_strategy import GoldenCrossStrategy
from strategies.rsi_rebound_strategy import RSIReboundStrategy
from strategies.low_pb_value_strategy import LowPBValueStrategy
from strategies.KDJ_strategy import KDJStrategy
from strategies.high_dividend_strategy import HighDividendStrategy
from strategies.profit_exceeds_expectation_strategy import ProfitExceedsExpectationStrategy
# 新增3个S级策略
from strategies.institution_research_strategy import InstitutionResearchStrategy
from strategies.earnings_preview_strategy import EarningsPreviewStrategy
from strategies.northbound_change_strategy import NorthboundChangeStrategy
# 新增5个S级策略v2
from strategies.monthly_weekly_daily import MonthlyWeeklyDailyStrategy
from strategies.major_capital_flow import MajorCapitalFlowStrategy
from strategies.institution_survey import InstitutionSurveyStrategy
from strategies.north_money_timing import NorthMoneyTimingStrategy
from strategies.earnings_surprise_v2 import EarningsSurpriseV2Strategy

# 新策略注册表
NEW_STRATEGIES = {
    'ETF二八轮动': {
        'class': ETFRotationStrategy,
        'category': '轮动策略',
        'risk': '低',
        'description': '大小盘轮动，ETF免印花税'
    },
    '财务基本面过滤小市值': {
        'class': FundamentalSmallCapStrategy,
        'category': '基本面',
        'risk': '中',
        'description': '小市值+基本面过滤'
    },
    '资金流事件': {
        'class': MoneyFlowEventStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '资金持续流入事件'
    },
    '反过度自信': {
        'class': AntiOverconfidenceStrategy,
        'category': '逆向策略',
        'risk': '中',
        'description': '逆向投资，人弃我取'
    },
    '行业动量': {
        'class': IndustryMomentumStrategy,
        'category': '轮动策略',
        'risk': '中',
        'description': '追强势行业'
    },
    '研报推荐': {
        'class': ResearchReportStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '跟随券商研报'
    },
    '超跌反弹': {
        'class': SuperShortReboundStrategy,
        'category': '逆向策略',
        'risk': '高',
        'description': '严重超跌后反弹'
    },
    '短线动量': {
        'class': ShortTermMomentumStrategy,
        'category': '技术面',
        'risk': '高',
        'description': '追强势股，快进快出'
    },
    '低波动': {
        'class': LowVolatilityStrategy,
        'category': '防御策略',
        'risk': '低',
        'description': '低波动股票，熊市防御'
    },
    '南向资金': {
        'class': SouthboundMoneyStrategy,
        'category': '资金流',
        'risk': '中',
        'description': '成交放量代表资金关注'
    },
    '龙虎榜': {
        'class': DragonTigerListStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '机构和游资动向'
    },
    '北向资金': {
        'class': NorthboundMoneyStrategy,
        'category': '资金流',
        'risk': '中',
        'description': '外资动向'
    },
    '价值成长': {
        'class': ValueGrowthStrategy,
        'category': '价值策略',
        'risk': '低',
        'description': '低PE+高成长'
    },
    '业绩暴增': {
        'class': ProfitExplosionStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '业绩超预期驱动'
    },
    '量价齐升': {
        'class': ContinuousVolumeStrategy,
        'category': '技术面',
        'risk': '中',
        'description': '量价配合上涨'
    },
    '涨停回调': {
        'class': LimitCallbackStrategy,
        'category': '事件驱动',
        'risk': '高',
        'description': '涨停后回调介入'
    },
    'MACD金叉': {
        'class': GoldenCrossStrategy,
        'category': '技术面',
        'risk': '中',
        'description': 'MACD零轴上方金叉'
    },
    'RSI超卖反转': {
        'class': RSIReboundStrategy,
        'category': '技术面',
        'risk': '中',
        'description': 'RSI超卖反弹'
    },
    '低PB价值': {
        'class': LowPBValueStrategy,
        'category': '价值策略',
        'risk': '低',
        'description': '低PB价值投资'
    },
    'KDJ超卖金叉': {
        'class': KDJStrategy,
        'category': '技术面',
        'risk': '中',
        'description': 'KDJ超卖金叉'
    },
    '高股息': {
        'class': HighDividendStrategy,
        'category': '价值策略',
        'risk': '低',
        'description': '高股息稳定收益'
    },
    '业绩超预期': {
        'class': ProfitExceedsExpectationStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '业绩超预期事件'
    },
    # 新增3个S级策略
    '机构调研': {
        'class': InstitutionResearchStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '机构调研后买入，专业资金关注'
    },
    '业绩预告超预期': {
        'class': EarningsPreviewStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '业绩预告净利润增速>20%'
    },
    '北向持仓变化': {
        'class': NorthboundChangeStrategy,
        'category': '资金流',
        'risk': '中',
        'description': '北向资金快速增持'
    },
    # 新增5个S级策略v2
    '多周期共振Pro': {
        'class': MonthlyWeeklyDailyStrategy,
        'category': '趋势策略',
        'risk': '中',
        'description': '日周月三周期共振，多时间框架确认'
    },
    '主力资金流向': {
        'class': MajorCapitalFlowStrategy,
        'category': '资金流',
        'risk': '中',
        'description': '追踪主力资金净流入，聪明钱信号'
    },
    '机构调研效应': {
        'class': InstitutionSurveyStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '机构调研后效应，专业资金关注'
    },
    '北向资金择时': {
        'class': NorthMoneyTimingStrategy,
        'category': '资金流',
        'risk': '中',
        'description': '北向资金持仓变化择时'
    },
    '财报季惊喜': {
        'class': EarningsSurpriseV2Strategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '业绩改善信号，财报季alpha'
    },
}


def get_new_strategy(name):
    """获取新策略实例"""
    if name in NEW_STRATEGIES:
        return NEW_STRATEGIES[name]['class']()
    return None


def list_new_strategies():
    """列出所有新策略"""
    return list(NEW_STRATEGIES.keys())
