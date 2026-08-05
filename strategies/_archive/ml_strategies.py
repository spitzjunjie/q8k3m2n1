# -*- coding: utf-8 -*-
"""
ML因子合成策略
用XGBoost合成多因子（ROE+PE+动量+北向+技术指标），预测未来5日收益
模型由 train_ml_model.py 训练，保存在 data/ml_model.pkl
"""

import os
import pandas as pd
import numpy as np
from strategies.base import FactorStrategy


class MLFactorStrategy(FactorStrategy):
    """XGBoost多因子合成策略

    特征工程：
        - 基本面：ROE, PE_TTM, PB, 北向持股比例
        - 技术面：60日动量, 20日波动率, RSI, 量比
    标签：未来5日收益率
    模型：XGBRegressor
    """

    def __init__(self):
        super().__init__("ML多因子合成", "ML策略", "ML综合得分")
        self.version = "1.0.0"
        self.model = None
        self.model_path = "data/ml_model.pkl"
        self._load_model()

    def get_description(self):
        return "XGBoost合成ROE+PE+动量+北向+技术指标，预测未来5日收益"

    def _load_model(self):
        """加载训练好的模型"""
        try:
            import joblib
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
        except ImportError:
            print("ML策略: joblib未安装，跳过模型加载")
        except Exception as e:
            print(f"ML策略: 加载模型失败: {e}")

    def _calc_rsi(self, close_series, period=14):
        """计算RSI指标"""
        try:
            delta = close_series.diff()
            gain = delta.where(delta > 0, 0).rolling(period).mean()
            loss = -delta.where(delta < 0, 0).rolling(period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not rsi.empty else 50
        except Exception:
            return 50

    def _build_features(self, helper, symbols):
        """构建特征矩阵

        Returns:
            DataFrame: 包含symbol列和特征列
        """
        features = []
        for sym in symbols:
            try:
                fin = helper.get_financial_indicator(sym)
                val = helper.get_valuation_data(sym)
                north = helper.get_north_holding(sym)
                kline = helper.get_history_kline(sym, days=90)

                if kline is None or kline.empty or len(kline) < 60:
                    continue

                close = kline['close']
                volume = kline['volume']

                # 基本面特征
                roe = fin.get('roe', 0)
                pe_ttm = val.get('pe_ttm', 100)
                pb = val.get('pb', 5)
                north_ratio = north.get('hold_ratio', 0)

                # 技术面特征
                momentum_60d = (close.iloc[-1] / close.iloc[-60] - 1) * 100
                volatility_20d = close.pct_change().tail(20).std() * 100
                rsi = self._calc_rsi(close)
                vol_ma10 = volume.tail(10).mean()
                volume_ratio = volume.iloc[-1] / vol_ma10 if vol_ma10 > 0 else 1

                feat = {
                    'symbol': sym,
                    'roe': float(roe) if roe else 0,
                    'pe_ttm': float(pe_ttm) if pe_ttm else 100,
                    'pb': float(pb) if pb else 5,
                    'north_ratio': float(north_ratio) if north_ratio else 0,
                    'momentum_60d': float(momentum_60d),
                    'volatility_20d': float(volatility_20d) if not np.isnan(volatility_20d) else 0,
                    'rsi': float(rsi) if rsi else 50,
                    'volume_ratio': float(volume_ratio) if not np.isnan(volume_ratio) else 1,
                }
                features.append(feat)
            except Exception:
                continue
        return pd.DataFrame(features)

    def calculate_factor(self, helper, date=None):
        """用ML模型预测未来5日收益，作为因子值"""
        if self.model is None:
            print("ML策略: 模型未加载，请先运行 train_ml_model.py")
            return pd.DataFrame()

        symbols = helper.get_stock_pool("hs300")[:80]
        features = self._build_features(helper, symbols)
        if features.empty:
            return pd.DataFrame()

        # 预测
        feature_cols = ['roe', 'pe_ttm', 'pb', 'north_ratio',
                        'momentum_60d', 'volatility_20d', 'rsi', 'volume_ratio']
        X = features[feature_cols].fillna(0)
        features['predicted_return'] = self.model.predict(X)

        # 构建输出DataFrame
        df = features[['symbol', 'predicted_return']].copy()
        df['name'] = df['symbol']
        df = df.rename(columns={'predicted_return': 'factor_value'})
        df = df.sort_values('factor_value', ascending=False).head(30)
        df['reason'] = df.apply(
            lambda r: f"ML预测5日收益={r['factor_value']:.2f}%", axis=1)
        return df


if __name__ == "__main__":
    # 测试ML策略（需要先训练模型）
    from data.akshare_helper import AKShareHelper
    helper = AKShareHelper()
    strategy = MLFactorStrategy()
    if strategy.model is None:
        print("模型未训练，请先运行: python train_ml_model.py")
    else:
        result = strategy.select_stocks(helper)
        print(f"选出 {len(result)} 只股票")
        if not result.empty:
            print(result[['symbol', 'factor_value', 'reason']].head(10))
