"""每周回测数据新鲜度检查

读取 output/strategy_data.json 的 update_time，与"最近一次周回测应产出"比较。
backtest.yml（workflow 名「每日单次回测」）自 2026-08-26 起已降频为每周一运行，
故 strategy_data.json 每周才更新一次。本脚本工作日 UTC 15:00（北京 23:00）检查
数据是否在 MAX_AGE_DAYS 天内更新过，超期才告警——避免对每周节奏误报。
GitHub 定时任务 best-effort（可能延迟/跳过且无通知），超期告警覆盖"周回测停摆无感知"。
"""
import datetime
import json
import os
import sys

# 每周回测 -> 数据最旧应为 7 天（上周一）；留 1 天缓冲 = 8 天。
# 超过 8 天说明已错过一个完整周回测周期，才告警。
MAX_AGE_DAYS = 8


def main():
    now = datetime.datetime.now()
    today = now.date()
    if today.weekday() >= 5:
        print(f"今天是周末（{today}），跳过检查")
        return 0

    try:
        d = json.load(open('output/strategy_data.json', encoding='utf-8'))
    except Exception as e:
        print(f"读取 strategy_data.json 失败: {e}")
        return 1

    ut = (d.get('update_time') or '').strip()
    try:
        ut_dt = datetime.datetime.strptime(ut[:19], '%Y-%m-%d %H:%M:%S')
    except Exception:
        print(f"update_time 格式异常: {ut!r}")
        return 1

    # 每周回测：数据在 MAX_AGE_DAYS 天内更新即视为新鲜。
    age_days = (today - ut_dt.date()).days
    if age_days <= MAX_AGE_DAYS:
        print(f"✅ 数据新鲜：update_time={ut}（{age_days} 天前，阈值 {MAX_AGE_DAYS} 天）")
        print(f"   策略数={len(d.get('strategies', []))}")
        return 0

    # 过期：告警
    print(f"⚠️ 数据过期：update_time={ut}（今天是 {today}，已 {age_days} 天 > {MAX_AGE_DAYS}）")
    print("   说明最近一次每周回测未产出数据（定时跳过/超时/失败）")
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
                          '⚠️ 每周回测数据过期\n'
                          f'update_time: {ut}（已 {age_days} 天 > {MAX_AGE_DAYS}）\n'
                          f'今天: {today}\n'
                          '请检查 GitHub Actions「每日单次回测」（现为每周一运行）并手动补跑'})},
                timeout=10)
            print("已推送飞书告警")
        except Exception as e:
            print(f"飞书告警失败: {e}")
    else:
        print("飞书未配置，跳过告警（仅日志）")
    return 1


if __name__ == '__main__':
    sys.exit(main())
