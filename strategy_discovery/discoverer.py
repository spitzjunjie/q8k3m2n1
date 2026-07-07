# -*- coding: utf-8 -*-
"""
LLM驱动策略发现器
基于论文笔记（Alpha-R1、QuantEvolve、Automate-Strategy-Finding-with-LLM）
建立"假设生成→代码生成→回测验证→自动上线"流水线

使用方式：
    from strategy_discovery import StrategyDiscoverer, MarketAnalyzer

    # 1. 准备LLM client（任何实现 complete(prompt) -> str 接口的对象）
    class MyLLMClient:
        def complete(self, prompt):
            # 调用GLM/DeepSeek/OpenAI API
            return response_text

    # 2. 运行策略发现
    discoverer = StrategyDiscoverer(MyLLMClient())
    result = discoverer.discover()
    if result['status'] == 'accepted':
        print("新策略已通过验证！")
        print(result['code'])
"""

import os
import sys
import json
import re
import tempfile
import importlib.util
from datetime import datetime

from data.akshare_helper import AKShareHelper
from .market_analyzer import MarketAnalyzer


# 已有策略列表（用于LLM避免重复）
EXISTING_STRATEGIES = """ROE/盈利增长/营收增长/低PE/低PB/PSR/低估值/现金流质量/高ROIC/低负债/
高股息/股息低波/动量反转/趋势动量/北向重仓/机构持仓/
首板回调/ST摘帽/高管增持/业绩超预期/分析师上调/北向跟投/
量价突破/MACD金叉/KDJ超卖/RSI反转/动量突破/
AI供应链/国产替代/均线多头/多周期共振/多因子综合/ML多因子合成"""


class StrategyDiscoverer:
    """LLM驱动策略发现器

    流程：
    1. 分析市场环境 → 为LLM提供上下文
    2. LLM生成策略假设（基于论文+市场环境+已有策略）
    3. LLM将假设转换为Python策略代码
    4. 动态加载代码并历史回测验证
    5. 评估回测结果，A级以上则接受
    """

    def __init__(self, llm_client, helper=None):
        """
        Args:
            llm_client: LLM客户端，必须实现 complete(prompt) -> str 方法
            helper: AKShareHelper实例（可选，默认创建）
        """
        self.llm = llm_client
        self.helper = helper or AKShareHelper()
        self.market_analyzer = MarketAnalyzer()

    def discover(self, market_context=None, backtest_days=30):
        """完整策略发现流程

        Args:
            market_context: 市场环境描述（None则自动分析）
            backtest_days: 回测验证天数

        Returns:
            dict: {
                'status': 'accepted'/'rejected'/'error',
                'hypothesis': 策略假设,
                'code': 策略代码,
                'backtest_result': 回测结果,
                'reason': 原因说明
            }
        """
        print("=" * 60)
        print("LLM策略发现流水线")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        try:
            # 1. 分析市场环境
            if market_context is None:
                print("\n[1/5] 分析市场环境...")
                market_context = self.market_analyzer.analyze(self.helper)
                print(f"市场环境:\n{market_context[:200]}...")

            # 2. 生成策略假设
            print("\n[2/5] LLM生成策略假设...")
            hypothesis = self._generate_hypothesis(market_context)
            if not hypothesis:
                return {'status': 'error', 'reason': 'LLM生成假设失败'}
            print(f"策略假设: {hypothesis.get('name', 'Unknown')}")

            # 3. 生成策略代码
            print("\n[3/5] LLM生成策略代码...")
            code = self._generate_code(hypothesis)
            if not code:
                return {'status': 'error', 'reason': 'LLM生成代码失败'}
            print(f"代码长度: {len(code)} 字符")

            # 4. 历史回测验证
            print("\n[4/5] 历史回测验证...")
            backtest_result = self._backtest_strategy(code, hypothesis.get('name', 'LLM策略'), backtest_days)
            if not backtest_result:
                return {
                    'status': 'error',
                    'hypothesis': hypothesis,
                    'code': code,
                    'reason': '回测失败'
                }

            # 5. 评估
            print("\n[5/5] 评估回测结果...")
            from evaluation import StrategyEvaluator
            evaluator = StrategyEvaluator()
            evaluation = evaluator.evaluate(backtest_result)
            print(f"综合分: {evaluation['composite_score']}, 等级: {evaluation['grade']}")

            if evaluation['composite_score'] >= 50:  # B级以上接受
                return {
                    'status': 'accepted',
                    'hypothesis': hypothesis,
                    'code': code,
                    'backtest_result': backtest_result,
                    'evaluation': evaluation,
                    'reason': f"综合分{evaluation['composite_score']}，等级{evaluation['grade']}"
                }
            else:
                return {
                    'status': 'rejected',
                    'hypothesis': hypothesis,
                    'code': code,
                    'backtest_result': backtest_result,
                    'evaluation': evaluation,
                    'reason': f"综合分{evaluation['composite_score']}，未达B级(50)"
                }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'reason': str(e)}

    def _generate_hypothesis(self, market_context):
        """LLM生成策略假设

        Returns:
            dict: {'name', 'hypothesis', 'select_rule', 'timing_rule'}
        """
        prompt = f"""你是A股量化策略研究员。基于以下信息提出一个新策略假设。

## 当前市场环境
{market_context}

## 已有策略（避免重复）
{EXISTING_STRATEGIES}

## 论文参考
- Alpha-R1: 强化学习筛选Alpha因子
- QuantEvolve: 多Agent进化框架，质量-多样性优化，产生适应市场风格切换的多元化策略
- LLM自动策略发现: 假设驱动+代码生成+回测验证

## A股特性
- T+1交易（当日买入次日才能卖出）
- 涨跌停限制（主板±10%，创业板/科创板±20%）
- 行业轮动明显
- 北向资金影响大

## 要求
1. 提出与现有策略不同的假设
2. 说明逻辑（为什么这个因子/事件能预测收益）
3. 给出可量化的选股规则
4. 给出择时规则（何时买何时卖）

输出严格的JSON格式（不要其他文字）：
{{
  "name": "策略名（4-6字）",
  "category": "类别（如：因子/事件/趋势/ML）",
  "hypothesis": "策略假设描述",
  "select_rule": "选股规则（具体量化条件）",
  "timing_rule": "择时规则（买卖时机）"
}}
"""
        response = self.llm.complete(prompt)
        if not response:
            return None

        # 解析JSON
        try:
            # 尝试直接解析
            hypothesis = json.loads(response)
            return hypothesis
        except json.JSONDecodeError:
            # 尝试从markdown代码块中提取
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            # 尝试提取第一个{...}块
            brace_match = re.search(r'\{.*\}', response, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass
            print(f"警告: 无法解析LLM输出的JSON: {response[:200]}")
            return None

    def _generate_code(self, hypothesis):
        """LLM将假设转换为Python策略代码

        Returns:
            str: Python代码字符串
        """
        prompt = f"""将以下策略假设转换为可运行的Python代码。

## 策略假设
{json.dumps(hypothesis, ensure_ascii=False, indent=2)}

## 模板（必须遵循此结构）
```python
# -*- coding: utf-8 -*-
from strategies.base import EventStrategy  # 或 FactorStrategy

class XxxStrategy(EventStrategy):
    def __init__(self):
        super().__init__("策略名", "类别")

    def get_description(self):
        return "策略描述"

    def detect_events(self, helper, date=None):
        symbols = helper.get_stock_pool("hs300")[:80]
        results = []
        for sym in symbols:
            try:
                # 策略逻辑
                kline = helper.get_history_kline(sym, days=30, end_date=date)
                if kline.empty or len(kline) < 20:
                    continue
                # 示例条件
                if 条件:
                    results.append({{
                        'symbol': sym, 'name': sym,
                        'reason': '原因说明'
                    }})
                if len(results) >= 10:
                    break
            except:
                continue
        return results
```

## 可用数据方法
- helper.get_history_kline(symbol, days=60, end_date=None) - K线数据，返回DataFrame[date,open,close,high,low,volume]
- helper.get_financial_indicator(symbol) - 财务指标，返回dict[roe, roic, debt_ratio, gross_margin, net_margin]
- helper.get_valuation_data(symbol) - 估值数据，返回dict[pe, pe_ttm, pb, ps, dv_ratio, total_mv]
- helper.get_growth_data(symbol) - 成长数据，返回dict[profit_growth, revenue_growth]
- helper.get_cash_flow(symbol) - 现金流，返回dict[operating_cf, net_profit, cf_quality]
- helper.get_north_holding(symbol) - 北向持股，返回dict[hold_ratio, hold_market_value]
- helper.get_analyst_rating(symbol) - 分析师评级，返回dict[rating, target_price, institution]
- helper.get_executive_trading() - 高管增减持，返回DataFrame
- helper.get_limit_up_list(date) - 涨停板列表，返回DataFrame
- helper.get_stock_pool(pool="hs300") - 股票池，返回list[code]

## 要求
1. 类名必须以Strategy结尾
2. 必须实现 __init__, get_description, detect_events（或calculate_factor）
3. 选股数量限制在10只以内
4. 必须处理异常（try-except）
5. 只输出Python代码，不要其他文字

输出Python代码：
"""
        response = self.llm.complete(prompt)
        if not response:
            return None

        # 提取代码块
        code_match = re.search(r'```(?:python)?\s*(.*?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1)
        # 如果没有代码块，假设整个响应就是代码
        return response

    def _backtest_strategy(self, code, strategy_name, backtest_days=30):
        """动态加载策略代码并回测

        Args:
            code: Python代码字符串
            strategy_name: 策略名（用于日志）
            backtest_days: 回测天数

        Returns:
            dict: 策略回测结果
        """
        # 写入临时文件
        temp_dir = "data/candidate"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = os.path.join(temp_dir, f"candidate_{int(datetime.now().timestamp())}.py")

        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(code)

            # 动态加载模块
            spec = importlib.util.spec_from_file_location("candidate_strategy", temp_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找Strategy类
            strategy_class = None
            for name in dir(module):
                obj = getattr(module, name)
                if (isinstance(obj, type) and name.endswith('Strategy')
                        and obj.__module__ == module.__name__):
                    strategy_class = obj
                    break

            if not strategy_class:
                print("错误：代码中未找到Strategy类")
                return None

            # 实例化策略
            strategy = strategy_class()
            print(f"加载策略: {strategy.name}")

            # 历史回测
            from backtest_history import run_strategy_on_date
            from timing.timing import TimingEngine
            from trading.simulator import TradingSimulator

            timing = TimingEngine()
            trading_dates = self.helper.get_trading_dates(n=backtest_days)

            if not trading_dates:
                print("获取交易日失败")
                return None

            print(f"回测区间: {trading_dates[0]} ~ {trading_dates[-1]}")

            # 逐日运行
            for date in trading_dates:
                run_strategy_on_date(strategy, self.helper, timing, date)

            # 获取最终价格
            last_date = trading_dates[-1]
            prices = {}
            for h in strategy.holdings:
                try:
                    df = self.helper.get_history_kline(h['symbol'], days=5, end_date=last_date)
                    if not df.empty:
                        prices[h['symbol']] = df['close'].iloc[-1]
                except Exception:
                    continue

            result = strategy.to_dict(prices)
            result['backtest_start'] = trading_dates[0]
            result['backtest_end'] = trading_dates[-1]
            result['backtest_days'] = len(trading_dates)
            return result

        except Exception as e:
            print(f"回测失败: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # 清理临时文件
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def save_accepted_strategy(self, result, output_dir="strategies/candidate"):
        """保存已接受的策略代码

        Args:
            result: discover()返回的结果
            output_dir: 输出目录
        """
        if result.get('status') != 'accepted':
            return False

        os.makedirs(output_dir, exist_ok=True)
        hypothesis = result.get('hypothesis', {})
        name = hypothesis.get('name', 'unknown')

        # 保存代码
        code_file = os.path.join(output_dir, f"{name}.py")
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(result['code'])

        # 保存元数据
        meta = {
            'name': name,
            'category': hypothesis.get('category', ''),
            'hypothesis': hypothesis,
            'evaluation': result.get('evaluation', {}),
            'created_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        meta_file = os.path.join(output_dir, f"{name}.json")
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"策略已保存: {code_file}")
        return True


# === LLM Client 示例实现 ===

class GLMClient:
    """智谱GLM API客户端示例

    使用前需要设置环境变量 ZHIPU_API_KEY
    安装: pip install zhipuai
    """

    def __init__(self, api_key=None, model="glm-4"):
        self.api_key = api_key or os.environ.get('ZHIPU_API_KEY')
        self.model = model
        if not self.api_key:
            print("警告: 未设置ZHIPU_API_KEY环境变量")

    def complete(self, prompt):
        """调用GLM API"""
        try:
            from zhipuai import ZhipuAI
            client = ZhipuAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except ImportError:
            print("错误: 未安装zhipuai，请运行 pip install zhipuai")
            return None
        except Exception as e:
            print(f"GLM API调用失败: {e}")
            return None


class DeepSeekClient:
    """DeepSeek API客户端示例

    使用前需要设置环境变量 DEEPSEEK_API_KEY
    安装: pip install openai
    """

    def __init__(self, api_key=None, model="deepseek-chat"):
        self.api_key = api_key or os.environ.get('DEEPSEEK_API_KEY')
        self.model = model

    def complete(self, prompt):
        """调用DeepSeek API"""
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"DeepSeek API调用失败: {e}")
            return None


if __name__ == "__main__":
    # 使用示例
    print("LLM策略发现器使用示例：")
    print()
    print("方式1: 使用智谱GLM")
    print("  export ZHIPU_API_KEY=your_key")
    print("  from strategy_discovery import StrategyDiscoverer, GLMClient")
    print("  discoverer = StrategyDiscoverer(GLMClient())")
    print("  result = discoverer.discover()")
    print()
    print("方式2: 使用DeepSeek")
    print("  export DEEPSEEK_API_KEY=your_key")
    print("  from strategy_discovery import StrategyDiscoverer, DeepSeekClient")
    print("  discoverer = StrategyDiscoverer(DeepSeekClient())")
    print("  result = discoverer.discover()")
    print()
    print("方式3: 使用自定义LLM client")
    print("  class MyClient:")
    print("      def complete(self, prompt):")
    print("          # 调用你的API")
    print("          return response_text")
    print("  discoverer = StrategyDiscoverer(MyClient())")
    print("  result = discoverer.discover()")
