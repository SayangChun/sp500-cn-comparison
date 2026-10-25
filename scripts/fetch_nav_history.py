# -*- coding: utf-8 -*-
"""
抓取各产品 A 类份额的完整净值历史，并滚动计算「截至最新交易日」的多期收益。

为什么不用中报里的「过去六个月/一年/三年」：
  那些窗口的终点被钉死在 2026-06-30。中报半年才更新一次，要反映"最新情况"
  就必须用日净值自己滚动窗口。

数据源：`fund.eastmoney.com/pingzhongdata/{code}.js`
  一次请求就带回全部历史（单位净值 + 累计净值），比按页翻 lsjz 快几十倍。
  累计净值用于复权计算，能正确处理分红。

用法：python scripts/fetch_nav_history.py
输出：data/nav_history.json（原始序列）、data/rolling_perf.json（多期收益）
"""
import json
import os
import re
import subprocess
import time
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# A 类主代码（与 analyze.py 的 PRODUCTS 保持一致）
CODES = ["513500", "159612", "159655", "513650", "050025",
         "161125", "007721", "017028", "017641", "018064"]

# 需要滚动的窗口：名称 -> 天数
WINDOWS = [("过去三个月", 91), ("过去六个月", 182), ("过去一年", 365),
           ("过去三年", 1095), ("过去五年", 1825)]


def curl(url, referer):
    for i in range(4):
        try:
            out = subprocess.run(
                ["curl", "-s", "--max-time", "40", "-A", UA, "-H", "Referer: " + referer, url],
                capture_output=True, check=True).stdout
            return out.decode("utf-8", "ignore")
        except Exception:                   # noqa: BLE001
            time.sleep(1.5 * (i + 1))
    return ""


def parse_series(txt, name):
    m = re.search(name + r"\s*=\s*(\[.*?\]);", txt, re.S)
    if not m:
        return []
    try:
        return json.loads(m.group(1))
    except Exception:                       # noqa: BLE001
        return []


def fetch_one(code):
    txt = curl("https://fund.eastmoney.com/pingzhongdata/%s.js?v=%s"
               % (code, datetime.now().strftime("%Y%m%d%H%M")),
               "https://fund.eastmoney.com/%s.html" % code)
    nav = parse_series(txt, "Data_netWorthTrend")        # [{x: 毫秒时间戳, y: 单位净值}]
    acc = parse_series(txt, "Data_ACWorthTrend")         # [[毫秒时间戳, 累计净值]]
    out = {}
    for x in nav:
        d = datetime.fromtimestamp(x["x"] / 1000, tz=timezone.utc).astimezone().date()
        out.setdefault(str(d), {})["nav"] = x["y"]
    for pair in acc:
        if len(pair) >= 2:
            d = datetime.fromtimestamp(pair[0] / 1000, tz=timezone.utc).astimezone().date()
            out.setdefault(str(d), {})["acc"] = pair[1]
    # 补齐缺失的累计净值（用单位净值兜底）
    for d, v in out.items():
        v.setdefault("acc", v.get("nav"))
    return dict(sorted(out.items()))


def value_on(series, target):
    """取 target 当天或之前最近一个交易日的 (日期, 累计净值)。"""
    ks = [k for k in series if k <= target]
    if not ks:
        return None, None
    k = ks[-1]
    return k, series[k]["acc"]


def main():
    hist, perf = {}, {}
    asof = None
    for code in CODES:
        s = fetch_one(code)
        if not s:
            print("  ! %s 抓取失败" % code)
            continue
        hist[code] = s
        last = list(s)[-1]
        asof = last if asof is None else max(asof, last)
        print("  %-8s %4d 个交易日  %s ~ %s" % (code, len(s), list(s)[0], last))
        time.sleep(0.4)

    json.dump(hist, open(os.path.join(ROOT, "data", "nav_history.json"), "w",
                         encoding="utf-8"), ensure_ascii=False)

    # 统一以所有产品里最新的交易日为基准日
    end = date.fromisoformat(asof)
    for code, s in hist.items():
        rec = {"asof": asof, "periods": {}}
        _, v_end = value_on(s, asof)
        for name, days in WINDOWS:
            start = end - timedelta(days=days)
            d0, v0 = value_on(s, str(start))
            if v0 and v_end:
                rec["periods"][name] = {
                    "nav": (v_end / v0 - 1) * 100.0,
                    "start": d0,
                    "days": days,
                }
        # 近一个月单独给（评分不用，展示用）
        d0, v0 = value_on(s, str(end - timedelta(days=30)))
        if v0 and v_end:
            rec["periods"]["过去一个月"] = {"nav": (v_end / v0 - 1) * 100.0,
                                          "start": d0, "days": 30}
        rec["nav_end"] = v_end
        perf[code] = rec

    json.dump(perf, open(os.path.join(ROOT, "data", "rolling_perf.json"), "w",
                         encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n基准日 %s" % asof)
    print("%-9s %8s %8s %8s %8s" % ("code", "近一月", "近三月", "近半年", "近一年"))
    for code, r in perf.items():
        p = r["periods"]
        f = lambda k: ("%.2f%%" % p[k]["nav"]) if k in p else "—"
        print("%-9s %8s %8s %8s %8s" % (code, f("过去一个月"), f("过去三个月"),
                                        f("过去六个月"), f("过去一年")))
    print("\nsaved -> data/nav_history.json, data/rolling_perf.json")


if __name__ == "__main__":
    main()
