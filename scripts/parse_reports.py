# -*- coding: utf-8 -*-
"""
解析各基金 2026 年中期报告 PDF，抽取：
  - 期末净资产、期初净资产（规模变化）
  - 资产组合：权益投资 / 基金投资 / 银行存款 金额（占总资产比）
  - 目标基金明细（联接基金持有的目标 ETF 及占净值比）
  - 股指期货合约市值（名义敞口，注意公允价值被抵销为 0）
  - 份额净值增长率 / 业绩比较基准收益率（过去六个月，按份额分列）
  - 业绩比较基准定义文本（含息口径、汇率口径、指数权重）
  - 管理费 / 托管费 / 销售服务费年费率及"目标 ETF 部分是否豁免"条款

用法：
    python scripts/parse_reports.py            # 解析 data/pdf/*.pdf -> data/raw_reports.json
    python scripts/parse_reports.py 050025     # 只解析某只并打印完整 JSON（调试用）
"""
import json
import os
import re
import sys

from pypdf import PdfReader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDFDIR = os.path.join(ROOT, "data", "pdf")
TXT = os.path.join(ROOT, "data", "txt")
os.makedirs(TXT, exist_ok=True)

PAGE_RE = re.compile(r"<<<PAGE (\d+)>>>")
NUM = r"-?[\d,]+(?:\.\d+)?"
CN = r"[\u4e00-\u9fff]"


# --------------------------------------------------------------------------- #
# 文本工具
# --------------------------------------------------------------------------- #
def extract_text(pdf_path):
    """逐页抽取文本，保留 <<<PAGE n>>> 页码标记便于回溯。"""
    txt_path = os.path.join(TXT, os.path.basename(pdf_path).replace(".pdf", ".txt"))
    if os.path.exists(txt_path):
        return open(txt_path, encoding="utf-8").read()
    r = PdfReader(pdf_path)
    parts = ["<<<PAGE %d>>>\n" % (i + 1) + (p.extract_text() or "")
             for i, p in enumerate(r.pages)]
    s = "\n".join(parts)
    open(txt_path, "w", encoding="utf-8").write(s)
    return s


def heal(s):
    """修复 PDF 换行把数字/中文词劈开的问题。

    只在「确实是同一个数被劈开」时合并，避免把相邻两列数字（如
    「153,713,843.04 / 88,919,503.30」）误粘成一个。
    """
    s = re.sub(r"(\d[\d,]*)\s*\n\s*\.\s*(\d{1,2})(?![\d,])", r"\1.\2", s)   # 1,234\n.56
    s = re.sub(r"(\d[\d,]*\.)\s*\n\s*(\d{1,2})(?![\d,])", r"\1\2", s)       # 1,234.\n56
    s = re.sub(r"(" + CN + r")\s*\n\s*(" + CN + r")", r"\1\2", s)            # 中文被换行切断
    s = re.sub(r"(" + CN + r")\s*\n\s*(\d)", r"\1\2", s)                     # 中文\n数字
    s = re.sub(r"(\d)\s*\n\s*(" + CN + r")", r"\1\2", s)                     # 数字\n中文
    return s


def f(x):
    return None if x is None else float(str(x).replace(",", ""))


def flat(s):
    return re.sub(r"\s+", "", s)


def page_of(s, idx):
    m = None
    for mm in PAGE_RE.finditer(s, 0, idx):
        m = mm
    return int(m.group(1)) if m else None


def seg_after(s, kw, n, last=True):
    i = s.rfind(kw) if last else s.find(kw)
    return None if i < 0 else s[i:i + n]


def find_flat(s, pattern, start=0):
    """在「去掉所有空白」的副本上做正则搜索，返回原文中的位置。

    PDF 抽取常在词中间换行（"三、本期增减变动\\n额"），直接对原文搜关键词会漏。
    start 为原文下标，搜索从该位置之后开始。
    """
    fs = re.sub(r"\s+", "", s)
    idx = [i for i, ch in enumerate(s) if not ch.isspace()]
    off = 0
    if start > 0:
        import bisect
        off = bisect.bisect_left(idx, start)
    m = re.search(pattern, fs[off:])
    if not m:
        return -1
    return idx[off + m.start()]


# --------------------------------------------------------------------------- #
# 各字段抽取
# --------------------------------------------------------------------------- #
def parse_scale(s):
    """净资产变动表：本期期初 / 本期期末净资产（元）。

    行结构「实收基金 | 其他综合收益 | 未分配利润 | 净资产合计」，
    净资产合计是该行最后一个数字。用 find（第一处=本期），并用紧随其后的
    表头关键词切段，避免误取后续行数字。
    注意：PDF 会在「三、」和「本期增减变动额」之间换行，stop 必须用正则容错。
    """
    out = {}
    stops = {"nav_begin": r"三、本期增减变动额", "nav_end": r"上年度可比期间"}
    for key, kw in (("nav_begin", "本期期初净资产"), ("nav_end", "本期期末净资产")):
        i = find_flat(s, kw)
        if i < 0:
            continue
        j = find_flat(s, stops[key], start=i + len(kw))
        seg = s[i:j] if j > i else s[i:i + 400]
        nums = [f(x) for x in re.findall(NUM, seg)]
        nums = [x for x in nums if abs(x) > 1e6]
        out[key] = nums[-1] if nums else None
        out[key + "_page"] = page_of(s, i)
    return out


def parse_portfolio(s):
    """期末基金资产组合情况（金额 + 占基金总资产比例）

    表格里「金额」和「占比」常常被抽成连在一起（"182,381,840.7893.67"），
    因此金额固定按两位小数切、占比固定按 [1-2位].[2位] 切。
    """
    i = s.rfind("期末基金资产组合情况")
    if i < 0:
        return {}
    blk = s[i:i + 1400]
    res = {"_page": page_of(s, i)}
    PAIR = r"(" + r"[\d,]+\.\d{2}" + r")\s*(\d{1,3}\.\d{2})"
    for key, kw in (("equity", "权益投资"), ("fund_inv", "基金投资")):
        m = re.search(re.escape(kw) + r"\s*" + PAIR, blk)
        if m:
            res[key] = f(m.group(1))
            res[key + "_pct_total"] = f(m.group(2))
    for key, kw in (("cash", "银行存款和结算备付金合计"),
                    ("other_assets", "其他各项资产")):
        m = re.search(re.escape(kw) + r"\s*" + PAIR, blk)
        if m:
            res[key] = f(m.group(1))
            res[key + "_pct_total"] = f(m.group(2))
    m = re.search(r"(?<!备付金)合计\s*" + PAIR, blk)
    if m:
        res["total_assets"] = f(m.group(1))
    res["_raw"] = flat(blk[:900])
    return res


def parse_target_fund(s):
    """期末投资目标基金明细 / 前十名基金投资明细：名称 + 公允价值 + 占净值比"""
    for kw in ("期末投资目标基金明细", "前十名基金投资明细"):
        i = s.rfind(kw)
        if i < 0:
            continue
        blk = flat(s[i:i + 2200])
        if "未持有基金" in blk[:80]:
            return {"note": "本报告期末未持有基金", "rows": []}
        rows = []
        # 行尾为「公允价值 占净值比」，前面是名称/类型/管理人
        for m in re.finditer(r"(" + NUM + r")\s*(" + NUM + r")(?=[0-9]?[^\d]|$)", blk):
            v, pct = f(m.group(1)), f(m.group(2))
            if v is None or v < 1e6 or pct is None or pct > 100:
                continue
            head = blk[max(0, m.start() - 160):m.start()]
            nm = re.findall(r"([\u4e00-\u9fffA-Za-z0-9&.（）()\- ]{4,60}?(?:ETF|LOF|基金|Trust|Portfolio))",
                            head)
            rows.append({"name": (nm[-1].strip() if nm else head[-40:]).strip(),
                         "value": v, "pct_nav": pct})
        if rows:
            return {"rows": rows, "_raw": blk[:900]}
    return {"rows": []}


def parse_futures(s):
    """期末持有的期货合约情况：合约市值合计（名义敞口）

    当日无负债结算下期货公允价值与暂收款抵销为 0，名义敞口必须看「合约市值」。
    各家中报的期货表排版差异很大（有的把代码/名称拆成多行，有的把合计行与前一行
    合并），因此不用"按行切分"，而直接匹配每份合约行尾的
    「持仓量 合约市值 公允价值变动」三元组。
    """
    i = s.rfind("期末基金持有的期货合约情况")
    if i < 0:
        return {"market_value": 0.0, "rows": []}
    blk = s[i:i + 1200]
    for stop in ("减：", "注：", "注:"):
        j = blk.find(stop, 60)
        if j > 0:
            blk = blk[:j]
            break
    # PDF 会把长数字在小数位处换行（"241,628,766.8\n5"），此处只在期货块内做拼接
    blk = re.sub(r"(?<=\d)\s*\n\s*(?=\d)", "", blk)
    pat = re.compile(
        r"(?<![\d.])(\d{1,4}(?:\.\d{1,2})?)\s+"
        r"(\d{1,3}(?:,\d{3})+\.\d{2})\s+"
        r"(-?\d{1,3}(?:,\d{3})+\.\d{2})")
    rows, total = [], 0.0
    for m in pat.finditer(blk):
        lots, mv, pnl = f(m.group(1)), f(m.group(2)), f(m.group(3))
        if mv and mv > 1e5:
            rows.append({"lots": lots, "market_value": mv, "pnl": pnl,
                         "ctx": flat(blk[max(0, m.start() - 60):m.start()])[-40:]})
            total += mv
    return {"market_value": total, "rows": rows,
            "_raw": flat(blk[:600])}


CLASS_TAIL = re.compile(r"阶段\s*份额净值")


def clean_label(label):
    """剥掉「份额净值增长率及其与同期业绩比较基准收益率的比较」这类前缀，只留份额名。

    单一份额的 ETF 中报里没有份额名，此时返回空串，由调用方兜底为「主份额」。
    """
    s = flat(label)
    for sep in ("比较", "报告", "页", "④", "②", "①", "③", "。"):
        if sep in s:
            s = s.rsplit(sep, 1)[-1]
    return s.strip("：: ")


PERIOD_RE = re.compile(r"(过去三个月|过去六个月|过去一年|过去三年|过去五年|过去七年|过去十年)"
                       r"[^\n]{0,170}")


def parse_returns(s):
    """3.2.1 份额净值增长率及其与同期业绩比较基准收益率的比较（按份额分列）。

    份额名在「阶段」表头之前，长度不定，所以取「阶段」往前 120 字符再清洗，
    比用定长捕获组可靠。每个份额抓全部区间（三个月/六个月/一年/三年…），
    其中六个月同时提升为 nav_6m / bench_6m / diff_6m 便于下游直接取用。
    """
    i = s.find("份额净值增长率及其与同期业绩比较基准")
    if i < 0:
        return {}
    blk = s[i:i + 9000]

    def label_before(p):
        """「阶段」表头往前 120 字符，先砍掉上一行残留的百分数，再清洗。"""
        raw = blk[max(0, p - 120):p]
        raw = raw.rsplit("%", 1)[-1]
        return clean_label(raw) or "主份额"

    marks = [(m.start(), label_before(m.start())) for m in CLASS_TAIL.finditer(blk)]
    out = {}
    for m in PERIOD_RE.finditer(blk):
        p = m.start()
        label = None
        for mp, name in marks:
            if mp < p:
                label = name
        if not label:
            continue
        nums = re.findall(r"-?\d+\.\d+%", m.group(0))
        if len(nums) < 5:
            continue
        rec = out.setdefault(label, {"periods": {}})
        rec["periods"][m.group(1)] = {
            "nav": float(nums[0].rstrip("%")),
            "std": float(nums[1].rstrip("%")),
            "bench": float(nums[2].rstrip("%")),
            "diff": float(nums[4].rstrip("%")),
        }
    for label, rec in out.items():
        p6 = rec["periods"].get("过去六个月")
        if p6:
            rec["nav_6m"] = p6["nav"]
            rec["bench_6m"] = p6["bench"]
            rec["diff_6m"] = p6["diff"]
    return {k: v for k, v in out.items() if "nav_6m" in v}


def parse_benchmark_def(s):
    """业绩比较基准的完整定义文本。

    必须跳过 3.2.1 表格里「业绩比较基准收益率为：5.86%」这类叙述，
    只保留真正的基准定义（以 标普/标准普尔/经/95 等开头）。
    """
    for m in re.finditer("业绩比较基准", s):
        tail = flat(s[m.end():m.end() + 220]).lstrip("：:为是 ")
        if tail.startswith(("收益率", "增长率", "收益")):
            continue
        if not re.match(r"^[（(]?(标普|标准普尔|经|S&P|95|90|100%|\d)", tail):
            continue
        txt = flat(s[m.start():m.end() + 260])
        for stop in ("。", "风险收益特征", "3.2", "本基金主要采用", "投资目标",
                     "本基金为", "管理人报告", "§", "<<<PAGE"):
            j = txt.find(stop, 6)
            if j > 0:
                txt = txt[:j]
        return txt[:200]
    return None


RATE_PATS = (
    r"([\d.]+)%\s*的?\s*年费率",
    r"年费率\s*为?\s*([\d.]+)%",
)


def _last_rate(note):
    """取注里当前适用的年费率。

    优先级：显式「由 A% 调整为 B%」→「A%/B%」并列取后者 → 最后一个「X%的年费率」。
    """
    m = list(re.finditer(r"由\s*([\d.]+)%\s*(?:年费率)?\s*(?:调整)?为\s*([\d.]+)%", note))
    if m:
        return float(m[-1].group(2))
    m = list(re.finditer(r"([\d.]+)%\s*/\s*([\d.]+)%", note))
    if m:
        return float(m[-1].group(2))
    rates = [float(x) for pat in RATE_PATS for x in re.findall(pat, note)]
    return rates[-1] if rates else None


def _fee_note(s, kw, span=2200):
    i = s.rfind(kw)
    if i < 0:
        return None
    blk = flat(s[i:i + span])
    j = blk.find("注")
    note = blk[j:] if j > 0 else blk
    # 截断到下一个附注小节，避免串到托管费/销售服务费
    m = re.search(r"6\.4\.\d+\.\d+\.\d+", note[4:])
    if m:
        note = note[:m.start() + 4]
    return note


def parse_fees(s):
    """管理费 / 托管费 / 销售服务费 年费率 + 是否对目标 ETF 部分豁免"""
    out = {}
    note = _fee_note(s, "当期发生的基金应支付的管理费")
    if note:
        out["mgmt_rate"] = _last_rate(note)
        out["mgmt_waiver"] = bool(
            re.search(r"目标\s*ETF\s*部分.{0,12}不收取管理费", note)
            or re.search(r"扣除.{0,60}目标\s*ETF", note))
        out["mgmt_note"] = note[:300]
    note = _fee_note(s, "当期发生的基金应支付的托管费")
    if note:
        out["cust_rate"] = _last_rate(note)
        out["cust_waiver"] = bool(
            re.search(r"目标\s*ETF\s*部分.{0,12}不收取托管费", note)
            or re.search(r"扣除.{0,60}目标\s*ETF", note))
        out["cust_note"] = note[:300]
    note = _fee_note(s, "销售服务费")
    if note:
        out["sales_note"] = note[:260]
        m = re.search(r"([\d.]+)%", note)
        out["sales_rate"] = float(m.group(1)) if m else None
    return out


def parse_one(code, tag="semi"):
    path = os.path.join(PDFDIR, "%s_%s.pdf" % (code, tag))
    if not os.path.exists(path):
        return None
    s = heal(extract_text(path))
    rec = {"code": code, "tag": tag, "pdf": "data/pdf/%s_%s.pdf" % (code, tag)}
    rec.update(parse_scale(s))
    rec["portfolio"] = parse_portfolio(s)
    rec["target_funds"] = parse_target_fund(s)
    rec["futures"] = parse_futures(s)
    rec["returns"] = parse_returns(s)
    rec["benchmark_def"] = parse_benchmark_def(s)
    rec["fees"] = parse_fees(s)
    m = re.search(r"本报告期自\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日起至\s*"
                  r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日止", s)
    rec["period"] = ("%s-%02d-%02d~%s-%02d-%02d" % tuple(int(x) for x in m.groups())) if m else None
    return rec


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(parse_one(sys.argv[1]), ensure_ascii=False, indent=2))
        sys.exit()

    idx = json.load(open(os.path.join(ROOT, "data", "reports_index.json"), encoding="utf-8"))
    allrec = {}
    for it in idx:
        for tag in ("semi", "annual"):
            if tag in it:
                r = parse_one(it["code"], tag)
                if r:
                    allrec["%s_%s" % (it["code"], tag)] = r
    json.dump(allrec, open(os.path.join(ROOT, "data", "raw_reports.json"), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=2)
    print("saved -> data/raw_reports.json  (%d reports)" % len(allrec))

    print("\n%-8s %16s %8s %8s %14s %8s %8s %8s  %s" % (
        "code", "NAV期末", "权益%", "基金%", "期货市值", "期货%", "净值6m", "基准6m", "份额"))
    for k, r in allrec.items():
        if not k.endswith("semi"):
            continue
        nav = r.get("nav_end") or 0
        pf = r.get("portfolio", {})
        fu = r.get("futures", {}).get("market_value") or 0
        rets = r.get("returns", {})
        first = list(rets.items())[0] if rets else ("-", {})
        print("%-8s %16.0f %8s %8s %14.0f %8s %8s %8s  %s" % (
            r["code"], nav,
            "%.2f" % (100 * (pf.get("equity") or 0) / nav) if nav else "-",
            "%.2f" % (100 * (pf.get("fund_inv") or 0) / nav) if nav else "-",
            fu, "%.2f" % (100 * fu / nav) if nav else "-",
            first[1].get("nav_6m", "-"), first[1].get("bench_6m", "-"),
            " / ".join(rets.keys())))
