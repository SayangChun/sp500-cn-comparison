# -*- coding: utf-8 -*-
"""
把打分与穿透结果渲染成纯 SVG 图表（无外部依赖、可离线、可嵌 GitHub Markdown）。

所有函数返回完整 <svg> 字符串；write_files() 会同时落盘到 docs/img/ 供 README 引用。

用法：python scripts/charts.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMGDIR = os.path.join(ROOT, "docs", "img")

INK, INK2, INK3 = "#1a1d21", "#4a5058", "#7c848e"
GRID, AXIS, PANEL = "#eef1f4", "#d8dde3", "#ffffff"
FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',"
        "'Hiragino Sans GB','Microsoft YaHei',sans-serif")

DIM_COLORS = [
    ("长期收益兑现", "#2563eb"),
    ("真实敞口", "#0d9488"),
    ("持有成本", "#d99a2b"),
    ("规模与稳定", "#6d28d9"),
    ("买入摩擦", "#94a3b8"),
]
TYPE_COLORS = {
    "场内ETF": "#2563eb", "场外ETF联接": "#0d9488",
    "场外QDII-FOF": "#d99a2b", "场外QDII-LOF": "#b45309",
    "场外QDII直投": "#6d28d9",
}


def _svg(w, h, title, desc, body):
    return ('<svg viewBox="0 0 %d %d" width="100%%" role="img" '
            'xmlns="http://www.w3.org/2000/svg" '
            'style="font-family:%s;background:%s">'
            '<title>%s</title><desc>%s</desc>%s</svg>'
            % (w, h, FONT, PANEL, title, desc, body))


def _txt(x, y, s, size=12, fill=INK2, anchor="start", weight=400):
    return ('<text x="%.1f" y="%.1f" font-size="%d" fill="%s" text-anchor="%s" '
            'font-weight="%d">%s</text>' % (x, y, size, fill, anchor, weight, s))


# --------------------------------------------------------------------------- #
def rank_stacked(rows, w=960):
    """总分堆叠条形图：每根条拆成五个维度的贡献。"""
    n = len(rows)
    top, rh, gap = 46, 30, 7
    lab_w, val_w = 112, 62
    plot = w - lab_w - val_w - 16
    h = top + n * (rh + gap) + 18
    b = [_txt(0, 16, "总分构成：五个维度各自的贡献（满分 100）", 14, INK, weight=500)]

    # 图例
    lx = 0
    for name, col in DIM_COLORS:
        b.append('<rect x="%d" y="26" width="10" height="10" rx="2" fill="%s"/>' % (lx, col))
        b.append(_txt(lx + 14, 35, name, 11.5, INK2))
        lx += 14 + len(name) * 12.2 + 18

    for i in range(0, 101, 20):
        x = lab_w + plot * i / 100.0
        b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1"/>'
                 % (x, top - 6, x, top + n * (rh + gap) - gap + 2, GRID))
        b.append(_txt(x, top - 11, str(i), 11, INK3, "middle"))

    for idx, r in enumerate(rows):
        y = top + idx * (rh + gap)
        bd = r["score_breakdown"]
        b.append(_txt(lab_w - 10, y + rh / 2 + 4.5, r["short"], 12, INK, "end", 500))
        x = lab_w
        for name, col in DIM_COLORS:
            v = bd[name]
            seg = plot * v / 100.0
            if seg > 0.5:
                b.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s"/>'
                         % (x, y, seg, rh, col))
                if seg > 26:
                    b.append(_txt(x + seg / 2, y + rh / 2 + 4.5, "%.1f" % v, 11,
                                  "#ffffff", "middle", 500))
            x += seg
        b.append(_txt(lab_w + plot * r["score"] / 100.0 + 8, y + rh / 2 + 5,
                      "%.2f" % r["score"], 13, INK, "start", 500))
    return _svg(w, h, "标普500标的量化打分总分构成",
                "十只产品的总分拆解为长期收益兑现、真实敞口、持有成本、规模与稳定、买入摩擦五个维度",
                "".join(b))


def return_fee_scatter(rows, w=960, h=440):
    """三年收益 × 加权综合费率 气泡图（气泡面积≈期末规模）。"""
    ml, mr, mt, mb = 74, 34, 52, 62
    pw, ph = w - ml - mr, h - mt - mb
    xs = [r["fee"] for r in rows]
    ys = [r["r3"] for r in rows]
    x0, x1 = min(xs) - 0.05, max(xs) + 0.05
    y0, y1 = min(ys) - 2.2, max(ys) + 2.2

    def px(v):
        return ml + pw * (v - x0) / (x1 - x0)

    def py(v):
        return mt + ph * (1 - (v - y0) / (y1 - y0))

    import math
    navs = [r["nav"] for r in rows]
    lo, hi = math.log10(min(navs)), math.log10(max(navs))

    def rad(nav):
        t = (math.log10(nav) - lo) / (hi - lo) if hi > lo else 0.5
        return 7 + 13 * t

    b = [_txt(0, 16, "三年收益 × 加权综合费率（气泡面积≈期末规模）", 14, INK, weight=500)]
    b.append(_txt(0, 34, "左上角最优：费低、收益高；右下角最差。同类产品之间的差距，主要来自这一张图。",
                  11.5, INK3))

    for i in range(6):
        v = y0 + (y1 - y0) * i / 5.0
        y = py(v)
        b.append('<line x1="%d" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                 % (ml, y, w - mr, y, GRID))
        b.append(_txt(ml - 8, y + 4, "%.0f%%" % v, 11, INK3, "end"))
    for i in range(6):
        v = x0 + (x1 - x0) * i / 5.0
        x = px(v)
        b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                 % (x, mt, x, mt + ph, GRID))
        b.append(_txt(x, mt + ph + 18, "%.2f%%" % v, 11, INK3, "middle"))

    b.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1"/>'
             % (ml, mt + ph, w - mr, mt + ph, AXIS))
    b.append(_txt(ml + pw / 2, h - 16, "加权综合费率（越低越好 →）", 12, INK2, "middle"))
    b.append('<text x="%d" y="%d" font-size="12" fill="%s" text-anchor="middle" '
             'transform="rotate(-90 %d %d)">过去三年净值增长率</text>'
             % (16, mt + ph / 2, INK2, 16, mt + ph / 2))

    # 平均线
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1" '
             'stroke-dasharray="4 4"/>' % (px(mx), mt, px(mx), mt + ph, "#c9cfd6"))
    b.append('<line x1="%d" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1" '
             'stroke-dasharray="4 4"/>' % (ml, py(my), w - mr, py(my), "#c9cfd6"))
    b.append(_txt(px(mx) + 6, mt + 14, "平均费率 %.2f%%" % mx, 11, INK3))
    b.append(_txt(w - mr - 6, py(my) - 7, "平均收益 %.1f%%" % my, 11, INK3, "end"))

    for r in sorted(rows, key=lambda x: -x["nav"]):
        col = TYPE_COLORS.get(r["kind"], INK3)
        cx, cy = px(r["fee"]), py(r["r3"])
        b.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="0.16" '
                 'stroke="%s" stroke-width="1.6"/>' % (cx, cy, rad(r["nav"]), col, col))
        dy = -rad(r["nav"]) - 6
        anchor = "middle"
        if cx > w - mr - 90:
            anchor, cx = "end", cx + rad(r["nav"]) - 2
        b.append(_txt(cx, cy + dy, r["short"], 11.5, INK, anchor, 500))

    lx = ml
    for kind, col in TYPE_COLORS.items():
        if not any(r["kind"] == kind for r in rows):
            continue
        b.append('<circle cx="%d" cy="%d" r="5" fill="%s" fill-opacity="0.3" stroke="%s"/>'
                 % (lx + 5, mt + ph + 40, col, col))
        lab = kind.replace("场外", "").replace("场内", "场内 ")
        b.append(_txt(lx + 15, mt + ph + 44, lab, 11, INK2))
        lx += 22 + len(lab) * 12
    return _svg(w, h, "三年收益与加权综合费率散点图",
                "横轴为加权综合费率，纵轴为过去三年净值增长率，气泡大小代表期末规模", "".join(b))


def period_grouped(rows, w=960, h=400):
    """多期年化收益分组条形图：三年 / 一年 / 半年（年化）。"""
    ml, mr, mt, mb = 56, 20, 58, 76
    pw, ph = w - ml - mr, h - mt - mb
    series = [("三年（年化）", "ann3", "#2563eb"),
              ("一年", "ann1", "#0d9488"),
              ("半年（年化）", "ann6", "#d99a2b")]
    vals = [r[k] for r in rows for _, k, _ in series if r.get(k) is not None]
    y0, y1 = min(vals) - 1.2, max(vals) + 1.2

    def py(v):
        return mt + ph * (1 - (v - y0) / (y1 - y0))

    b = [_txt(0, 16, "多期年化收益对比（看长期，别看半年）", 14, INK, weight=500)]
    b.append(_txt(0, 34, "场内四只 ETF 在三年维度上稳定领先；场外只有博时联接、易方达 LOF 接近。",
                  11.5, INK3))
    lx = 0
    for name, _k, col in series:
        b.append('<rect x="%d" y="44" width="10" height="10" rx="2" fill="%s"/>' % (lx, col))
        b.append(_txt(lx + 14, 53, name, 11.5, INK2))
        lx += 14 + len(name) * 12.5 + 20

    for i in range(5):
        v = y0 + (y1 - y0) * i / 4.0
        y = py(v)
        b.append('<line x1="%d" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                 % (ml, y, w - mr, y, GRID))
        b.append(_txt(ml - 8, y + 4, "%.0f%%" % v, 11, INK3, "end"))

    gw = pw / len(rows)
    bw = min(16.0, gw / 4.4)
    for i, r in enumerate(rows):
        gx = ml + gw * i
        for j, (_name, key, col) in enumerate(series):
            v = r.get(key)
            if v is None:
                continue
            x = gx + gw / 2 + (j - 1) * (bw + 2) - bw / 2
            y = py(v)
            b.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="1.5" fill="%s"/>'
                     % (x, y, bw, mt + ph - y, col))
            if j == 0:
                b.append(_txt(x + bw / 2, y - 5, "%.1f" % v, 10.5, INK2, "middle"))
        b.append('<text x="%.1f" y="%.1f" font-size="11.5" fill="%s" text-anchor="end" '
                 'transform="rotate(-32 %.1f %.1f)">%s</text>'
                 % (gx + gw / 2, mt + ph + 14, INK2, gx + gw / 2, mt + ph + 14, r["short"]))
    b.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1"/>'
             % (ml, mt + ph, w - mr, mt + ph, AXIS))
    return _svg(w, h, "多期年化收益分组条形图",
                "十只产品在过去三年、一年、半年的年化净值增长率对比", "".join(b))


def exposure_fee(rows, w=960):
    """穿透后参与率 与 加权综合费率 的双面板条形图。"""
    n = len(rows)
    top, rh, gap = 50, 24, 6
    lab_w = 112
    panel = (w - lab_w - 40) / 2.0
    h = top + n * (rh + gap) + 34
    b = [_txt(0, 16, "真实敞口 与 持有成本（两条都要看）", 14, INK, weight=500)]
    b.append(_txt(0, 34, "左：穿透后参与率，越高说明越多钱真的进了指数；右：加权综合费率，越低越好。",
                  11.5, INK3))

    x1, x2 = lab_w, lab_w + panel + 40
    b.append(_txt(x1, top - 10, "穿透后参与率", 12, INK, weight=500))
    b.append(_txt(x2, top - 10, "加权综合费率", 12, INK, weight=500))
    for i in range(0, 101, 20):
        x = x1 + panel * i / 100.0
        b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                 % (x, top, x, top + n * (rh + gap) - gap, GRID))
    for i in range(0, 6):
        x = x2 + panel * i / 5.0
        b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                 % (x, top, x, top + n * (rh + gap) - gap, GRID))
        b.append(_txt(x, top + n * (rh + gap) + 14, "%.2f%%" % (i * 0.25), 11, INK3, "middle"))

    for idx, r in enumerate(rows):
        y = top + idx * (rh + gap)
        b.append(_txt(lab_w - 10, y + rh / 2 + 4.5, r["short"], 12, INK, "end", 500))
        v = r["penetrated"]
        wp = panel * v / 100.0
        col = TYPE_COLORS.get(r["kind"], "#2563eb")
        b.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="2" fill="%s"/>'
                 % (x1, y, wp, rh, col))
        b.append(_txt(x1 + wp + 7, y + rh / 2 + 4.5, "%.2f%%" % v, 11, INK2))
        f = r["fee"]
        wf = panel * min(f / 1.25, 1.0)
        b.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="2" fill="#d99a2b"/>'
                 % (x2, y, wf, rh))
        b.append(_txt(x2 + wf + 7, y + rh / 2 + 4.5, "%.2f%%" % f, 11, INK2))

    b.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%.1f" stroke="#c0392b" stroke-width="1" '
             'stroke-dasharray="4 3"/>'
             % (x1 + panel * 0.95, top - 4, x1 + panel * 0.95, top + n * (rh + gap) - gap))
    b.append(_txt(x1 + panel * 0.95 - 4, top - 8, "场外合同基准 95%", 10.5, "#c0392b", "end"))
    return _svg(w, h, "穿透后参与率与加权综合费率对比",
                "左面板为穿透后参与率，右面板为加权综合费率", "".join(b))


# --------------------------------------------------------------------------- #
def load():
    a = json.load(open(os.path.join(ROOT, "data", "analysis.json"), encoding="utf-8"))
    s = json.load(open(os.path.join(ROOT, "data", "score.json"), encoding="utf-8"))
    amap = a["products"]
    rows = []
    for r in s["ranking"]:
        m = amap[r["code"]]
        rows.append(dict(r, penetrated=m["penetrated_pct"], fee=m["comprehensive_fee"],
                         nav=m["nav_end"], kind=m["kind"], name=m["name"]))
    return rows


def build_all(rows=None):
    rows = rows or load()
    return {
        "rank_stacked": rank_stacked(rows),
        "return_fee": return_fee_scatter(rows),
        "period_grouped": period_grouped(rows),
        "exposure_fee": exposure_fee(rows),
    }


def write_files(rows=None):
    os.makedirs(IMGDIR, exist_ok=True)
    out = {}
    for name, svg in build_all(rows).items():
        p = os.path.join(IMGDIR, name + ".svg")
        open(p, "w", encoding="utf-8").write(svg)
        out[name] = "docs/img/%s.svg" % name
        print("  docs/img/%s.svg  (%.1f KB)" % (name, len(svg.encode()) / 1024))
    return out


if __name__ == "__main__":
    write_files()
