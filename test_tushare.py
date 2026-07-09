from data.tushare_helper import TushareHelper
h = TushareHelper()
symbols = ['002594', '600276']  # 比亚迪、恒瑞医药
for s in symbols:
    df = h.get_history_kline(s, days=5)
    if not df.empty:
        print(f'{s}: 最新价={df["close"].iloc[-1]}')
    else:
        print(f'{s}: 获取失败')
