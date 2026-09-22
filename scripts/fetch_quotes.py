# -*- coding: utf-8 -*-
"""
抓取场内 ETF 的日收盘价与关键日期份额净值，用于计算场内溢价率。

数据源：
  - 场内日 K：腾讯行情 web.ifzq.gtimg.cn（已与东方财富 push2his 逐点交叉验证一致）
  - 份额净值：天天基金 api.fund.eastmoney.com/f10/lsjz

输出：
  - data/quotes_cache.json  场内日收盘价
  - data/nav_per_share.json 2025-12-31 / 2026-06-29 / 2026-06-30 的份额净值

用法：python scripts/fetch_quotes.py
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
DATES = ["2025-12-31", "2026-06-29", "2026-06-30"]


def curl_json(url, referer="", retry=4):
    """统一走 curl：push2his 等接口会拒绝 urllib/requests 的 TLS 指纹。"""
    last = None
    for i in range(retry):
        try:
            cmd = ["curl", "-s", "--max-time", "40", "-A", UA]
            if referer:
                cmd += ["-H", "Referer: " + referer]
            out = subprocess.run(cmd + [url], capture_output=True, check=True).stdout
            return json.loads(out.decode("utf-8", "ignore"))
        except Exception as e:      # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def prices():
    out = {}
    for code, sym in TX.items():
        d = curl_json("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,"
                      "day,2025-12-15,2026-07-10,200," % sym)
        node = (d.get("data") or {}).get(sym) or {}
        ks = node.get("day") or node.get("qfqday") or []
        out[code] = {r[0]: float(r[2]) for r in ks}     # [日期, 开, 收, 高, 低, ...]
        time.sleep(0.3)
    return out


def nav_per_share():
    out = {}
    for code in TX:
        rows = {}
        for pn in range(1, 20):
            d = curl_json("https://api.fund.eastmoney.com/f10/lsjz?fundCode=%s&pageIndex=%d"
                          "&pageSize=20" % (code, pn),
                          "https://fundf10.eastmoney.com/jjjz_%s.html" % code)
            L = (d.get("Data") or {}).get("LSJZList") or []
            if not L:
                break
            for x in L:
                if x.get("DWJZ"):
                    rows[x["FSRQ"]] = float(x["DWJZ"])
            if min(x["FSRQ"] for x in L) < "2025-12-25":
                break
            time.sleep(0.2)
        out[code] = {}
        for dt in DATES:
            ks = sorted(k for k in rows if k <= dt)
            out[code]["nav_" + dt.replace("-", "")] = rows[ks[-1]] if ks else None
        time.sleep(0.3)
    return out


if __name__ == "__main__":
    p = prices()
    json.dump(p, open(os.path.join(ROOT, "data", "quotes_cache.json"), "w",
                      encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved -> data/quotes_cache.json  (%s)" % {k: len(v) for k, v in p.items()})
    n = nav_per_share()
    json.dump(n, open(os.path.join(ROOT, "data", "nav_per_share.json"), "w",
                      encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved -> data/nav_per_share.json")
    print(json.dumps(n, ensure_ascii=False, indent=2))
