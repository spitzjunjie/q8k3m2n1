# -*- coding: utf-8 -*-
"""正确合并策略数据 - 保留现有数据，如果存在新数据则合并"""
import json
import os
import subprocess
from datetime import datetime
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def _trade_key(t):
    """交易去重键：symbol + buy_date + sell_date"""
    return (str(t.get('symbol', '')), str(t.get('buy_date', '')), str(t.get('sell_date', '')))


def _full_history(s):
    """策略的完整历史交易：all_trades 优先，回退 trades"""
    return s.get('all_trades') or s.get('trades') or []


def _merge_equity_curve(old_curve, new_curve):
    """按日期合并权益曲线：同日以新覆盖旧，旧日期补齐新缺失的日期。

    解决「两条回测链路产出不同长度曲线、合并时整段覆盖导致数据丢失」的问题。
    equity_curve 元素可能是 {'date','value'} 或裸数值；裸数值无日期，直接保留新的。
    """
    if not new_curve:
        return list(old_curve)
    if not old_curve:
        return list(new_curve)
    if not all(isinstance(x, dict) and 'date' in x for x in list(old_curve) + list(new_curve)):
        return list(new_curve)
    merged = {x['date']: x for x in old_curve}
    for x in new_curve:
        merged[x['date']] = x
    return [merged[d] for d in sorted(merged.keys())]


def align_equity_curves(strategies):
    """把所有策略的 equity_curve 重采样到统一的交易日序列。

    统一交易日序列来自 core.trading_calendar，区间取所有策略权益曲线的
    最早日期到最晚日期。缺的日期 value 填 None（JSON 序列化为 null，表示 MISSING）。
    这样每个策略的 equity_curve 长度一致，可做跨策略比较/相关性。
    """
    if not strategies:
        return strategies

    from datetime import datetime, timedelta
    from core.trading_calendar import is_trading_day

    # 1. 收集所有策略的日期范围（YYYYMMDD）
    seen = set()
    for s in strategies:
        for x in s.get('equity_curve', []) or []:
            if isinstance(x, dict) and x.get('date'):
                seen.add(str(x['date']).replace('-', ''))
    if not seen:
        return strategies

    # 用内置节假日表生成交易日序列（离线，不走网络，避免拖慢合并）
    start = datetime.strptime(min(seen), '%Y%m%d')
    end = datetime.strptime(max(seen), '%Y%m%d')
    fmt_dates = []
    cur = start
    while cur <= end:
        if is_trading_day(cur):
            fmt_dates.append(cur.strftime('%Y-%m-%d'))
        cur += timedelta(days=1)
    if not fmt_dates:
        return strategies

    # 2. 重采样每个策略：缺的日期 value=None
    for s in strategies:
        curve = s.get('equity_curve', []) or []
        value_map = {}
        for x in curve:
            if isinstance(x, dict) and x.get('date'):
                d = str(x['date']).replace('-', '')
                value_map[d] = x.get('value')
        s['equity_curve'] = [
            {'date': d, 'value': value_map.get(d.replace('-', ''))}
            for d in fmt_dates
        ]
    return strategies


def merge_strategy_state(old_s, new_s):
    """合并单策略：保留旧历史交易 + 叠加新状态（持仓/资金/权益/指标）。

    每日回测是"上一日状态续接"：新版本自带完整历史（all_trades=历史+今日卖出），
    但为防御水合失败/字段缺失，这里仍以"旧历史为基础 + 追加新交易 + 覆盖最新状态"
    的方式合并，保证历史交易永不丢失。
    """
    merged = dict(old_s)

    # 1. 交易历史：旧历史 + 新历史中不重复的（今日新卖出的）
    old_trades = _full_history(old_s)
    old_keys = {_trade_key(t) for t in old_trades}
    new_trades = _full_history(new_s)
    added = [t for t in new_trades if _trade_key(t) not in old_keys]
    merged['all_trades'] = list(old_trades) + added
    merged['trades'] = list(merged['all_trades'])

    # 2. 最新状态以新版本为准（持仓/资金/权益曲线/展示指标）
    overlay_keys = (
        'holdings', 'current_capital', 'total_fees',
        'realized_pnl', 'realized_pnl_pct',
        'floating_pnl', 'floating_pnl_pct',
        'total_pnl', 'total_pnl_pct',
        'total_value',
        'total_return', 'monthly_return',
        'sharpe_ratio', 'max_drawdown', 'win_rate',
        'composite_score', 'grade',
        'profit_loss_ratio', 'return_stability', 'calmar_ratio',
    )
    for k in overlay_keys:
        if k in new_s:
            merged[k] = new_s[k]

    # 3. equity_curve 特殊处理：按日期合并，不整段覆盖
    merged['equity_curve'] = _merge_equity_curve(
        old_s.get('equity_curve', []), new_s.get('equity_curve', []))
    return merged


def main():
    # 本次回测刚生成的新数据（由 backtest.py 写入，update_time 为当前时间）
    # 注意：不要用 output/new_strategy_results.json —— 它可能长期没更新，
    # 之前就是因为它被 git 追踪、内容停留在 7/28，导致每天合并的都是旧数据。
    new_file = 'output/strategy_data.json'
    
    if not os.path.exists(new_file):
        print("没有新策略数据文件，跳过合并")
        # 仍然检查并保存当前数据
        if os.path.exists('output/strategy_data.json'):
            print("当前数据文件已存在，无需更新")
        return
    
    # 从git获取原始数据（如果存在）
    old_data = None
    try:
        result = subprocess.run(
            ['git', 'show', 'HEAD:output/strategy_data.json'],
            capture_output=True, text=True, encoding='utf-8-sig',
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            old_data = json.loads(result.stdout)
            print(f"Git原始策略: {len(old_data.get('strategies', []))}个")
    except Exception as e:
        print(f"获取Git原始数据失败: {e}")
    
    # 如果没有原始数据，尝试使用当前文件
    if old_data is None:
        if os.path.exists('output/strategy_data.json'):
            try:
                with open('output/strategy_data.json', 'r', encoding='utf-8') as f:
                    old_data = json.load(f)
                print(f"使用当前数据: {len(old_data.get('strategies', []))}个策略")
            except Exception as e:
                print(f"读取当前数据失败: {e}")
                old_data = {'strategies': [], 'update_time': ''}
        else:
            old_data = {'strategies': [], 'update_time': ''}
            print("没有找到任何历史数据，创建新数据文件")
    
    # 读取新数据
    try:
        with open(new_file, 'r', encoding='utf-8') as f:
            new_data = json.load(f)
        print(f"新策略: {len(new_data.get('strategies', []))}个")
    except Exception as e:
        print(f"读取新数据失败: {e}")
        new_data = {'strategies': []}

    # 陈旧数据守卫：new_file 就是 output/strategy_data.json，它可能是 checkout 下来的
    # 旧文件（7/25 起每日回测全部超时，旧文件长期被当成"新数据"自我合并，产生假提交）。
    # 只有 update_time 在最近 7 天内的才允许合并；否则警告并跳过，保持仓库数据不变。
    ut = (new_data.get('update_time') or '').strip()
    try:
        ut_dt = datetime.strptime(ut[:19], '%Y-%m-%d %H:%M:%S')
        if (datetime.now() - ut_dt).total_seconds() > 7 * 24 * 3600:
            print(f"⚠️ 新数据 update_time 过旧（{ut}），判定为陈旧数据，跳过合并")
            print("   回测未真正产出新数据（可能超时/失败），保持仓库当前数据不变")
            return
    except Exception:
        print(f"⚠️ 新数据 update_time 格式异常（{ut!r}），跳过合并")
        return
    
    # 处理策略：有活动（交易/持仓/收益变化）才合并；旧策略走"旧历史+新状态"
    old_names = {s['name'] for s in old_data.get('strategies', [])}
    added = []
    replaced = []

    for s in new_data.get('strategies', []):
        has_activity = (
            s.get('trades')
            or s.get('holdings')
            or s.get('total_return', 0) != 0
        )
        if not has_activity:
            continue

        if s['name'] in old_names:
            for i, old_s in enumerate(old_data['strategies']):
                if old_s['name'] == s['name']:
                    old_data['strategies'][i] = merge_strategy_state(old_s, s)
                    replaced.append(
                        f"{s['name']}: {s.get('total_pnl_pct', 0):.2f}% "
                        f"(交易{len(_full_history(s))}笔/持仓{len(s.get('holdings', []))}只)"
                    )
                    break
        else:
            # 新策略：完整保留
            old_data['strategies'].append(s)
            added.append(f"{s['name']}: {s.get('total_pnl_pct', 0):.2f}%")
    
    print(f"\n替换策略: {len(replaced)}个")
    for r in replaced:
        print(f"  🔄 {r}")
    
    print(f"新增策略: {len(added)}个")
    for a in added:
        print(f"  ✅ {a}")
    
    old_data['strategy_count'] = len(old_data['strategies'])
    # 用本次回测的真实时间，不再硬编码
    old_data['update_time'] = new_data.get('update_time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 如果新数据带回了测区间元数据，以新数据为准
    for k in ('backtest_type', 'backtest_start', 'backtest_end', 'backtest_days'):
        if new_data.get(k):
            old_data[k] = new_data[k]
    
    # 权益曲线按交易日历对齐（缺的日期补 null）
    old_data['strategies'] = align_equity_curves(old_data['strategies'])

    # 保存
    with open('output/strategy_data.json', 'w', encoding='utf-8') as f:
        json.dump(old_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n最终策略数: {len(old_data['strategies'])}")

if __name__ == '__main__':
    main()
