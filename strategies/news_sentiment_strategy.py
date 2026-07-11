# -*- coding: utf-8 -*-
"""
新闻情感选股策略（中文优化版）
使用关键词匹配 + 规则判断筛选利好股票

使用方法：
    from strategies.news_sentiment_strategy import NewsSentimentStrategy
    strategy = NewsSentimentStrategy()
    results = strategy.detect_events(helper)
"""

import pandas as pd
import numpy as np
import akshare as ak
from strategies.base import EventStrategy


class NewsSentimentStrategy(EventStrategy):
    """新闻情感选股策略
    
    通过关键词分析财经新闻，筛选：
    1. 正面新闻集中的股票
    2. 近期有重大利好公告的股票
    
    注意：FinBERT 对中文支持有限，使用规则+关键词判断
    """

    def __init__(self):
        super().__init__("新闻情感", "事件驱动")
        
        # FinBERT 客户端（用于英文或中英混合新闻）
        self._client = None
        
        # 正面关键词
        self.positive_keywords = [
            '增长', '盈利', '突破', '签约', '合作', '上调', '超预期', '创新高',
            '利润', '大增', '扭亏', '首板', '涨停', '强势', '看好', '推荐买入',
            '增持', '买入', '评级', '目标价', '业绩', '订单', '中标', '签约',
            '扩产', '投产', '量产', '发布', '新品', '技术突破', '市场份额',
            '出口', '海外', '布局', '扩张', '战略', '转型', '降本', '提效'
        ]
        
        # 负面关键词
        self.negative_keywords = [
            '下降', '亏损', '风险', '下调', '低于预期', '危机', '诉讼', '减持',
            '卖出', '警告', '警示', '处罚', '整改', '违规', '调查', '业绩下滑',
            '债务', '违约', '破产', '裁员', '关停', '停产', '召回', '造假',
            '暴雷', 'ST', '*ST', '退市', '商誉', '减值', '诉讼', '索赔'
        ]

    @property
    def client(self):
        """延迟加载 HuggingFace 客户端"""
        if self._client is None:
            try:
                from strategy_discovery.hf_client import HuggingFaceClient
                self._client = HuggingFaceClient(api_token='***REMOVED***')
            except Exception as e:
                print(f"初始化 HuggingFace 客户端失败: {e}")
                self._client = None
        return self._client

    def get_description(self):
        return "基于新闻关键词分析，筛选利好股票"

    def detect_events(self, helper, date=None):
        """检测正面新闻集中的股票"""
        results = []
        
        # 获取今日财经新闻
        try:
            news_df = ak.stock_news_em()
        except Exception as e:
            print(f"获取新闻失败: {e}")
            return results
        
        if news_df is None or news_df.empty:
            return results
        
        # 分析每条新闻
        analyzed_news = []
        
        for _, row in news_df.head(50).iterrows():
            try:
                keyword = str(row.get('关键词', '')).strip()
                title = str(row.get('新闻标题', ''))
                content = str(row.get('新闻内容', ''))[:500] if row.get('新闻内容') else ''
                source = str(row.get('文章来源', ''))
                publish_time = str(row.get('发布时间', ''))
                
                # 合并标题和内容
                full_text = f"{title} {content}"
                
                # 计算情感分数
                pos_count = sum(1 for k in self.positive_keywords if k in full_text)
                neg_count = sum(1 for k in self.negative_keywords if k in full_text)
                
                # 使用 FinBERT 分析英文或中英混合内容
                finbert_score = None
                if self.client and len(full_text) > 20:
                    # 只对包含英文的文本使用 FinBERT
                    if any(c.isascii() for c in full_text):
                        try:
                            result = self.client.analyze_financial_news(full_text)
                            if result:
                                finbert_score = result['sentiment_score']
                        except:
                            pass
                
                # 综合评分
                if pos_count > neg_count:
                    # 正面新闻
                    sentiment = 'positive'
                    score = (pos_count - neg_count) / max(pos_count + neg_count, 1)
                    
                    # 如果 FinBERT 有结果，综合两者
                    if finbert_score is not None:
                        score = (score + finbert_score) / 2
                    
                    if score > 0.2:  # 阈值
                        analyzed_news.append({
                            'keyword': keyword,
                            'title': title,
                            'content': content[:100],
                            'source': source,
                            'publish_time': publish_time,
                            'sentiment': sentiment,
                            'score': score,
                            'pos_count': pos_count,
                            'neg_count': neg_count,
                            'finbert_score': finbert_score
                        })
                elif neg_count > pos_count:
                    # 负面新闻
                    sentiment = 'negative'
                    score = -(neg_count - pos_count) / max(pos_count + neg_count, 1)
                    
                    if finbert_score is not None:
                        score = (score + finbert_score) / 2
                
            except Exception as e:
                continue
        
        # 按分数排序，取正面新闻
        analyzed_news.sort(key=lambda x: x['score'], reverse=True)
        
        # 获取股票名称（如果关键词是股票代码）
        for news in analyzed_news[:10]:
            try:
                keyword = news['keyword']
                
                # 尝试获取股票信息
                quote = helper.get_realtime_quote(keyword)
                if quote and quote.get('名称'):
                    name = quote.get('名称')
                    symbol = keyword
                else:
                    name = keyword
                    symbol = keyword
                
                reason = (f"利好: {news['title'][:30]}... | "
                          f"正面词:{news['pos_count']}个 "
                          f"情感分:{news['score']:.2f}")
                
                if news.get('finbert_score') is not None:
                    reason += f" (FinBERT:{news['finbert_score']:.2f})"
                
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': reason,
                    'title': news['title'],
                    'source': news['source'],
                    'publish_time': news['publish_time'],
                    'score': news['score']
                })
                
            except Exception:
                results.append({
                    'symbol': news['keyword'],
                    'name': news['keyword'],
                    'reason': f"利好: {news['title'][:30]}... 情感分:{news['score']:.2f}"
                })
        
        return results


class HotNewsTrackingStrategy(EventStrategy):
    """热点新闻追踪策略
    
    追踪市场热点新闻，关注：
    1. 近期热点概念相关股票
    2. 有重大公告的股票
    3. 新闻热度高的股票
    """

    def __init__(self):
        super().__init__("热点新闻", "事件驱动")
        
        self.hot_concepts = [
            'AI', '人工智能', '新能源', '锂电池', '储能', '光伏', '半导体',
            '芯片', '算力', '大模型', '机器人', '智能驾驶', '无人驾驶',
            '医疗', '创新药', '中药', '医疗器械', '消费', '食品', '白酒',
            '地产', '基建', '银行', '保险', '证券', '军工', '航空'
        ]

    def get_description(self):
        return "追踪热点新闻，筛选概念相关股票"

    def detect_events(self, helper, date=None):
        """检测热点新闻相关股票"""
        results = []
        
        try:
            news_df = ak.stock_news_em()
        except Exception as e:
            print(f"获取新闻失败: {e}")
            return results
        
        if news_df is None or news_df.empty:
            return results
        
        # 寻找热点新闻
        hot_news = []
        
        for _, row in news_df.head(30).iterrows():
            try:
                title = str(row.get('新闻标题', ''))
                content = str(row.get('新闻内容', ''))[:200] if row.get('新闻内容') else ''
                keyword = str(row.get('关键词', ''))
                
                full_text = f"{title} {content}"
                
                # 检查是否涉及热点概念
                concepts = [c for c in self.hot_concepts if c in full_text]
                
                if concepts:
                    hot_news.append({
                        'keyword': keyword,
                        'title': title,
                        'content': content[:100],
                        'concepts': concepts,
                        'has_positive': any(k in full_text for k in ['增长', '突破', '签约', '合作', '业绩'])
                    })
                    
            except Exception:
                continue
        
        # 获取股票名称
        for news in hot_news[:8]:
            try:
                keyword = news['keyword']
                quote = helper.get_realtime_quote(keyword)
                if quote and quote.get('名称'):
                    name = quote.get('名称')
                    symbol = keyword
                else:
                    name = keyword
                    symbol = keyword
                
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'reason': f"热点: {','.join(news['concepts'][:2])} | {news['title'][:25]}...",
                    'concepts': news['concepts'],
                    'has_positive': news['has_positive']
                })
                
            except Exception:
                continue
        
        return results


if __name__ == "__main__":
    # 测试策略
    from data.akshare_helper import AKShareHelper
    
    print("=" * 60)
    print("测试新闻选股策略")
    print("=" * 60)
    
    helper = AKShareHelper()
    
    # 测试新闻情感策略
    print("\n[1] 新闻情感策略")
    strategy = NewsSentimentStrategy()
    results = strategy.detect_events(helper)
    print(f"选出 {len(results)} 只股票:")
    for r in results[:5]:
        print(f"  {r.get('name', r['symbol'])}({r['symbol']}): {r.get('reason', '')[:60]}")
    
    # 测试热点新闻策略
    print("\n[2] 热点新闻策略")
    strategy2 = HotNewsTrackingStrategy()
    results2 = strategy2.detect_events(helper)
    print(f"选出 {len(results2)} 只股票:")
    for r in results2[:5]:
        print(f"  {r.get('name', r['symbol'])}({r['symbol']}): {r.get('reason', '')[:60]}")
