"""每日回测数据新鲜度检查

读取 output/strategy_data.json 的 update_time，与"今天应产出"比较。
GitHub 定时任务 best-effort（可能延迟/跳过且无通知），本脚本在工作日
UTC 15:00（北京 23:00）检查今天的回测是否完成，过期则告警。
"""
import datetime
import json
import os
import sys


def main():
    now = datetime.datetime.now()
    # 回测在 UTC 10:30 触发，30-60 分钟完成，UTC 15:00 检查时今天应已完成
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

    # 期望 update_time 是今天（UTC）。GitHub 定时可能延迟到 12:30 触发，
    # 回测 30-60 分钟 -> 最晚 13:30 完成；若 update_time 是昨天或更早
    # 说明今天的回测没产出（定时跳过/超时/失败）
    if ut_dt.date() >= today:
        print(f"✅ 数据新鲜：update_time={ut}（今天 {today}）")
        print(f"   策略数={len(d.get('strategies', []))}")
        return 0

    # 过期：告警
    print(f"⚠️ 数据过期：update_time={ut}（今天是 {today}）")
    print("   说明今天的每日回测未产出数据（定时跳过/超时/失败）")
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
                          '⚠️ 每日回测数据过期\n'
                          f'update_time: {ut}\n'
                          f'今天: {today}\n'
                          '请检查 GitHub Actions 每日单次回测并手动补跑'})},
                timeout=10)
            print("已推送飞书告警")
        except Exception as e:
            print(f"飞书告警失败: {e}")
    else:
        print("飞书未配置，跳过告警（仅日志）")
    return 1


if __name__ == '__main__':
    sys.exit(main())
