# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
MA200 每日信号：拉当日沪深300 收盘 + 200 日均线，输出当前该持有还是该空仓。
用法：python ma200_signal.py
"""
import sys
from ma200_common import get_pro, fetch_hs300, signal_state
sys.stdout.reconfigure(encoding='utf-8')


def main():
    pro = get_pro()
    df = fetch_hs300(pro)
    st = signal_state(df)
    if st is None:
        print('数据不足 200 日，无法判断信号')
        return
    label = '持有（60%股票）' if st['signal'] == 'hold' else '空仓（全现金）'
    print(f"日期: {st['date']}")
    print(f"沪深300收盘: {st['close']:.2f}")
    print(f"200日均线: {st['ma']:.2f}")
    print(f"信号: {label}")
    print(f"SIGNAL={st['signal']} CLOSE={st['close']:.2f} MA200={st['ma']:.2f}")


if __name__ == '__main__':
    main()
