#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
数据可用性体检
====================================================================
要回答的问题：output/zero_analysis.json 显示 92 个策略里 68 个零成交，
这 68 个到底是「真的没信号」还是「数据没拿到」？

为什么现在分不清：
  仓库里有 167 处 bare except。策略调 helper 拿数据，接口挂了抛异常，
  被 except 吞掉，策略安静地返回空列表，看板显示 0.00%。
  从结果上，「今天确实没机会」和「接口 404 了」长得一模一样。

这个脚本怎么解决：
  **在 helper 层做插桩，而不是在策略层。**
  把 AKShareHelper / TushareHelper 的每个公开方法包一层，
  记录：谁调的、传了什么、返回几行、耗时多久、抛没抛异常。
  记录发生在策略的 except 之前，所以吞不掉。

跑完你会得到一张表，68 个零成交会被分成三类：
  A. helper 报错     -> 接口问题，修数据层就能救活
  B. helper 返回空   -> 数据源没这个数据，要换源或换实现
  C. 数据正常但没选出票 -> 真的是策略条件太严，这才是策略问题

用法（必须在你自己机器上跑，需要联网）：
    cd C:\Users\xrs08\Desktop\量化交易系统\stock_intelligence\multi_strategy_trading
    . .\load_env.ps1
    python scripts\diagnose_data.py --limit 10      # 先小规模试跑
    python scripts\diagnose_data.py                 # 全量

输出：output/data_diagnosis.json 与 output/data_diagnosis.md
====================================================================
"""

import argparse
import functools
import json
import os
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class CallRecorder:
    """记录当前策略对 helper 的所有调用"""

    def __init__(self):
        self.current = None
        self.log = defaultdict(list)

    def start(self, strategy_name):
        self.current = strategy_name
        self.log.setdefault(strategy_name, [])

    def record(self, method, args, kwargs, result, error, elapsed):
        if self.current is None:
            return
        self.log[self.current].append({
            "method": method,
            "arg": _brief_args(args, kwargs),
            "rows": _size_of(result),
            "empty": _is_empty(result),
            "error": error,
            "ms": round(elapsed * 1000),
        })


def _brief_args(args, kwargs):
    parts = [repr(a)[:24] for a in args[:2]]
    parts += ["%s=%s" % (k, repr(v)[:16]) for k, v in list(kwargs.items())[:2]]
    return ", ".join(parts)


def _size_of(x):
    if x is None:
        return 0
    try:
        import pandas as pd
        if isinstance(x, (pd.DataFrame, pd.Series)):
            return len(x)
    except Exception:
        pass
    if isinstance(x, (list, tuple, dict, set)):
        return len(x)
    return 1


def _is_empty(x):
    if x is None:
        return True
    try:
        import pandas as pd
        if isinstance(x, (pd.DataFrame, pd.Series)):
            return x.empty
    except Exception:
        pass
    if isinstance(x, (list, tuple, dict, set, str)):
        return len(x) == 0
    return False


def instrument(helper, recorder):
    """把 helper 实例的所有公开方法包一层记录器"""
    for name in dir(helper):
        if name.startswith("_"):
            continue
        attr = getattr(helper, name)
        if not callable(attr):
            continue

        def make(mname, orig):
            @functools.wraps(orig)
            def wrapped(*a, **kw):
                t0 = time.time()
                try:
                    r = orig(*a, **kw)
                    recorder.record(mname, a, kw, r, None, time.time() - t0)
                    return r
                except Exception as e:
                    # 关键：在策略的 except 吞掉它之前先记下来
                    recorder.record(mname, a, kw, None,
                                    ("%s: %s" % (type(e).__name__, e))[:180],
                                    time.time() - t0)
                    raise
            return wrapped

        try:
            setattr(helper, name, make(name, attr))
        except Exception:
            pass
    return helper


def classify(calls, n_selected, strategy_error):
    """归类 —— 这是整个脚本的产出重点"""
    if strategy_error:
        return "E_策略崩溃", "策略代码本身抛异常（原本被 bare except 吞掉）"
    if not calls:
        return "D_没调数据", "选股过程没有调用任何 helper —— 可能是硬编码或提前 return"
    errs = [c for c in calls if c["error"]]
    empties = [c for c in calls if not c["error"] and c["empty"]]
    if n_selected > 0:
        return "OK_正常", "选出 %d 只" % n_selected
    if errs:
        return "A_接口报错", "%d/%d 次调用抛异常，首个：%s -> %s" % (
            len(errs), len(calls), errs[0]["method"], errs[0]["error"][:80])
    if empties and len(empties) == len(calls):
        return "B_数据为空", "%d 次调用全部返回空，首个：%s" % (len(empties), empties[0]["method"])
    if empties:
        return "B_数据部分为空", "%d/%d 次调用返回空，首个：%s" % (
            len(empties), len(calls), empties[0]["method"])
    return "C_条件太严", "%d 次调用都拿到数据了，但没有股票通过筛选条件" % len(calls)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="akshare", choices=["akshare", "tushare"])
    ap.add_argument("--date", default=None, help="回测日期 YYYYMMDD，默认最近交易日")
    ap.add_argument("--limit", type=int, default=0, help="只测前 N 个策略，0=全部")
    ap.add_argument("--only", default="", help="只测指定策略，逗号分隔")
    args = ap.parse_args()

    print("=" * 70)
    print("数据可用性体检")
    print("=" * 70)

    if args.source == "tushare":
        from data.tushare_helper import TushareHelper
        helper = TushareHelper()
    else:
        from data.akshare_helper import AKShareHelper
        helper = AKShareHelper(cache_dir="data/cache")

    recorder = CallRecorder()
    instrument(helper, recorder)

    from backtest import get_all_strategies
    strategies = get_all_strategies()
    if args.only:
        want = set(x.strip() for x in args.only.split(",") if x.strip())
        strategies = [s for s in strategies if getattr(s, "name", "") in want]
    if args.limit:
        strategies = strategies[:args.limit]

    print("数据源  : %s" % args.source)
    print("策略数  : %d" % len(strategies))
    print("日期    : %s" % (args.date or "最近交易日"))
    print("-" * 70)

    results = []
    t_all = time.time()

    for i, st in enumerate(strategies, 1):
        name = getattr(st, "name", st.__class__.__name__)
        recorder.start(name)
        selected, err = [], None
        t0 = time.time()
        try:
            selected = st.select_stocks(helper, args.date) or []
        except Exception as e:
            err = ("%s: %s" % (type(e).__name__, e))[:200]
        elapsed = time.time() - t0

        calls = recorder.log.get(name, [])
        cat, detail = classify(calls, len(selected), err)

        results.append({
            "name": name,
            "category": getattr(st, "category", ""),
            "class": st.__class__.__name__,
            "selected": len(selected),
            "n_calls": len(calls),
            "n_errors": sum(1 for c in calls if c["error"]),
            "n_empty": sum(1 for c in calls if not c["error"] and c["empty"]),
            "seconds": round(elapsed, 1),
            "verdict": cat,
            "detail": detail,
            "strategy_error": err,
            "calls": calls[:40],
        })

        flag = {"OK_正常": "OK ", "A_接口报错": "ERR", "B_数据为空": "EMP",
                "B_数据部分为空": "EMP", "C_条件太严": "STR",
                "D_没调数据": "---", "E_策略崩溃": "!!!"}.get(cat, "?  ")
        print("[%3d/%d] %s %-20s 选出%3d  调用%3d  %5.1fs  %s" % (
            i, len(strategies), flag, name[:20], len(selected), len(calls),
            elapsed, detail[:60]))

    total_time = time.time() - t_all

    buckets = defaultdict(list)
    for r in results:
        buckets[r["verdict"]].append(r["name"])

    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    for k in ["OK_正常", "A_接口报错", "B_数据为空", "B_数据部分为空",
              "C_条件太严", "D_没调数据", "E_策略崩溃"]:
        if k in buckets:
            print("  %-16s %3d 个" % (k, len(buckets[k])))

    fail = defaultdict(lambda: {"err": 0, "empty": 0, "ok": 0})
    for r in results:
        for c in r["calls"]:
            k = c["method"]
            if c["error"]:
                fail[k]["err"] += 1
            elif c["empty"]:
                fail[k]["empty"] += 1
            else:
                fail[k]["ok"] += 1

    print("\n  helper 方法健康度（按失败次数排序）：")
    print("    %-28s%6s%6s%6s" % ("方法", "成功", "空", "报错"))
    ranked = sorted(fail.items(), key=lambda kv: -(kv[1]["err"] + kv[1]["empty"]))
    for m, s in ranked[:20]:
        if s["err"] or s["empty"]:
            print("    %-28s%6d%6d%6d" % (m, s["ok"], s["empty"], s["err"]))

    os.makedirs("output", exist_ok=True)
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": args.source,
        "date": args.date,
        "total_strategies": len(results),
        "total_seconds": round(total_time),
        "summary": dict((k, len(v)) for k, v in buckets.items()),
        "buckets": dict(buckets),
        "helper_health": dict(ranked),
        "strategies": results,
    }
    with open("output/data_diagnosis.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    _write_md(payload, ranked)

    print("\n  耗时 %.0fs" % total_time)
    print("  明细 -> output/data_diagnosis.json")
    print("  报告 -> output/data_diagnosis.md")
    print("\n" + "=" * 70)
    a = len(buckets.get("A_接口报错", []))
    b = len(buckets.get("B_数据为空", [])) + len(buckets.get("B_数据部分为空", []))
    c = len(buckets.get("C_条件太严", []))
    print("  可修复的（接口报错 + 数据为空）：%d 个" % (a + b))
    print("  真正的策略问题（条件太严）：    %d 个" % c)
    print("  —— 前者改数据层就能救活，后者才需要动策略逻辑。")
    print("=" * 70)
    return 0


def _write_md(p, ranked):
    L = []
    L.append("# 数据可用性体检报告\n")
    L.append("生成时间：%s　|　数据源：%s　|　策略数：%d　|　耗时：%ds\n" % (
        p["generated_at"], p["source"], p["total_strategies"], p["total_seconds"]))

    meaning = {
        "OK_正常": "选出了股票，工作正常",
        "A_接口报错": "**可修复** — helper 抛异常，改数据层就能救活",
        "B_数据为空": "**可修复** — 接口通了但没数据，需换源或换实现",
        "B_数据部分为空": "**可修复** — 部分接口没数据",
        "C_条件太严": "真·策略问题 — 数据都拿到了，但没票通过筛选",
        "D_没调数据": "选股过程压根没调 helper，检查是不是硬编码/提前 return",
        "E_策略崩溃": "策略代码抛异常（原本被 bare except 吞掉）",
    }
    L.append("\n## 结论分布\n")
    L.append("| 判定 | 数量 | 含义 |")
    L.append("|---|---:|---|")
    for k, v in sorted(p["summary"].items(), key=lambda kv: -kv[1]):
        L.append("| %s | %d | %s |" % (k, v, meaning.get(k, "")))

    L.append("\n## helper 方法健康度\n")
    L.append("修哪个方法回报最大，看这张表。\n")
    L.append("| helper 方法 | 成功 | 返回空 | 报错 |")
    L.append("|---|---:|---:|---:|")
    for m, s in ranked[:25]:
        if s["err"] or s["empty"]:
            L.append("| `%s` | %d | %d | %d |" % (m, s["ok"], s["empty"], s["err"]))

    for cat in ["A_接口报错", "B_数据为空", "B_数据部分为空", "E_策略崩溃",
                "D_没调数据", "C_条件太严", "OK_正常"]:
        rows = [r for r in p["strategies"] if r["verdict"] == cat]
        if not rows:
            continue
        L.append("\n## %s（%d 个）\n" % (cat, len(rows)))
        L.append("| 策略 | 选出 | 调用 | 报错 | 空 | 说明 |")
        L.append("|---|---:|---:|---:|---:|---|")
        for r in sorted(rows, key=lambda x: -x["n_errors"]):
            L.append("| %s | %d | %d | %d | %d | %s |" % (
                r["name"], r["selected"], r["n_calls"], r["n_errors"],
                r["n_empty"], r["detail"][:90]))

    L.append("\n---\n")
    L.append("## 怎么用这份报告\n")
    L.append("1. 先看 **helper 方法健康度** —— 报错次数最多的那个方法，"
             "修好它能同时救活多个策略，性价比最高。\n")
    L.append("2. `A_接口报错` 和 `B_数据为空` 里的策略，**不是策略不行，是数据没到**，"
             "这是最容易拿回来的产能。\n")
    L.append("3. `C_条件太严` 才是真正需要讨论策略逻辑的部分 —— "
             "但放宽条件之前先想清楚，是不是在为了出信号而出信号。\n")
    L.append("4. `D_没调数据` 值得单独看一眼，很可能是写了一半的占位实现。\n")

    with open("output/data_diagnosis.md", "w", encoding="utf-8") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
