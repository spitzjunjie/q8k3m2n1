"""模拟盘账本新鲜度检查

2026-10-03 起实盘主线为静态 60/40，选股回测（strategy_data.json）已停用定时任务，
本脚本改为检查静态 60/40 模拟盘 output/static6040_paper_state.json 的最后记账日。
该账本由 asset_allocation.yml 每个工作日更新；GitHub 定时任务 best-effort（可能延迟/跳过且无通知），
超期告警覆盖"模拟盘停摆无感知"。

阈值按工作日计：最后记账日之后已过去的工作日数 > MAX_WEEKDAYS 才告警。
取 7 是为了不在春节 / 国庆长假（休市最多约 6 个工作日）误报。
"""
import datetime
import json
import os
import sys

STATE_FILE = 'output/static6040_paper_state.json'
MAX_WEEKDAYS = 7


def weekdays_between(a, b):
    """a 之后到 b（含）之间的工作日数。"""
    n, d = 0, a
    while d < b:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def main():
    today = datetime.date.today()
    if today.weekday() >= 5:
        print(f"今天是周末（{today}），跳过检查")
        return 0

    if not os.path.exists(STATE_FILE):
        print(f"{STATE_FILE} 尚未生成（账本首次运行前），跳过检查")
        return 0
    try:
        d = json.load(open(STATE_FILE, encoding='utf-8'))
        last = d['history'][-1]['date']
        last_dt = datetime.datetime.strptime(last, '%Y%m%d').date()
    except Exception as e:
        print(f"读取 {STATE_FILE} 失败: {e}")
        return 1

    gap = weekdays_between(last_dt, today)
    if gap <= MAX_WEEKDAYS:
        print(f"✅ 模拟盘正常：最后记账日 {last}（之后 {gap} 个工作日，阈值 {MAX_WEEKDAYS}）")
        print(f"   净值={d['history'][-1].get('equity')}  记录天数={len(d['history'])}")
        return 0

    ut = last
    age_days = gap
    print(f"⚠️ 模拟盘停摆：最后记账日 {last}（今天 {today}，已过 {gap} 个工作日 > {MAX_WEEKDAYS}）")
    print("   请检查 GitHub Actions「资产配置回测」是否被跳过或失败")
    # 飞书告警
    aid = os.environ.get('FEISHU_APP_ID')
    sec = os.environ.get('FEISHU_APP_SECRET')
    rid = os.environ.get('FEISHU_RECEIVE_ID')
    if all([aid, sec, rid]):
        try:
            import requests
            token = requests.post(
                'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
                json={'app_id': aid, 'app_secret': sec}, timeout=10
            ).json().get('tenant_access_token')
            requests.post(
                'https://open.feishu.cn/open-apis/im/v1/messages',
                params={'receive_id_type': 'chat_id'},
                headers={'Authorization': f'Bearer {token}'},
                json={'receive_id': rid, 'msg_type': 'text',
                      'content': json.dumps({'text':
                          '⚠️ 静态 60/40 模拟盘停摆\n'
                          f'最后记账日: {ut}（之后 {age_days} 个工作日 > {MAX_WEEKDAYS}）\n'
                          f'今天: {today}\n'
                          '请检查 GitHub Actions「资产配置回测」并手动补跑（模拟盘会自动回放漏记日）'})},
                timeout=10)
            print("已推送飞书告警")
        except Exception as e:
            print(f"飞书告警失败: {e}")
    else:
        print("飞书未配置，跳过告警（仅日志）")
    return 1


if __name__ == '__main__':
    sys.exit(main())
