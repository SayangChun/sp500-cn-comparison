# -*- coding: utf-8 -*-
"""批量获取中国跟踪标普500的基金定期报告 PDF（数据源：天天基金公开接口）"""
import json, os, re, time, urllib.request, urllib.parse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDFDIR = os.path.join(ROOT, "data", "pdf")
os.makedirs(PDFDIR, exist_ok=True)

# 基金池：同一产品的 A 类份额代码作为主代码（A/C/E 共用同一份定期报告）
POOL = [
    # 场内 ETF
    ("513500", "博时标普500ETF",                    "场内ETF"),
    ("159612", "国泰标普500ETF",                    "场内ETF"),
    ("159655", "华夏标普500ETF",                    "场内ETF"),
    ("513650", "南方标普500ETF",                    "场内ETF"),
    # 场外
    ("050025", "博时标普500ETF联接A",               "场外联接"),
    ("161125", "易方达标普500指数A(LOF)",           "场外QDII-LOF"),
    ("007721", "天弘标普500发起(QDII-FOF)A",        "场外QDII-FOF"),
    ("017028", "国泰标普500ETF发起联接A",           "场外联接"),
    ("017641", "摩根标普500指数(QDII)A",            "场外QDII"),
    ("018064", "华夏标普500ETF发起式联接A",         "场外联接"),
    # 等权重（单列，不与市值加权混排）
    ("096001", "大成标普500等权重指数A",            "场外等权重"),
    ("519981", "长信标普100等权重指数",             "场外等权重"),
]

def get(url, referer, binary=False, retry=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
    for i in range(retry):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read() if binary else r.read().decode("utf-8", "ignore")
        except Exception as e:
            if i == retry - 1:
                raise
            time.sleep(2)

def list_reports(code):
    url = ("https://api.fund.eastmoney.com/f10/JJGG?callback=cb&fundcode=%s"
           "&pageIndex=1&pageSize=40&type=3" % code)
    txt = get(url, "https://fundf10.eastmoney.com/jjgg_%s_2.html" % code)
    m = re.search(r"cb\((.*)\)\s*$", txt, re.S)
    return json.loads(m.group(1)).get("Data", []) if m else []

def pick(data, keyword):
    for it in data:
        if keyword in it["TITLE"]:
            return it
    return None

out = []
for code, name, kind in POOL:
    rec = {"code": code, "name": name, "kind": kind}
    try:
        data = list_reports(code)
    except Exception as e:
        rec["error"] = "list_failed: %s" % e
        out.append(rec); print(code, name, rec.get("error")); continue
    for tag, kw in (("semi", "2026年中期报告"), ("annual", "2025年年度报告"),
                    ("q2", "2026年第2季度报告")):
        it = pick(data, kw)
        if not it:
            continue
        rec[tag] = {"title": it["TITLE"], "id": it["ID"], "date": it["PUBLISHDATEDesc"]}
        if tag in ("semi", "annual"):
            fn = os.path.join(PDFDIR, "%s_%s.pdf" % (code, tag))
            if not os.path.exists(fn) or os.path.getsize(fn) < 20000:
                pdf = get("https://pdf.dfcfw.com/pdf/H2_%s_1.pdf" % it["ID"],
                          "https://fundf10.eastmoney.com/", binary=True)
                open(fn, "wb").write(pdf)
                time.sleep(0.6)
            rec[tag]["file"] = "data/pdf/%s_%s.pdf" % (code, tag)
    out.append(rec)
    print(code, name, "|", "semi:", rec.get("semi", {}).get("date"), "|", rec.get("error", ""))

json.dump(out, open(os.path.join(ROOT, "data", "reports_index.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("saved -> data/reports_index.json")
