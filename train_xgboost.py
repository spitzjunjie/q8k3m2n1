# -*- coding: utf-8 -*-
"""
C.1 训练XGBoost多因子模型
收集所有策略的历史因子数据，构建训练数据集并训练XGBoost模型
"""

import os
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from data.akshare_helper import AKShareHelper
from strategies.factor_strategies import (
    ROEStrategy, LowPEStrategy, NorthHeavyStrategy,
    TrendMomentumStrategy, HighROICStrategy, HighDividendStrategy
)
from strategies.event_strategies import (
    ExecutiveBuyStrategy, TrendMomentumStrategy as EventTrendMomentum
)
from strategies.special_strategies import (
    MaBreakStrategy, MultiPeriodStrategy
)


def calc_rsi(close_series, period=14):
    """计算RSI指标"""
    delta = close_series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calc_bollinger_bands(close_series, period=20, std_dev=2):
    """计算布林带"""
    ma = close_series.rolling(period).mean()
    std = close_series.rolling(period).std()
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    return upper, ma, lower


def build_factor_features(helper, symbol, date=None):
    """构建单只股票的多因子特征
    
    特征包括:
    - 基本面: ROE、PE、PB、融资余额等
    - 动量: 20/60日动量
    - 北向持股比例
    
    Returns:
        dict: 特征字典
    """
    features = {'symbol': symbol}
    
    try:
        # 基本面数据
        fin = helper.get_financial_indicator(symbol)
        val = helper.get_valuation_data(symbol)
        north = helper.get_north_holding(symbol)
        
        features['roe'] = float(fin.get('roe', 0) or 0)
        features['pe_ttm'] = float(val.get('pe_ttm', 100) or 100)
        features['pb'] = float(val.get('pb', 5) or 5)
        features['dv_ttm'] = float(val.get('dv_ttm', 0) or 0)
        features['north_ratio'] = float(north.get('hold_ratio', 0) or 0)
        
        # K线数据
        kline = helper.get_history_kline(symbol, days=120, end_date=date)
        if kline is not None and not kline.empty and len(kline) >= 60:
            close = kline['close']
            volume = kline['volume']
            
            # 动量因子
            features['momentum_20d'] = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
            features['momentum_60d'] = (close.iloc[-1] / close.iloc[-60] - 1) * 100 if len(close) >= 60 else 0
            
            # 波动率
            features['volatility_20d'] = close.pct_change().tail(20).std() * 100
            
            # RSI
            rsi = calc_rsi(close)
            features['rsi'] = float(rsi.iloc[-1]) if not rsi.empty else 50
            
            # 成交量比
            vol_ma10 = volume.tail(10).mean()
            features['volume_ratio'] = volume.iloc[-1] / vol_ma10 if vol_ma10 > 0 else 1
            
            # 均线多头排列标记
            ma5 = close.rolling(5).mean().iloc[-1]
            ma10 = close.rolling(10).mean().iloc[-1]
            ma20 = close.rolling(20).mean().iloc[-1]
            ma60 = close.rolling(60).mean().iloc[-1] if len(close) >= 60 else ma20
            features['ma_bullish'] = 1 if (ma5 > ma10 > ma20) else 0
            features['ma_strong_bullish'] = 1 if (ma5 > ma10 > ma20 > ma60) else 0
            
            # 布林带位置
            upper, mid, lower = calc_bollinger_bands(close)
            features['bb_position'] = (close.iloc[-1] - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1]) if upper.iloc[-1] != lower.iloc[-1] else 0.5
            
        else:
            # 默认值
            features.update({
                'momentum_20d': 0, 'momentum_60d': 0,
                'volatility_20d': 0, 'rsi': 50,
                'volume_ratio': 1, 'ma_bullish': 0,
                'ma_strong_bullish': 0, 'bb_position': 0.5
            })
        
        # 融资余额（如果有）
        try:
            margin = helper.get_margin_balance(symbol)
            features['margin_balance'] = float(margin.get('balance', 0) or 0)
        except:
            features['margin_balance'] = 0
        
        return features
        
    except Exception as e:
        return None


def collect_strategy_factors(helper, symbols, lookback_days=180):
    """收集所有策略的历史因子数据
    
    Args:
        helper: AKShareHelper实例
        symbols: 股票代码列表
        lookback_days: 回看天数
    
    Returns:
        DataFrame: 包含所有因子数据的DataFrame
    """
    print(f"收集策略因子数据: {len(symbols)} 只股票, 回看 {lookback_days} 天")
    
    all_factors = []
    trading_dates = helper.get_trading_dates(n=lookback_days)
    
    if not trading_dates or len(trading_dates) < 30:
        print("交易日数据不足")
        return pd.DataFrame()
    
    # 每月采样一次以减少计算量
    sample_dates = trading_dates[::10]  # 每10天采样一次
    
    for i, date in enumerate(sample_dates):
        if i % 5 == 0:
            print(f"  进度: {i}/{len(sample_dates)} ({date})")
        
        for symbol in symbols:
            features = build_factor_features(helper, symbol, date)
            if features:
                features['date'] = date
                all_factors.append(features)
        
        time.sleep(0.05)  # 避免API限制
    
    df = pd.DataFrame(all_factors)
    print(f"收集到 {len(df)} 条因子记录")
    return df


def build_training_dataset(helper, symbols, forward_days=5):
    """构建训练数据集
    
    标签规则: 未来N日收益率 > 中位数 → 1, 否则 0
    
    Args:
        helper: AKShareHelper实例
        symbols: 股票代码列表
        forward_days: 预测未来天数
    
    Returns:
        tuple: (X DataFrame, y Series, 元数据dict)
    """
    print(f"\n构建训练数据集 (预测周期: {forward_days}天)")
    
    # 收集因子数据
    df = collect_strategy_factors(helper, symbols, lookback_days=180)
    
    if df.empty:
        return pd.DataFrame(), pd.Series(), {}
    
    # 计算未来收益作为标签
    labels = []
    for idx, row in df.iterrows():
        try:
            symbol = row['symbol']
            date = row['date']
            kline = helper.get_history_kline(symbol, days=forward_days + 10, end_date=date)
            
            if kline is not None and len(kline) >= forward_days:
                current_price = kline['close'].iloc[-forward_days]
                future_price = kline['close'].iloc[-1]
                if current_price > 0:
                    future_return = (future_price / current_price - 1) * 100
                    labels.append(future_return)
                else:
                    labels.append(0)
            else:
                labels.append(0)
        except:
            labels.append(0)
    
    df['future_return'] = labels
    
    # 过滤无效数据
    df = df[df['future_return'] != 0].dropna()
    
    if len(df) < 100:
        print("有效样本不足")
        return pd.DataFrame(), pd.Series(), {}
    
    # 构建二分类标签：未来收益 > 中位数 → 1, 否则 0
    median_return = df['future_return'].median()
    df['label'] = (df['future_return'] > median_return).astype(int)
    
    print(f"标签统计: 中位数={median_return:.2f}%, 正样本={df['label'].sum()}, 负样本={len(df) - df['label'].sum()}")
    
    # 特征列
    feature_cols = [
        'roe', 'pe_ttm', 'pb', 'dv_ttm', 'north_ratio',
        'momentum_20d', 'momentum_60d', 'volatility_20d',
        'rsi', 'volume_ratio', 'ma_bullish', 'ma_strong_bullish',
        'bb_position', 'margin_balance'
    ]
    
    # 过滤存在的列
    feature_cols = [col for col in feature_cols if col in df.columns]
    
    X = df[feature_cols].fillna(0)
    y = df['label']
    
    meta = {
        'sample_count': len(X),
        'feature_count': len(feature_cols),
        'features': feature_cols,
        'forward_days': forward_days,
        'positive_ratio': y.mean(),
        'median_return': median_return
    }
    
    return X, y, meta


def train_xgboost_model(X, y, test_size=0.2):
    """训练XGBoost多因子分类模型
    
    Args:
        X: 特征DataFrame
        y: 标签Series
        test_size: 测试集比例
    
    Returns:
        tuple: (model, 评估结果dict)
    """
    from xgboost import XGBClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, 
        f1_score, roc_auc_score, classification_report
    )
    
    print(f"\n训练XGBoost模型 (样本数: {len(X)}, 特征数: {len(X.columns)})")
    
    # 时间序列分割（前80%训练，后20%测试）
    split_idx = int(len(X) * (1 - test_size))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    print(f"训练集: {len(X_train)} 样本")
    print(f"测试集: {len(X_test)} 样本")
    
    # XGBoost分类器
    model = XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        min_child_weight=3,
        gamma=0.1,
        objective='binary:logistic',
        eval_metric='auc',
        random_state=42,
        n_jobs=-1,
        use_label_encoder=False
    )
    
    # 训练
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )
    
    # 预测
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    # 评估指标
    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'f1': f1_score(y_test, y_pred),
        'auc': roc_auc_score(y_test, y_pred_proba),
    }
    
    print(f"\n模型评估指标:")
    print(f"  准确率 (Accuracy): {metrics['accuracy']:.4f}")
    print(f"  精确率 (Precision): {metrics['precision']:.4f}")
    print(f"  召回率 (Recall): {metrics['recall']:.4f}")
    print(f"  F1分数: {metrics['f1']:.4f}")
    print(f"  AUC: {metrics['auc']:.4f}")
    
    return model, metrics


def print_feature_importance(model, feature_cols):
    """输出特征重要性排名"""
    print(f"\n{'='*50}")
    print("特征重要性排名")
    print(f"{'='*50}")
    
    importances = model.feature_importances_
    sorted_features = sorted(zip(feature_cols, importances), key=lambda x: -x[1])
    
    print(f"{'排名':<6}{'特征名':<20}{'重要性':<12}{'说明'}")
    print("-" * 60)
    
    feature_descriptions = {
        'roe': '净资产收益率',
        'pe_ttm': '市盈率TTM',
        'pb': '市净率',
        'dv_ttm': '股息率TTM',
        'north_ratio': '北向持股比例',
        'momentum_20d': '20日动量',
        'momentum_60d': '60日动量',
        'volatility_20d': '20日波动率',
        'rsi': 'RSI指标',
        'volume_ratio': '量比',
        'ma_bullish': '均线多头标记',
        'ma_strong_bullish': '均线强多头标记',
        'bb_position': '布林带位置',
        'margin_balance': '融资余额'
    }
    
    for rank, (feature, imp) in enumerate(sorted_features, 1):
        desc = feature_descriptions.get(feature, '')
        print(f"{rank:<6}{feature:<20}{imp:<12.4f}{desc}")
    
    print(f"{'='*50}\n")
    
    return sorted_features


def save_model_and_metadata(model, metrics, meta, feature_importance, output_dir='models'):
    """保存模型和元数据"""
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存模型
    model_path = os.path.join(output_dir, 'xgboost_model.json')
    model.save_model(model_path)
    print(f"模型已保存: {model_path}")
    
    # 保存特征重要性
    importance_path = os.path.join(output_dir, 'feature_importance.json')
    importance_data = [
        {'feature': f, 'importance': float(i)} 
        for f, i in feature_importance
    ]
    with open(importance_path, 'w', encoding='utf-8') as f:
        json.dump(importance_data, f, ensure_ascii=False, indent=2)
    print(f"特征重要性已保存: {importance_path}")
    
    # 保存完整元数据
    meta_path = os.path.join(output_dir, 'xgboost_meta.json')
    full_meta = {
        'train_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'model_type': 'XGBClassifier',
        'metrics': metrics,
        'data_meta': meta,
        'feature_importance': importance_data
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(full_meta, f, ensure_ascii=False, indent=2)
    print(f"元数据已保存: {meta_path}")
    
    return model_path, importance_path, meta_path


def main():
    """主函数"""
    print("=" * 60)
    print("C.1 训练XGBoost多因子模型")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 初始化
    helper = AKShareHelper(cache_dir="data/cache")
    
    # 获取股票池
    print("\n获取股票池...")
    symbols = helper.get_stock_pool("hs300")[:50]  # 限制50只避免太慢
    print(f"股票数: {len(symbols)}")
    
    # 构建训练数据
    X, y, meta = build_training_dataset(helper, symbols, forward_days=5)
    
    if X.empty:
        print("训练数据为空，退出")
        return
    
    # 训练模型
    print("\n开始训练XGBoost模型...")
    model, metrics = train_xgboost_model(X, y)
    
    # 特征重要性
    feature_importance = print_feature_importance(model, list(X.columns))
    
    # 保存模型
    paths = save_model_and_metadata(model, metrics, meta, feature_importance)
    
    print("\n" + "=" * 60)
    print("训练完成！")
    print(f"模型文件: {paths[0]}")
    print(f"特征重要性: {paths[1]}")
    print(f"元数据: {paths[2]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
