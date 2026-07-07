# -*- coding: utf-8 -*-
"""
ML模型训练脚本
用历史数据训练XGBoost回归模型，预测未来5日收益
特征：基本面(ROE/PE/PB/北向) + 技术面(动量/波动率/RSI/量比)
标签：未来5日收益率
"""

import os
import sys
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from data.akshare_helper import AKShareHelper


def calc_rsi(close_series, period=14):
    """计算RSI"""
    delta = close_series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def build_features_for_date(helper, symbol, kline_df, date_idx):
    """为单只股票在指定日期构建特征

    Args:
        helper: AKShareHelper
        symbol: 股票代码
        kline_df: 该股票的完整K线数据
        date_idx: 当前日期在kline_df中的索引位置

    Returns:
        dict: 特征字典，或None（数据不足）
    """
    if date_idx < 60:  # 至少需要60天数据
        return None

    close = kline_df['close'].iloc[:date_idx + 1]
    volume = kline_df['volume'].iloc[:date_idx + 1]

    if len(close) < 60:
        return None

    try:
        # 基本面特征（从缓存获取，不区分日期——季度数据简化处理）
        fin = helper.get_financial_indicator(symbol)
        val = helper.get_valuation_data(symbol)
        north = helper.get_north_holding(symbol)

        # 技术面特征
        momentum_60d = (close.iloc[-1] / close.iloc[-60] - 1) * 100
        volatility_20d = close.pct_change().tail(20).std() * 100
        rsi_series = calc_rsi(close)
        rsi = rsi_series.iloc[-1] if not rsi_series.empty else 50
        vol_ma10 = volume.tail(10).mean()
        volume_ratio = volume.iloc[-1] / vol_ma10 if vol_ma10 > 0 else 1

        return {
            'symbol': symbol,
            'roe': float(fin.get('roe', 0) or 0),
            'pe_ttm': float(val.get('pe_ttm', 100) or 100),
            'pb': float(val.get('pb', 5) or 5),
            'north_ratio': float(north.get('hold_ratio', 0) or 0),
            'momentum_60d': float(momentum_60d),
            'volatility_20d': float(volatility_20d) if not np.isnan(volatility_20d) else 0,
            'rsi': float(rsi) if not np.isnan(rsi) else 50,
            'volume_ratio': float(volume_ratio) if not np.isnan(volume_ratio) else 1,
        }
    except Exception:
        return None


def build_label(kline_df, date_idx, forward_days=5):
    """构建标签：未来5日收益率

    Args:
        kline_df: 完整K线数据
        date_idx: 当前日期索引
        forward_days: 向前看的天数

    Returns:
        float: 未来5日收益率(%)，或None
    """
    end_idx = date_idx + forward_days
    if end_idx >= len(kline_df):
        return None
    current_close = kline_df['close'].iloc[date_idx]
    future_close = kline_df['close'].iloc[end_idx]
    if current_close <= 0:
        return None
    return (future_close / current_close - 1) * 100


def build_training_data(helper, symbols, lookback_days=200, forward_days=5):
    """构建训练数据

    Args:
        helper: AKShareHelper
        symbols: 股票代码列表
        lookback_days: 回看天数（训练数据时间跨度）
        forward_days: 标签向前看天数

    Returns:
        tuple: (X DataFrame, y Series)
    """
    # 获取交易日列表
    trading_dates = helper.get_trading_dates(n=lookback_days + forward_days + 60)
    if not trading_dates or len(trading_dates) < lookback_days:
        print(f"交易日数据不足: {len(trading_dates) if trading_dates else 0}")
        return pd.DataFrame(), pd.Series()

    # 只用最近的lookback_days个交易日做训练样本
    trading_dates = trading_dates[-(lookback_days + forward_days):]
    print(f"训练区间: {trading_dates[0]} ~ {trading_dates[-1]}")
    print(f"股票数: {len(symbols)}, 交易日数: {len(trading_dates)}")

    all_samples = []
    processed = 0

    for symbol in symbols:
        processed += 1
        if processed % 10 == 0:
            print(f"  处理进度: {processed}/{len(symbols)}")

        try:
            # 获取足够长的K线数据
            kline_df = helper.get_history_kline(symbol, days=lookback_days + forward_days + 60)
            if kline_df is None or kline_df.empty or len(kline_df) < 100:
                continue

            # 为每个交易日构建特征+标签
            for date_idx in range(60, len(kline_df) - forward_days):
                features = build_features_for_date(helper, symbol, kline_df, date_idx)
                label = build_label(kline_df, date_idx, forward_days)
                if features and label is not None:
                    features['label'] = label
                    features['date'] = kline_df['date'].iloc[date_idx]
                    all_samples.append(features)
        except Exception as e:
            continue

        # 避免API调用过快
        time.sleep(0.05)

    if not all_samples:
        print("未获取到训练样本")
        return pd.DataFrame(), pd.Series()

    df = pd.DataFrame(all_samples)
    print(f"\n训练样本总数: {len(df)}")

    feature_cols = ['roe', 'pe_ttm', 'pb', 'north_ratio',
                    'momentum_60d', 'volatility_20d', 'rsi', 'volume_ratio']
    X = df[feature_cols].fillna(0)
    y = df['label']
    return X, y


def train_model(X, y):
    """训练XGBoost回归模型

    采用时间序列分割：前80%训练，后20%验证
    """
    from xgboost import XGBRegressor
    from sklearn.metrics import mean_squared_error, r2_score

    # 时间序列分割（不能随机分割，避免未来数据泄露）
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"\n训练集: {len(X_train)} 样本")
    print(f"验证集: {len(X_val)} 样本")

    model = XGBRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False
    )

    # 评估
    train_pred = model.predict(X_train)
    val_pred = model.predict(X_val)
    train_mse = mean_squared_error(y_train, train_pred)
    val_mse = mean_squared_error(y_val, val_pred)
    train_r2 = r2_score(y_train, train_pred)
    val_r2 = r2_score(y_val, val_pred)

    print(f"\n模型评估:")
    print(f"  训练集 MSE: {train_mse:.4f}, R²: {train_r2:.4f}")
    print(f"  验证集 MSE: {val_mse:.4f}, R²: {val_r2:.4f}")

    # 特征重要性
    feature_cols = ['roe', 'pe_ttm', 'pb', 'north_ratio',
                    'momentum_60d', 'volatility_20d', 'rsi', 'volume_ratio']
    importances = model.feature_importances_
    print(f"\n特征重要性:")
    for col, imp in sorted(zip(feature_cols, importances), key=lambda x: -x[1]):
        print(f"  {col:<20}: {imp:.4f}")

    return model


def main():
    """主函数：构建数据 + 训练模型 + 保存"""
    print("=" * 60)
    print("ML模型训练 - XGBoost多因子合成")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    helper = AKShareHelper(cache_dir="data/cache")

    # 获取股票池
    print("\n获取沪深300成分股...")
    symbols = helper.get_stock_pool("hs300")[:80]  # 限制80只避免太慢
    print(f"股票数: {len(symbols)}")

    # 构建训练数据
    print("\n构建训练数据...")
    X, y = build_training_data(helper, symbols, lookback_days=200, forward_days=5)

    if X.empty:
        print("训练数据为空，退出")
        return

    # 训练模型
    print("\n训练XGBoost模型...")
    model = train_model(X, y)

    # 保存模型
    import joblib
    os.makedirs("data", exist_ok=True)
    model_path = "data/ml_model.pkl"
    joblib.dump(model, model_path)
    print(f"\n模型已保存: {model_path}")

    # 保存训练元数据
    meta = {
        'train_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sample_count': len(X),
        'feature_count': len(X.columns),
        'features': list(X.columns),
        'lookback_days': 200,
        'forward_days': 5,
        'stock_count': len(symbols),
    }
    with open("data/ml_model_meta.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("训练完成！")
    print("可运行 MLFactorStrategy 测试模型效果")
    print("=" * 60)


if __name__ == "__main__":
    main()
