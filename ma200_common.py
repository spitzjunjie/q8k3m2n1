# -*- coding: utf-8 -*-
"""MA200 信号公共逻辑：拉沪深300收盘 + 算 200 日均线 + 信号（供信号/模拟盘复用）。"""
import os, sys
from datetime import datetime, timedelta
sys.stdout.reconfigure(encoding='utf-8')
try:
    from dotenv import load_dotenv
    load_dotenv('.env')
except Exception:
    pass
import tushare as ts

MA = 200
INDEX = '000300.SH'


def get_pro():
    ts.set_token(os.environ.get('TUSHARE_TOKEN', ''))
    return ts.pro_api()


def fetch_hs300(pro, n_days=420):
    """拉近 n_days 个交易日的沪深300 收盘（含 MA200 所需的足够窗口）。"""
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=n_days * 2)).strftime('%Y%m%d')
    df = pro.index_daily(ts_code=INDEX, start_date=start, end_date=end)
    df = df.sort_values('trade_date').reset_index(drop=True)
    return df[['trade_date', 'close']]


def signal_state(df, ma=MA):
    """返回 {date, close, ma, signal: 'hold'|'cash'}；数据不足返回 None。"""
    closes = df['close'].astype(float).tolist()
    dates = df['trade_date'].astype(str).tolist()
    if len(closes) < ma:
        return None
    last_close = closes[-1]
    last_date = dates[-1]
    ma_val = sum(closes[-ma:]) / ma
    return {
        'date': last_date, 'close': last_close, 'ma': ma_val,
        'signal': 'hold' if last_close >= ma_val else 'cash',
    }
