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
# 新增11个GitHub开源研究策略v3
from strategies.moat_strategy import MoatStrategy
from strategies.piotroski_strategy import PiotroskiStrategy
from strategies.garp_strategy import GARPStrategy
from strategies.high_growth_strategy import HighGrowthStrategy
from strategies.cycle_timing_strategy import CycleTimingStrategy
from strategies.repurchase_strategy import RepurchaseStrategy
from strategies.equity_incentive_strategy import EquityIncentiveStrategy
from strategies.lockup_expiry_strategy import LockupExpiryStrategy
from strategies.dragon_tiger_follow_strategy import DragonTigerFollowStrategy
from strategies.limit_up_relay_strategy import LimitUpRelayStrategy
from strategies.new_stock_strategy import NewStockStrategy
# 新增4个研究驱动策略v4（基于海外交易者方法论+量化经典书系）
from strategies.perilla_chokepoint_strategy import PerillaChokepointStrategy
from strategies.sepa_growth_strategy import SEPAGrowthStrategy
from strategies.cointegration_pairs_strategy import CointegrationPairsStrategy
from strategies.hurst_timing_strategy import HurstTimingStrategy
# 新增13个GitHub开源研究策略v5（短线交易类+套利另类类+基本面深度类）
from strategies.auction_selection_strategy import AuctionSelectionStrategy
from strategies.after_hours_momentum_strategy import AfterHoursMomentumStrategy
from strategies.hot_money_tracking_strategy import HotMoneyTrackingStrategy
from strategies.limit_up_seal_strategy import LimitUpSealStrategy
from strategies.limit_down_rebound_strategy import LimitDownReboundStrategy
from strategies.convertible_bond_double_low_strategy import ConvertibleBondDoubleLowStrategy
from strategies.convertible_bond_downward_strategy import ConvertibleBondDownwardStrategy
from strategies.etf_premium_arbitrage_strategy import ETFPremiumArbitrageStrategy
from strategies.grid_trading_strategy import GridTradingStrategy
from strategies.lockup_expiry_arbitrage_strategy import LockupExpiryArbitrageStrategy
from strategies.davis_double_hit_strategy import DavisDoubleHitStrategy
from strategies.turnaround_strategy import TurnaroundStrategy
from strategies.shareholder_change_strategy import ShareholderChangeStrategy
from strategies.chip_distribution_strategy import ChipDistributionStrategy
# 新增强版质量因子选股策略（ Piotroski F-Score + Altman Z-Score）
from strategies.quality_factor_strategy import QualityFactorStrategy

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
    # 新增11个GitHub开源研究策略v3
    '护城河选股': {
        'class': MoatStrategy,
        'category': '质量因子',
        'risk': '低',
        'description': '高ROE+高毛利+低负债，巴菲特护城河'
    },
    '质量因子选股': {
        'class': PiotroskiStrategy,
        'category': '质量因子',
        'risk': '低',
        'description': 'Piotroski F-Score≥7分，高质量公司'
    },
    'GARP成长': {
        'class': GARPStrategy,
        'category': '价值成长',
        'risk': '中',
        'description': 'PEG<1，合理价格成长股'
    },
    '高成长股': {
        'class': HighGrowthStrategy,
        'category': '成长因子',
        'risk': '中',
        'description': '营收+净利双高增长，动能确认'
    },
    '周期股择时': {
        'class': CycleTimingStrategy,
        'category': '价值因子',
        'risk': '中',
        'description': 'PB低位+价格分位低，周期底部反转'
    },
    '回购信号': {
        'class': RepurchaseStrategy,
        'category': '事件驱动',
        'risk': '低',
        'description': '高管增持+低估+高ROE，回购信号'
    },
    '股权激励': {
        'class': EquityIncentiveStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '高ROE+成长+低负债，激励特征'
    },
    '解禁逆向': {
        'class': LockupExpiryStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '超跌+基本面支撑，解禁逆向博弈'
    },
    '龙虎榜跟风': {
        'class': DragonTigerFollowStrategy,
        'category': '资金面',
        'risk': '中高',
        'description': '龙虎榜净买入跟风，资金关注'
    },
    '打板接力': {
        'class': LimitUpRelayStrategy,
        'category': '短线事件',
        'risk': '高',
        'description': '连板接力，情绪周期'
    },
    '次新股': {
        'class': NewStockStrategy,
        'category': '事件驱动',
        'risk': '中高',
        'description': '次新股放量+趋势，波动博弈'
    },
    # 新增4个研究驱动策略v4（基于海外交易者方法论+量化经典书系）
    'AI供应链瓶颈': {
        'class': PerillaChokepointStrategy,
        'category': '产业链选股',
        'risk': '中',
        'description': 'Serenity瓶颈理论，AI供应链关键节点突破+量能放大'
    },
    'SEPA成长股': {
        'class': SEPAGrowthStrategy,
        'category': '成长股选股',
        'risk': '中',
        'description': 'Minervini SEPA，200日线+相对强度RS+基本面高增长'
    },
    '协整配对交易': {
        'class': CointegrationPairsStrategy,
        'category': '统计套利',
        'risk': '中',
        'description': 'Chan配对交易，同行业龙头价差z-score均值回归'
    },
    'Hurst择时动量': {
        'class': HurstTimingStrategy,
        'category': '择时策略',
        'risk': '中',
        'description': 'Hurst指数判断市场状态，动量/均值回归/低波动切换'
    },
    # 新增13个GitHub开源研究策略v5
    # 短线交易类（5个）
    '集合竞价选股': {
        'class': AuctionSelectionStrategy,
        'category': '短线事件',
        'risk': '高',
        'description': '竞价高开+量比，短线持有1-2天'
    },
    '尾盘抢筹': {
        'class': AfterHoursMomentumStrategy,
        'category': '短线事件',
        'risk': '中',
        'description': '黄金两点半异动，尾盘买入次日卖'
    },
    '游资席位跟踪': {
        'class': HotMoneyTrackingStrategy,
        'category': '资金面',
        'risk': '高',
        'description': '知名游资席位净买入跟风'
    },
    '涨停封单': {
        'class': LimitUpSealStrategy,
        'category': '短线事件',
        'risk': '高',
        'description': '封单量>5000万+换手率<5%'
    },
    '跌停撬板': {
        'class': LimitDownReboundStrategy,
        'category': '短线事件',
        'risk': '极高',
        'description': '跌停板博弈反转，高风险'
    },
    # 套利另类类（5个）
    '可转债双低': {
        'class': ConvertibleBondDoubleLowStrategy,
        'category': '套利策略',
        'risk': '低',
        'description': '价格<130元+溢价率<20%'
    },
    '可转债下修博弈': {
        'class': ConvertibleBondDownwardStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '正股跌破回售触发价博弈下修'
    },
    'ETF折溢价套利': {
        'class': ETFPremiumArbitrageStrategy,
        'category': '套利策略',
        'risk': '低',
        'description': '场内价与IOPV偏离套利'
    },
    '网格交易': {
        'class': GridTradingStrategy,
        'category': '另类策略',
        'risk': '中',
        'description': '区间震荡等间距挂单'
    },
    '限售解禁博弈': {
        'class': LockupExpiryArbitrageStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '解禁前逆向博弈利空出尽'
    },
    # 基本面深度类（3个）
    '戴维斯双击': {
        'class': DavisDoubleHitStrategy,
        'category': '成长因子',
        'risk': '中',
        'description': '业绩+估值双提升，低PE高增速'
    },
    '困境反转': {
        'class': TurnaroundStrategy,
        'category': '价值因子',
        'risk': '中',
        'description': '9类指标恢复评分，低估值底部介入'
    },
    '股东户数变化': {
        'class': ShareholderChangeStrategy,
        'category': '事件驱动',
        'risk': '中',
        'description': '户数减少=筹码集中，机构持股提升'
    },
    '筹码分布': {
        'class': ChipDistributionStrategy,
        'category': '技术/筹码',
        'risk': '中',
        'description': '筹码集中度>70%+低位密集+放量突破，捕捉主力建仓'
    },
    # 新增强版质量因子策略（ Piotroski F-Score + Altman Z-Score）
    '质量因子选股Pro': {
        'class': QualityFactorStrategy,
        'category': '质量因子',
        'risk': '低',
        'description': 'F-Score≥7 + Z-Score>2.99，财务优秀+破产风险低，PB最低20%池筛选'
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
