# -*- coding: utf-8 -*-
"""
生成"最新快照"：截至最近一个交易日（2026-10-22）的净值、场内价、溢价、申购状态。

与中报数据的分工：
  - 参与率 / 加权综合费率 / 规模 → 仍取 2026 中报（Q3 季报未出，这是最新可得）
  - 多期收益 / 场内溢价 / 申购状态 → 用本脚本滚动到最新交易日

输出 data/latest.json
"""
import json
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

TX = {"513500": "sh513500", "159612": "sz159612",
      "159655": "sz159655", "513650": "sh513650"}

# 场内 ETF + 场外 A 类（申购状态用）
SUB_CODES = ["513500", "159612", "159655", "513650", "050025",
             "161125", "007721", "017028", "017641", "018064"]


def curl_json(url, referer="", retry=4):
    last = None
    for i in range(retry):
        try:
            cmd = ["curl", "-s", "--max-time", "45", "-A", UA]
            if referer:
                cmd += ["-H", "Referer: " + referer]
            out = subprocess.run(cmd + [url], capture_output=True, check=True).stdout
            return json.loads(out.decode("utf-8", "ignore"))
        except Exception as e:              # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def prices():
    out = {}
    for code, sym in TX.items():
        d = curl_json("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,"
                      "day,2025-10-01,2026-12-31,400," % sym)
        node = (d.get("data") or {}).get(sym) or {}
        ks = node.get("day") or node.get("qfqday") or []
        out[code] = {r[0]: float(r[2]) for r in ks}
        time.sleep(0.35)
    return out


def subscribe_status():
    out = {}
    for c in SUB_CODES:
        try:
            d = curl_json("https://api.fund.eastmoney.com/f10/lsjz?fundCode=%s&pageIndex=1"
                          "&pageSize=1" % c, "https://fundf10.eastmoney.com/jjjz_%s.html" % c)
            L = (d.get("Data") or {}).get("LSJZList") or []
            if L:
                out[c] = {"date": L[0]["FSRQ"], "nav": L[0]["DWJZ"],
                          "sgzt": L[0].get("SGZT"), "shzt": L[0].get("SHZT")}
        except Exception:                   # noqa: BLE001
            pass
        time.sleep(0.25)
    return out


def main():
    hist = json.load(open(os.path.join(ROOT, "data", "nav_history.json"), encoding="utf-8"))
    perf = json.load(open(os.path.join(ROOT, "data", "rolling_perf.json"), encoding="utf-8"))
    an = json.load(open(os.path.join(ROOT, "data", "analysis.json"), encoding="utf-8"))
    px = prices()
    subs = subscribe_status()
    asof = max(r["asof"] for r in perf.values())

    prods = {}
    for code, rec in an["products"].items():
        p = perf.get(code, {})
        # 溢价必须用「单位净值」算，不能用累计净值（有分红的产品两者差很远）
        ks = sorted(k for k in hist.get(code, {}) if k <= asof)
        nav_unit = hist[code][ks[-1]]["nav"] if ks else None
        entry = {"periods": p.get("periods", {}), "nav": nav_unit,
                 "asof": p.get("asof"), "sgzt": (subs.get(code) or {}).get("sgzt"),
                 "penetrated": rec["penetrated_pct"],
                 "fee": rec["comprehensive_fee"], "nav_scale": rec["nav_end"]}
        if code in px and px[code] and nav_unit:
            kk = sorted(k for k in px[code] if k <= asof)
            if kk:
                k = kk[-1]
                entry.update(price=px[code][k], price_date=k,
                             premium=(px[code][k] / nav_unit - 1) * 100.0)
                entry["premium_adj_pct"] = rec["penetrated_pct"] / (1 + entry["premium"] / 100.0)
                # 一年前同口径，用于展示溢价变化
                k1y = sorted(k for k in px[code] if k <= "2025-10-22")
                kk1y = sorted(k for k in hist.get(code, {}) if k <= "2025-10-22")
                if k1y and kk1y:
                    n1y = hist[code][kk1y[-1]]["nav"]
                    entry["price_1y"] = px[code][k1y[-1]]
                    entry["nav_1y"] = n1y
                    entry["premium_1y"] = (px[code][k1y[-1]] / n1y - 1) * 100.0
                    entry["premium_change"] = entry["premium"] - entry["premium_1y"]
        prods[code] = entry

    out = {"asof": asof, "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
           "products": prods,
           "subscribe": subs}
    json.dump(out, open(os.path.join(ROOT, "data", "latest.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)

    print("基准日 %s\n" % asof)
    print("%-9s %8s %8s %8s %8s %8s %9s %10s" % (
        "code", "近一月", "近三月", "近半年", "近一年", "近三年", "溢价", "有效参率"))
    for code, e in sorted(prods.items(), key=lambda x: -x[1]["penetrated"]):
        p = e["periods"]
        f = lambda k: ("%7.2f%%" % p[k]["nav"]) if k in p else "       —"
        prem = ("%+7.2f%%" % e["premium"]) if "premium" in e else "       —"
        adj = ("%9.2f%%" % e["premium_adj_pct"]) if "premium_adj_pct" in e else "        —"
        print("%-9s %s %s %s %s %s %s %s" % (
            code, f("过去一个月"), f("过去三个月"), f("过去六个月"),
            f("过去一年"), f("过去三年"), prem, adj))
    print("\nsaved -> data/latest.json")


if __name__ == "__main__":
    main()
