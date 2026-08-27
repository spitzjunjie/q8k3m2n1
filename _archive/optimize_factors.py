# -*- coding: utf-8 -*-
"""
因子有效性分析 - 使用XGBoost找出最有效的因子组合
"""

import pandas as pd
import numpy as np
from data.akshare_helper import AKShareHelper
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
import json

def analyze_factor_effectiveness():
    """分析各因子的有效性"""
    helper = AKShareHelper()
    
    # 获取沪深300成分股
    stocks = helper.get_stock_pool("hs300")[:50]
    
    # 收集因子数据
    data = []
    for sym in stocks:
        try:
            # 获取各类因子
            kline = helper.get_history_kline(sym, days=90)
            if kline is None or len(kline) < 60:
                continue
            
            val = helper.get_valuation_data(sym)
            fin = helper.get_financial_indicator(sym)
            growth = helper.get_growth_data(sym)
            north = helper.get_north_holding(sym)
            
            # 计算技术指标
            ma5 = kline['close'].rolling(5).mean().iloc[-1]
            ma20 = kline['close'].rolling(20).mean().iloc[-1]
            rsi = calculate_rsi(kline)
            
            # 计算未来收益（未来20日）
            future_return = (kline['close'].iloc[-1] / kline['close'].iloc[-20] - 1) * 100 if len(kline) >= 20 else 0
            
            # 标签：收益>中位数 → 1
            data.append({
                'symbol': sym,
                'pe': val.get('pe_ttm', 0),
                'pb': val.get('pb', 0),
                'roe': fin.get('roe', 0) * 100 if fin.get('roe', 0) else 0,
                'profit_growth': growth.get('profit_growth', 0),
                'revenue_growth': growth.get('revenue_growth', 0),
                'north_hold': north.get('hold_ratio', 0),
                'ma5_ma20_ratio': ma5 / ma20 if ma20 else 1,
                'rsi': rsi,
                'future_return': future_return,
            })
        except Exception as e:
            continue
    
    df = pd.DataFrame(data)
    if df.empty or len(df) < 10:
        print("数据不足，无法分析")
        return
    
    # 训练XGBoost找有效因子
    features = ['pe', 'pb', 'roe', 'profit_growth', 'revenue_growth', 
                'north_hold', 'ma5_ma20_ratio', 'rsi']
    
    # 标签：收益>中位数
    median_return = df['future_return'].median()
    df['label'] = (df['future_return'] > median_return).astype(int)
    
    X = df[features].fillna(0)
    y = df['label']
    
    # 训练XGBoost
    model = XGBClassifier(n_estimators=50, max_depth=3, random_state=42)
    model.fit(X, y)
    
    # 获取特征重要性
    importance = pd.DataFrame({
        'factor': features,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\n" + "=" * 60)
    print("因子有效性排名（XGBoost分析）")
    print("=" * 60)
    for _, row in importance.iterrows():
        print(f"{row['factor']}: {row['importance']:.3f}")
    
    # 保存结果
    result = {
        'factor_ranking': importance.to_dict('records'),
        'effective_factors': importance[importance['importance'] > 0.1]['factor'].tolist(),
    }
    
    os.makedirs('data', exist_ok=True)
    with open('data/factor_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n有效因子: {result['effective_factors']}")
    print("结果已保存到 data/factor_analysis.json")

def calculate_rsi(kline, period=14):
    delta = kline['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]
    return rsi if not np.isnan(rsi) else 50

if __name__ == "__main__":
    import os
    analyze_factor_effectiveness()
