# -*- coding: utf-8 -*-
"""
金融NLP综合模块 - 金融大模型应用集

功能列表：
1. 财报智能解读 - 财务指标提取、异常识别、投资评级
2. 研报摘要生成 - 自动生成研报摘要和关键信息
3. 失败策略分析 - 分析失败原因并给出改进建议
4. 每日报告增强 - 生成投资建议和市场解读
5. 市场情绪监控 - 整体市场情绪分析
6. 公告事件识别 - 识别重大公告事件

使用 HuggingFace Inference API (FinBERT) + LLM
"""

import os
import json
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# HuggingFace Token
HF_TOKEN = '***REMOVED***'
# Groq API Key
GROQ_API_KEY = '***REMOVED***'


# ==================== 辅助函数 ====================

def _get_llm_client():
    """获取 LLM 客户端（优先 Groq，其次 HuggingFace）"""
    # 优先使用 Groq（速度快）
    try:
        from strategy_discovery.groq_client import GroqClient
        client = GroqClient(api_key=GROQ_API_KEY)
        if client.client:
            return client
    except:
        pass
    
    # 备用 HuggingFace
    try:
        from strategy_discovery.hf_client import HuggingFaceClient
        client = HuggingFaceClient(api_token=HF_TOKEN)
        if client.client:
            return client
    except:
        pass
    
    return None


# ==================== 1. 财报智能解读 ====================

class FinancialReportAnalyzer:
    """财报智能解读器
    
    功能：
    - 提取关键财务指标
    - 识别财务异常
    - 生成投资评级
    - 对比行业平均
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._init_llm()

    def _init_llm(self):
        if self.llm is None:
            self.llm = _get_llm_client()
            if not self.llm:
                print("警告: 初始化LLM客户端失败，将使用规则分析")

    def analyze_stock(self, symbol: str) -> Optional[Dict]:
        """分析单只股票的财务状况
        
        Args:
            symbol: 股票代码
        
        Returns:
            dict: 分析结果
        """
        # 获取财务数据
        financial_data = self._get_financial_data(symbol)
        if not financial_data:
            return None

        # 如果有LLM，进行深度分析
        if self.llm:
            return self._llm_analysis(symbol, financial_data)
        
        return self._rule_based_analysis(symbol, financial_data)

    def _get_financial_data(self, symbol: str) -> Dict:
        """获取财务数据"""
        data = {'symbol': symbol}
        
        try:
            # 获取估值数据
            valuation = ak.stock_a_indicator_value(symbol)
            if valuation is not None and not valuation.empty:
                data['valuation'] = valuation.to_dict('records')[0] if len(valuation) > 0 else {}
        except Exception:
            data['valuation'] = {}

        try:
            # 获取财务指标
            financial = ak.stock_financial_analysis_indicator(symbol)
            if financial is not None and not financial.empty:
                latest = financial.tail(4)
                data['financial'] = latest.to_dict('records')
        except Exception:
            data['financial'] = []

        return data

    def _llm_analysis(self, symbol: str, data: Dict) -> Dict:
        """使用LLM进行深度分析"""
        prompt = f"""分析以下股票{symbol}的财务数据，生成投资建议。

## 财务数据
{json.dumps(data, ensure_ascii=False, indent=2)[:2000]}

请输出JSON格式：
{{
    "investment_rating": "强烈推荐/推荐/中性/回避",
    "profitability": "盈利评价（优/良/中/差）",
    "growth": "成长性评价",
    "valuation": "估值评价（高估/合理/低估）",
    "financial_health": "财务健康评价",
    "key_strengths": ["优势1", "优势2"],
    "key_risks": ["风险1", "风险2"],
    "summary": "一句话总结（50字内）"
}}

只输出JSON："""

        response = self.llm.complete(
            prompt,
            system_prompt="你是一个专业的财务分析师，擅长从财报中发现投资机会和风险。",
            temperature=0.3,
            max_tokens=800
        )

        if response:
            import re
            try:
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    result = json.loads(match.group(0))
                    result['symbol'] = symbol
                    result['data_source'] = 'llm'
                    return result
            except:
                pass
        
        return self._rule_based_analysis(symbol, data)

    def _rule_based_analysis(self, symbol: str, data: Dict) -> Dict:
        """基于规则的分析（无LLM时使用）"""
        result = {
            'symbol': symbol,
            'investment_rating': '中性',
            'data_source': 'rule'
        }

        # 简单的规则判断
        try:
            if data.get('financial'):
                latest = data['financial'][0]
                # 可以添加更多规则判断
                result['raw_data'] = latest
        except:
            pass

        return result

    def batch_analyze(self, symbols: List[str]) -> List[Dict]:
        """批量分析多只股票"""
        results = []
        for symbol in symbols:
            try:
                result = self.analyze_stock(symbol)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"分析 {symbol} 失败: {e}")
        return results


# ==================== 2. 研报摘要生成 ====================

class ResearchReportSummarizer:
    """研报摘要生成器
    
    功能：
    - 抓取研报内容
    - 生成摘要
    - 提取关键信息
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._init_llm()

    def _init_llm(self):
        if self.llm is None:
            self.llm = _get_llm_client()

    def get_recent_reports(self, symbol: str = None, days: int = 7) -> List[Dict]:
        """获取近期研报"""
        reports = []
        
        try:
            # 尝试获取研报数据
            report_df = ak.stock_research_report_em(symbol=symbol if symbol else "000001")
            if report_df is not None and not report_df.empty:
                for _, row in report_df.head(20).iterrows():
                    reports.append({
                        'title': row.get('股票简称', ''),
                        'institution': row.get('券商', ''),
                        'rating': row.get('评级', ''),
                        'date': str(row.get('日期', ''))
                    })
        except Exception as e:
            print(f"获取研报失败: {e}")
        
        return reports

    def summarize_report(self, report_content: str) -> Optional[Dict]:
        """生成研报摘要"""
        if not self.llm:
            return {'summary': report_content[:200], 'key_points': []}

        prompt = f"""为以下研报生成摘要和关键信息。

研报内容：
{report_content[:3000]}

请输出JSON格式：
{{
    "summary": "摘要（100字内）",
    "investment_rating": "投资评级",
    "target_price": "目标价（如有）",
    "key_points": ["要点1", "要点2", "要点3"],
    "risks": ["风险点1", "风险点2"]
}}

只输出JSON："""

        response = self.llm.complete(
            prompt,
            system_prompt="你是一个专业的券商分析师，擅长提炼研报核心观点。",
            temperature=0.3,
            max_tokens=600
        )

        if response:
            import re
            try:
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            except:
                pass
        
        return {'summary': report_content[:200], 'key_points': []}


# ==================== 3. 失败策略分析优化 ====================

class StrategyFailureAnalyzer:
    """失败策略分析器
    
    功能：
    - 分析策略失败原因
    - 生成改进建议
    - 优化策略参数
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._init_llm()

    def _init_llm(self):
        if self.llm is None:
            self.llm = _get_llm_client()

    def analyze_failure(self, strategy_info: Dict, backtest_result: Dict) -> Optional[Dict]:
        """分析策略失败原因
        
        Args:
            strategy_info: 策略信息 {name, hypothesis, select_rule, timing_rule}
            backtest_result: 回测结果 {total_return, sharpe, win_rate, max_drawdown}
        
        Returns:
            dict: 改进建议
        """
        if not self.llm:
            return self._rule_based_suggestion(strategy_info, backtest_result)

        prompt = f"""分析以下量化策略失败的原因，并给出具体改进建议。

## 策略信息
名称: {strategy_info.get('name', 'Unknown')}
假设: {strategy_info.get('hypothesis', 'N/A')}
选股规则: {strategy_info.get('select_rule', 'N/A')}
择时规则: {strategy_info.get('timing_rule', 'N/A')}

## 回测结果
总收益: {backtest_result.get('total_return', 'N/A')}%
夏普比率: {backtest_result.get('sharpe', 'N/A')}
胜率: {backtest_result.get('win_rate', 'N/A')}%
最大回撤: {backtest_result.get('max_drawdown', 'N/A')}%
评分: {backtest_result.get('grade', 'N/A')}

## 分析任务
1. 分析策略失败的核心原因
2. 提出2-3个具体的改进方向
3. 针对每个方向给出具体参数调整建议

请输出JSON格式：
{{
    "failure_reasons": ["原因1", "原因2"],
    "improvements": [
        {{
            "direction": "改进方向名称",
            "problem": "当前问题",
            "suggestion": "具体修改建议",
            "expected_impact": "预期效果"
        }}
    ],
    "overall_assessment": "总体评价"
}}

只输出JSON："""

        response = self.llm.complete(
            prompt,
            system_prompt="你是一个专业的量化策略研究员，擅长诊断策略问题并提出改进方案。",
            temperature=0.5,
            max_tokens=1000
        )

        if response:
            import re
            try:
                match = re.search(r'\{.*\}', response, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            except:
                pass
        
        return self._rule_based_suggestion(strategy_info, backtest_result)

    def _rule_based_suggestion(self, strategy_info: Dict, backtest_result: Dict) -> Dict:
        """基于规则的建议（无LLM时使用）"""
        suggestions = []
        
        total_return = backtest_result.get('total_return', 0)
        win_rate = backtest_result.get('win_rate', 0)
        max_drawdown = backtest_result.get('max_drawdown', 0)
        
        if total_return < 0:
            suggestions.append({
                'direction': '收益优化',
                'problem': '总收益为负',
                'suggestion': '考虑收紧止损或调整选股条件',
                'expected_impact': '降低亏损'
            })
        
        if win_rate < 0.4:
            suggestions.append({
                'direction': '胜率提升',
                'problem': '胜率过低',
                'suggestion': '提高选股门槛，增加趋势确认',
                'expected_impact': '提高胜率'
            })
        
        if max_drawdown > 20:
            suggestions.append({
                'direction': '风险控制',
                'problem': '回撤过大',
                'suggestion': '降低单只股票仓位，增加分散度',
                'expected_impact': '降低回撤'
            })
        
        return {
            'failure_reasons': ['基于规则分析'],
            'improvements': suggestions,
            'overall_assessment': '需要人工进一步分析'
        }


# ==================== 4. 每日选股报告增强 ====================

class DailyReportEnhancer:
    """每日选股报告增强器
    
    功能：
    - 生成市场解读
    - 生成投资建议
    - 生成风险提示
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._init_llm()

    def _init_llm(self):
        if self.llm is None:
            self.llm = _get_llm_client()

    def generate_market_insight(self, market_data: Dict) -> str:
        """生成市场洞察"""
        if not self.llm:
            return "市场数据获取中..."

        # 格式化市场数据
        indices_info = ""
        if 'indices' in market_data:
            for name, info in market_data['indices'].items():
                change = info.get('change_pct', 0)
                indices_info += f"- {name}: {info.get('price', 'N/A')} ({'+' if change > 0 else ''}{change:.2f}%)\n"

        prompt = f"""分析当前A股市场状况，生成简短的市场洞察。

## 市场数据
{indices_info}
成交量: {market_data.get('volume', 'N/A')}
北向资金: {market_data.get('north_flow', 'N/A')}

## 要求
1. 判断当前市场状态（上涨/下跌/震荡）
2. 识别主要驱动因素
3. 给出操作建议

直接输出150字以内的市场洞察，不要JSON："""

        response = self.llm.complete(
            prompt,
            system_prompt="你是一个专业的A股市场分析师，擅长判断市场趋势。",
            temperature=0.5,
            max_tokens=400
        )

        return response or "市场分析生成失败"

    def generate_stock_recommendation(self, stock: Dict, market_context: str) -> str:
        """生成个股推荐理由"""
        if not self.llm:
            return stock.get('reason', '')

        prompt = f"""为以下股票生成简洁的推荐理由。

股票: {stock.get('name', stock.get('symbol'))}({stock.get('symbol')})
选股原因: {stock.get('reason', 'N/A')}

当前市场: {market_context}

请输出80字以内的推荐理由，直接输出文字："""

        response = self.llm.complete(
            prompt,
            system_prompt="你是一个专业的投资顾问，擅长撰写简洁的投资建议。",
            temperature=0.5,
            max_tokens=200
        )

        return response or stock.get('reason', '')

    def generate_risk_warning(self, selected_stocks: List[Dict]) -> str:
        """生成风险提示"""
        if not self.llm:
            return "市场有风险，投资需谨慎。"

        stocks_info = "\n".join([
            f"- {s.get('name', s['symbol'])}: {s.get('reason', '')[:30]}..."
            for s in selected_stocks[:5]
        ])

        prompt = f"""根据以下选股结果，生成风险提示。

选股：
{stocks_info}

请输出100字以内的风险提示，直接输出文字："""

        response = self.llm.complete(
            prompt,
            system_prompt="你是一个专业的风险分析师，擅长识别投资风险。",
            temperature=0.3,
            max_tokens=250
        )

        return response or "注意控制仓位，分散投资。"


# ==================== 5. 市场情绪监控 ====================

class MarketSentimentMonitor:
    """市场情绪监控器
    
    功能：
    - 监控整体市场情绪
    - 分析资金流向
    - 预警极端情绪
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._finbert_client = None
        self._init_llm()

    def _init_llm(self):
        if self.llm is None:
            try:
                from strategy_discovery.hf_client import HuggingFaceClient
                self.llm = HuggingFaceClient(api_token=HF_TOKEN)
            except:
                pass

        # FinBERT 客户端
        try:
            from huggingface_hub import InferenceClient
            self._finbert_client = InferenceClient(token=HF_TOKEN)
        except:
            pass

    def get_market_sentiment(self) -> Dict:
        """获取整体市场情绪"""
        sentiment_data = {
            'news_sentiment': self._analyze_news_sentiment(),
            'fund_flow': self._get_fund_flow(),
            'market_status': self._get_market_status(),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 综合评分
        sentiment_data['overall_sentiment'] = self._calculate_overall_sentiment(sentiment_data)
        
        return sentiment_data

    def _analyze_news_sentiment(self) -> Dict:
        """分析新闻情绪"""
        try:
            news_df = ak.stock_news_em()
            if news_df is None or news_df.empty:
                return {'sentiment': 'neutral', 'score': 0}

            # 使用 FinBERT 分析
            if self._finbert_client:
                sentiments = []
                for _, row in news_df.head(20).iterrows():
                    try:
                        title = str(row.get('新闻标题', ''))
                        response = self._finbert_client.text_classification(
                            text=title,
                            model="ProsusAI/finbert"
                        )
                        if response:
                            top = sorted(response, key=lambda x: x['score'], reverse=True)[0]
                            if top['label'] == 'positive':
                                sentiments.append(top['score'])
                            elif top['label'] == 'negative':
                                sentiments.append(-top['score'])
                    except:
                        continue
                
                if sentiments:
                    avg_score = sum(sentiments) / len(sentiments)
                    return {
                        'sentiment': 'bullish' if avg_score > 0.2 else 'bearish' if avg_score < -0.2 else 'neutral',
                        'score': round(avg_score, 3),
                        'news_count': len(sentiments)
                    }
            
            # 备用：关键词分析
            return self._keyword_sentiment_analysis(news_df)
            
        except Exception as e:
            print(f"新闻情绪分析失败: {e}")
            return {'sentiment': 'neutral', 'score': 0}

    def _keyword_sentiment_analysis(self, news_df) -> Dict:
        """基于关键词的情绪分析"""
        positive_keywords = ['增长', '突破', '创新', '合作', '业绩', '利好']
        negative_keywords = ['下降', '风险', '危机', '亏损', '利空']
        
        pos_count = 0
        neg_count = 0
        
        for _, row in news_df.head(30).iterrows():
            text = f"{row.get('新闻标题', '')} {row.get('新闻内容', '')}"
            pos_count += sum(1 for k in positive_keywords if k in text)
            neg_count += sum(1 for k in negative_keywords if k in text)
        
        total = pos_count + neg_count
        if total == 0:
            return {'sentiment': 'neutral', 'score': 0}
        
        score = (pos_count - neg_count) / total
        return {
            'sentiment': 'bullish' if score > 0.1 else 'bearish' if score < -0.1 else 'neutral',
            'score': round(score, 3),
            'positive': pos_count,
            'negative': neg_count
        }

    def _get_fund_flow(self) -> Dict:
        """获取资金流向"""
        try:
            # 北向资金
            north_df = ak.stock_em_hsgt_north_net_flow_in(indicator="沪深港通北向资金净买入")
            if north_df is not None and not north_df.empty:
                latest = north_df.tail(1).iloc[0]
                return {
                    'north_flow': float(latest.get('今日北向资金净买入', 0)),
                    'unit': '亿元'
                }
        except:
            pass
        
        return {'north_flow': 0, 'unit': '亿元'}

    def _get_market_status(self) -> Dict:
        """获取市场状态"""
        try:
            indices = ak.stock_zh_index_spot_em()
            if indices is not None and not indices.empty:
                # 简化处理
                return {'status': '正常交易', 'index_count': len(indices)}
        except:
            pass
        
        return {'status': '未知', 'index_count': 0}

    def _calculate_overall_sentiment(self, data: Dict) -> Dict:
        """计算综合情绪"""
        score = 0
        weights = {'news': 0.4, 'fund': 0.3, 'market': 0.3}
        
        # 新闻情绪
        news_score = data.get('news_sentiment', {}).get('score', 0)
        score += news_score * weights['news']
        
        # 资金情绪
        north_flow = data.get('fund_flow', {}).get('north_flow', 0)
        fund_score = 1 if north_flow > 50 else -1 if north_flow < -50 else 0
        score += fund_score * weights['fund']
        
        return {
            'score': round(score, 3),
            'label': '乐观' if score > 0.2 else '悲观' if score < -0.2 else '中性',
            'action': '可以加仓' if score > 0.3 else '控制仓位' if score < -0.3 else '观望'
        }


# ==================== 6. 公告事件识别 ====================

class AnnouncementEventDetector:
    """公告事件识别器
    
    功能：
    - 识别重大公告
    - 分类事件类型
    - 评估事件影响
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._init_llm()
        
        # 事件类型关键词
        self.event_keywords = {
            '业绩': ['业绩预告', '业绩快报', '年报', '季报', '净利润'],
            '并购': ['收购', '并购', '重组', '定增', '发行股份'],
            '股权': ['股权激励', '增持', '减持', '回购', '解禁'],
            '合作': ['签约', '合作', '战略', '协议', '中标'],
            '高管': ['辞职', '任命', '换届', '高管'],
            '风险': ['警示', '调查', '处罚', '诉讼', '违规']
        }

    def _init_llm(self):
        if self.llm is None:
            try:
                from strategy_discovery.hf_client import HuggingFaceClient
                self.llm = HuggingFaceClient(api_token=HF_TOKEN)
            except:
                pass

    def detect_events(self, symbol: str = None, days: int = 3) -> List[Dict]:
        """检测重大公告事件
        
        Args:
            symbol: 股票代码，None表示全市场
            days: 回溯天数
        
        Returns:
            list: 事件列表
        """
        events = []
        
        try:
            # 获取公告数据
            if symbol:
                # 个股公告
                news_df = ak.stock_news_em()
                if news_df is not None:
                    news_df = news_df[news_df['关键词'] == symbol]
            else:
                # 全市场新闻
                news_df = ak.stock_news_em()
            
            if news_df is None or news_df.empty:
                return events

            # 分析每条新闻
            for _, row in news_df.head(50).iterrows():
                event = self._analyze_announcement(row)
                if event:
                    events.append(event)
            
            # 按重要性排序
            events.sort(key=lambda x: x.get('importance', 0), reverse=True)
            
        except Exception as e:
            print(f"检测公告事件失败: {e}")
        
        return events[:20]

    def _analyze_announcement(self, row: pd.Series) -> Optional[Dict]:
        """分析单条公告"""
        title = str(row.get('新闻标题', ''))
        content = str(row.get('新闻内容', ''))[:500] if row.get('新闻内容') else ''
        keyword = str(row.get('关键词', ''))
        source = str(row.get('文章来源', ''))
        publish_time = str(row.get('发布时间', ''))
        
        full_text = f"{title} {content}"
        
        # 识别事件类型
        event_types = []
        for event_type, keywords in self.event_keywords.items():
            if any(k in full_text for k in keywords):
                event_types.append(event_type)
        
        if not event_types:
            return None
        
        # 评估重要性
        importance = self._assess_importance(full_text, event_types)
        
        # 评估影响
        impact = self._assess_impact(full_text, event_types)
        
        return {
            'symbol': keyword,
            'title': title,
            'content': content[:200],
            'source': source,
            'publish_time': publish_time,
            'event_types': event_types,
            'importance': importance,
            'impact': impact  # positive/negative/neutral
        }

    def _assess_importance(self, text: str, event_types: List[str]) -> int:
        """评估事件重要性"""
        importance = len(event_types) * 10  # 事件类型越多越重要
        
        # 关键词加成
        high_impact_keywords = ['重大', '首次', '创历史', '超预期', '突破性']
        for keyword in high_impact_keywords:
            if keyword in text:
                importance += 20
        
        return min(importance, 100)

    def _assess_impact(self, text: str, event_types: List[str]) -> str:
        """评估事件影响"""
        positive_indicators = ['增长', '盈利', '突破', '合作', '中标', '增持', '回购']
        negative_indicators = ['下降', '亏损', '减持', '处罚', '调查', '风险', '诉讼']
        
        pos_count = sum(1 for k in positive_indicators if k in text)
        neg_count = sum(1 for k in negative_indicators if k in text)
        
        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        else:
            return 'neutral'


# ==================== 便捷函数 ====================

def create_financial_analyzer() -> FinancialReportAnalyzer:
    """创建财报分析器"""
    return FinancialReportAnalyzer()


def create_report_summarizer() -> ResearchReportSummarizer:
    """创建研报摘要器"""
    return ResearchReportSummarizer()


def create_strategy_analyzer() -> StrategyFailureAnalyzer:
    """创建策略失败分析器"""
    return StrategyFailureAnalyzer()


def create_report_enhancer() -> DailyReportEnhancer:
    """创建报告增强器"""
    return DailyReportEnhancer()


def create_sentiment_monitor() -> MarketSentimentMonitor:
    """创建情绪监控器"""
    return MarketSentimentMonitor()


def create_event_detector() -> AnnouncementEventDetector:
    """创建事件检测器"""
    return AnnouncementEventDetector()


# ==================== 测试代码 ====================

if __name__ == "__main__":
    print("=" * 60)
    print("金融NLP模块测试")
    print("=" * 60)

    # 1. 测试市场情绪监控
    print("\n[1] 市场情绪监控")
    monitor = create_sentiment_monitor()
    sentiment = monitor.get_market_sentiment()
    print(f"整体情绪: {sentiment['overall_sentiment']['label']}")
    print(f"操作建议: {sentiment['overall_sentiment']['action']}")
    print(f"新闻情绪: {sentiment['news_sentiment']}")

    # 2. 测试公告事件检测
    print("\n[2] 公告事件检测")
    detector = create_event_detector()
    events = detector.detect_events(days=3)
    print(f"检测到 {len(events)} 个重大事件:")
    for e in events[:3]:
        print(f"  - {e['symbol']}: {e['title'][:30]}... ({','.join(e['event_types'])})")

    # 3. 测试策略失败分析
    print("\n[3] 策略失败分析")
    analyzer = create_strategy_analyzer()
    strategy_info = {
        'name': '测试策略',
        'hypothesis': '低PE股票有超额收益',
        'select_rule': 'PE<10',
        'timing_rule': '金叉买入'
    }
    backtest_result = {
        'total_return': -5.2,
        'sharpe': 0.3,
        'win_rate': 0.35,
        'max_drawdown': 15
    }
    suggestion = analyzer.analyze_failure(strategy_info, backtest_result)
    if suggestion:
        print(f"失败原因: {suggestion.get('failure_reasons', [])[:2]}")
        print(f"改进方向: {[i['direction'] for i in suggestion.get('improvements', [])[:2]]}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
