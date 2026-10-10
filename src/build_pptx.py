"""
build_pptx.py - generate the presentation deck from the canonical research
outputs.  Palette: Midnight Executive (same as the July deck).
Saves: "crypto_stat_arb_deck  -  Final.pptx"
"""
import json
import os
import sys

import pandas as pd
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

sys.path.insert(0, os.path.dirname(__file__))
from textclean import clean

OUTFILE = "crypto_stat_arb_deck_V2.pptx"

# ---- palette (Midnight Executive) ---------------------------------------- #
NAVY = RGBColor(0x1E, 0x27, 0x61)
NAVY2 = RGBColor(0x14, 0x1B, 0x45)
ICE = RGBColor(0xCA, 0xDC, 0xFC)
BLUE = RGBColor(0x5B, 0x8D, 0xEF)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CORAL = RGBColor(0xF9, 0x61, 0x67)
GOLD = RGBColor(0xE6, 0xA8, 0x17)
GREEN = RGBColor(0x2C, 0x8C, 0x5A)
GREY = RGBColor(0x5A, 0x5A, 0x5A)
LIGHT = RGBColor(0xF4, 0xF6, 0xFB)
MID = RGBColor(0xD0, 0xD0, 0xD0)
HEAD = "Cambria"
BODY = "Calibri"

# ---- data ---------------------------------------------------------------- #
R = "data/research"
S = json.load(open(f"{R}/summary.json"))
rd = lambda n, **k: pd.read_csv(f"{R}/{n}.csv", **k)
FULL = rd("J_performance_full").set_index("Strategy")
OOS = rd("J_performance_oos").set_index("Strategy")
INS = rd("J_performance_is").set_index("Strategy")
HOR, ACT, WKD = rd("A_horizon_scan"), rd("B_activity_volume"), rd("C_weekday_weekend").set_index("Strategy")
THM, COR, MAC = rd("D_theme_momentum"), rd("F_correlation").set_index("Strategy"), rd("G_macro_regimes")
SEL, EXE, SWP = rd("H_candidate_selection"), rd("H_execution_variants"), rd("H_cost_sweep").set_index("cost_bps")
WTS, RB = rd("I_weighting_methods").set_index("Method"), rd("I_selection_robustness")
CORR = rd("I_sleeve_correlation", index_col=0)
IH = rd("A2_intraday_horizon")
UNI = pd.read_csv("data/universe.csv")
V1 = json.load(open(f"{R}/v1_reference.json"))
CMB, CMB20 = "Combined portfolio", "Combined (all trades at 20bps)"
MOM20, MOM7 = "Momentum book (20bps market)", "Momentum book (7bps limit)"
REV7, REV20 = "Reversal book (7bps limit)", "Reversal book (20bps market)"
PRS, EW, BTC = "Cointegrated pairs (20bps)", "Equal-weight crypto (B&H)", "Buy & Hold BTC"
co, ci, cf = OOS.loc[CMB], INS.loc[CMB], FULL.loc[CMB]
best_m = S["weighting_selected"]
n_in = int((UNI.status == "in universe").sum())


def pct(x, d=1):
    v = round(x * 100, d)
    return f"{0.0 if v == 0 else v:.{d}f}%"


def num(x, d=2):
    v = round(x, d)
    return f"{0.0 if v == 0 else v:.{d}f}"


def hz(kind, L, col="Gross IS"):
    return HOR[(HOR.kind == kind) & (HOR.lookback_days == L)][col].iloc[0]


def mac(strat, ind, k, per="IS"):
    return MAC[(MAC.Strategy == strat) & (MAC.Indicator == ind)][f"{k} Sharpe {per}"].iloc[0]


def sel(name, col):
    return SEL[SEL.Strategy == name][col].iloc[0]


def pretty(name):
    return (name.replace(" MOM ", " momentum, hold ").replace(" REV ", " reversal, hold ")
            .replace("H=", "").replace("L=", "").replace("blend", "7/14/28 blend"))


prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


# ---- helpers ------------------------------------------------------------- #
def slide():
    return prs.slides.add_slide(BLANK)


def bg(s, color):
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = color


def box(s, x, y, w, h, fill=None, line=None, line_w=None, shadow=False,
        shape=MSO_SHAPE.RECTANGLE, radius=None):
    sp = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid(); sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(line_w or 1)
    sp.shadow.inherit = False
    if shadow:
        # reuse the single <a:effectLst> python-pptx already created; a second
        # one makes PowerPoint "repair" the file
        el = sp._element.spPr
        ef = el.find(qn('a:effectLst'))
        if ef is None:
            ef = el.makeelement(qn('a:effectLst'), {}); el.append(ef)
        sh = ef.makeelement(qn('a:outerShdw'),
                            {'blurRad': '90000', 'dist': '38100', 'dir': '5400000', 'rotWithShape': '0'})
        clr = sh.makeelement(qn('a:srgbClr'), {'val': '1E2761'})
        alpha = clr.makeelement(qn('a:alpha'), {'val': '30000'})
        clr.append(alpha); sh.append(clr); ef.append(sh)
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sp.adjustments[0] = radius
        except Exception:
            pass
    return sp


def text(s, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         space_after=4, line_spacing=1.0):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space_after); p.space_before = Pt(0)
        p.line_spacing = line_spacing
        for (txt, size, color, bold, italic, font) in para:
            r = p.add_run(); r.text = clean(txt)
            r.font.size = Pt(size); r.font.color.rgb = color
            r.font.bold = bold; r.font.italic = italic; r.font.name = font
    return tb


def Rn(txt, size, color=NAVY, bold=False, italic=False, font=BODY):
    return (txt, size, color, bold, italic, font)


def bullets(s, x, y, w, h, items, size=15, color=NAVY, gap=8, marker="-", mcolor=None):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    mcolor = mcolor or BLUE
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap); p.space_before = Pt(0); p.line_spacing = 1.05
        rm = p.add_run(); rm.text = marker + "  "
        rm.font.size = Pt(size); rm.font.color.rgb = mcolor; rm.font.bold = True; rm.font.name = BODY
        if isinstance(it, tuple):
            lead, rest = it
            r1 = p.add_run(); r1.text = clean(lead)
            r1.font.size = Pt(size); r1.font.color.rgb = color; r1.font.bold = True; r1.font.name = BODY
            r2 = p.add_run(); r2.text = clean(rest)
            r2.font.size = Pt(size); r2.font.color.rgb = color; r2.font.bold = False; r2.font.name = BODY
        else:
            r = p.add_run(); r.text = clean(it)
            r.font.size = Pt(size); r.font.color.rgb = color; r.font.name = BODY
    return tb


def title_bar(s, kicker, ttl):
    text(s, 0.7, 0.45, 12, 0.4, [[Rn(kicker.upper(), 13, BLUE, True)]])
    text(s, 0.7, 0.8, 12, 0.9, [[Rn(ttl, 30, NAVY, True, False, HEAD)]])


def pagenum(s):
    n = len(prs.slides._sldIdLst)
    text(s, 12.3, 7.02, 0.8, 0.3, [[Rn(str(n), 11, GREY)]], align=PP_ALIGN.RIGHT)


def footer(s, txt):
    text(s, 0.7, 7.0, 11, 0.3, [[Rn(txt, 10.5, GREY, False, True)]])


def pic(s, path, x, y, w=None, h=None):
    """Place an image keeping its aspect ratio, fitting inside w x h."""
    iw, ih = Image.open(path).size
    if w is not None and h is not None:
        scale = min(w / iw, h / ih)
        ww, hh = iw * scale, ih * scale
    elif w is not None:
        ww, hh = w, w * ih / iw
    else:
        ww, hh = h * iw / ih, h
    s.shapes.add_picture(path, Inches(x), Inches(y), width=Inches(ww), height=Inches(hh))
    return ww, hh


def card(s, x, y, w, h, label, value, sub, color=NAVY, dark=False, vsize=30):
    box(s, x, y, w, h, fill=(NAVY if dark else LIGHT), shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        radius=0.08, shadow=True)
    text(s, x + 0.22, y + 0.16, w - 0.4, 0.35, [[Rn(label.upper(), 11, ICE if dark else GREY, True)]])
    text(s, x + 0.22, y + 0.44, w - 0.4, 0.6, [[Rn(value, vsize, WHITE if dark else color, True, False, HEAD)]])
    text(s, x + 0.22, y + h - 0.4, w - 0.4, 0.35, [[Rn(sub, 11.5, ICE if dark else NAVY, False, True)]])


def grid_table(s, x, y, col_w, rows, rh=0.5, hl=(), size=12.5, head_size=12):
    yy = y
    for ri, row in enumerate(rows):
        xx = x
        header = ri == 0
        best = ri in hl
        fill = NAVY if header else (RGBColor(0xE9, 0xF0, 0xFF) if best else (LIGHT if ri % 2 else WHITE))
        for ci, val in enumerate(row):
            box(s, xx, yy, col_w[ci], rh, fill=fill)
            col = WHITE if header else (NAVY if best else RGBColor(0x33, 0x33, 0x33))
            bold = header or best or ci == 0
            al = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER
            pad = 0.12 if ci == 0 else 0
            text(s, xx + pad, yy, col_w[ci] - pad, rh,
                 [[Rn(str(val), head_size if header else size, col, bold)]], align=al, anchor=MSO_ANCHOR.MIDDLE)
            xx += col_w[ci]
        yy += rh
    return yy


# =========================================================================== #
# 1. Title
# =========================================================================== #
s = slide(); bg(s, NAVY)
box(s, 9.4, -1.2, 5.2, 5.2, fill=NAVY2, shape=MSO_SHAPE.OVAL)
box(s, 10.9, 3.6, 3.6, 3.6, fill=NAVY2, shape=MSO_SHAPE.OVAL)
text(s, 0.9, 1.55, 11, 0.5, [[Rn("WALL STREET QUANTS  |  BOOTCAMP PROJECT  |  VERSION 2", 15, ICE, True)]])
text(s, 0.9, 2.15, 11.2, 2.0, [[Rn("Statistical Arbitrage in", 44, WHITE, True, False, HEAD)],
                              [Rn("Cryptocurrency Markets", 44, WHITE, True, False, HEAD)]], space_after=2)
text(s, 0.9, 4.05, 11, 0.6, [[Rn(f"Momentum and reversal on a survivorship-free {n_in}-coin universe", 18, ICE, False, True)]])
for i, (lab, val) in enumerate([("Hold-out Sharpe (x sqrt 252)", num(co["Sharpe"])),
                                ("Hold-out alpha t-stat", num(co["Alpha t"])),
                                ("Hold-out correlation to BTC", num(co["Corr BTC"]))]):
    cx = 0.9 + i * 3.75
    box(s, cx, 5.2, 3.5, 1.15, fill=NAVY2, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12)
    text(s, cx + 0.25, 5.35, 3.0, 0.6, [[Rn(val, 30, WHITE, True, False, HEAD)]])
    text(s, cx + 0.25, 5.93, 3.05, 0.35, [[Rn(lab, 12, ICE)]])
text(s, 0.9, 6.85, 11.5, 0.4, [[Rn(f"Research {S['bt_start'][:4]}-{S['is_end'][:4]} (all decisions)  |  hold-out {S['oos_start'][:4]}-{S['sample_end'][:4]} (untouched)  |  net of 20 / 7 bps costs", 12, ICE)]])

# =========================================================================== #
# 2. Executive summary (hold-out first)
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Executive summary", "Hold-out first: a modest, market-neutral edge")
bullets(s, 0.7, 1.95, 6.2, 4.9, [
    ("Hold-out (2024-2026): ", f"Sharpe {num(co['Sharpe'])}, alpha {pct(co['Alpha'])}/yr with t = {num(co['Alpha t'])} - not significant."),
    ("Research (2021-2023): ", f"Sharpe {num(ci['Sharpe'])}, alpha t {num(ci['Alpha t'])}. The gap is selection bias plus decay."),
    ("Market-neutral: ", f"beta {num(co['Beta'])}, correlation to BTC {num(co['Corr BTC'])}."),
    ("What survived: ", "time-series momentum switched off when implied vol (DVOL) is high."),
    ("What faded: ", "theme momentum and slow residual reversal."),
    ("vs version 1: ", f"1.02 (sqrt 365) = {num(V1['sharpe_full_252'])} at sqrt 252; hold-out {num(V1['sharpe_oos_252'])} -> {num(co['Sharpe'])} after fixes."),
], size=14, gap=10)
for i, (lab, val, sub, c) in enumerate([("Hold-out Sharpe", num(co["Sharpe"]), f"research {num(ci['Sharpe'])}", NAVY),
                                        ("Hold-out alpha t", num(co["Alpha t"]), f"research {num(ci['Alpha t'])}", CORAL),
                                        ("Corr to BTC", num(co["Corr BTC"]), f"beta {num(co['Beta'])}", BLUE),
                                        ("Hold-out max DD", pct(co["MaxDD"]), f"BTC {pct(OOS.loc[BTC, 'MaxDD'])}", GREEN)]):
    card(s, 7.3 + (i % 2) * 2.95, 1.95 + (i // 2) * 2.25, 2.75, 2.0, lab, val, sub, c)
footer(s, "Sharpe = mean / std x sqrt(252). Momentum at 20 bps, reversal at 7 bps; all-at-20-bps results in the report.")
pagenum(s)

# =========================================================================== #
# 3. V1 vs V2
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Version 2", "What changed from V1 to V2")
rows = [("V1", "V2", "Effect")]
rows += [("Sharpe with sqrt(365)", "mean / std x sqrt(252) everywhere", f"V1 1.02 -> {num(V1['sharpe_full_252'])}"),
         ("Exploration on full 2021-26 sample", "Mechanical protocol on 2021-23 only", f"True hold-out: {num(co['Sharpe'])}"),
         ("Full sample first; no corr to BTC", "Hold-out first; corr to BTC in all tables", f"alpha t {num(co['Alpha t'])}, corr {num(co['Corr BTC'])}"),
         ("16 coins alive in 2026", f"Top 40 by Jan-2021 market cap ({n_in} with data)", "FTT, EOS, MKR exits included"),
         ("No rebuild or methodology guide", "60-line rebuild + methodology explainer", "Matches engine to 1e-12")]
grid_table(s, 0.7, 1.9, [3.6, 4.6, 3.7], rows, rh=0.75, size=13, head_size=13)
pagenum(s)

# =========================================================================== #
# 4. Universe
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Data", "A survivorship-free universe, fixed in January 2021")
bullets(s, 0.7, 1.95, 6.1, 4.6, [
    ("Rule: ", "the 40 largest coins on CoinMarketCap's 2021-01-03 snapshot, excluding stablecoins and wrapped tokens."),
    ("Never updated with hindsight: ", "coins stay in until their prices stop."),
    ("Failures included: ", "FTX Token (collapsed Nov-2022), EOS and MKR (history ends 2026)."),
    ("Sources: ", "Coinbase, KuCoin, Gate.io, Bitfinex - the most complete history per coin; Bitfinex keeps delisted pairs."),
    ("Missing: ", "Revain (no free price history)."),
], size=14.5, gap=10)
src_counts = UNI[UNI.status == "in universe"].source.value_counts()
for i, (val, lab) in enumerate([(str(n_in), "coins traded"), ("40", "top by market cap"),
                                (str((UNI.reason.fillna('').str.contains('ends')).sum()), "exits during sample"),
                                (str(len(src_counts)), "data venues")]):
    x = 7.1 + (i % 2) * 2.85; y = 1.95 + (i // 2) * 1.5
    box(s, x, y, 2.65, 1.3, fill=NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1, shadow=True)
    text(s, x + 0.22, y + 0.15, 2.3, 0.6, [[Rn(val, 30, WHITE, True, False, HEAD)]])
    text(s, x + 0.22, y + 0.85, 2.3, 0.35, [[Rn(lab.upper(), 11, ICE, True)]])
box(s, 7.1, 5.05, 5.5, 1.6, fill=LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
text(s, 7.35, 5.15, 5.1, 0.35, [[Rn("UNIVERSE", 12, BLUE, True)]])
text(s, 7.35, 5.45, 5.1, 1.2, [[Rn(" ".join(UNI[UNI.status == "in universe"].asset), 11.5, NAVY)]], line_spacing=1.15)
pagenum(s)

# =========================================================================== #
# 5. Protocol
# =========================================================================== #
s = slide(); bg(s, NAVY)
text(s, 0.7, 0.5, 12, 0.4, [[Rn("PRE-REGISTERED PROTOCOL", 13, ICE, True)]])
text(s, 0.7, 0.85, 12, 0.9, [[Rn("Every decision made on 2021-2023, mechanically", 32, WHITE, True, False, HEAD)]])
steps = [("1", "Signals", f"{S['n_signals']} variants in 7 families: cross-sectional, time-series, theme, two residuals, high-vol, pairs"),
         ("2", "Direction", "follow or fade each signal by the sign of its 2021-23 gross Sharpe"),
         ("3", "Candidates", f"cross with holding periods -> {S['n_candidates']} candidates at 20 bps (momentum) / 7 bps (reversal)"),
         ("4", "Books", "best variant per family if 2021-23 net Sharpe > 0; top three families per book"),
         ("5", "Execution + weights", f"chosen on 2021-23: {S['execution_selected']['Momentum'].lower()} / {S['execution_selected']['Reversal'].lower()}; {best_m.lower()}")]
y = 2.05
for n_, head_, desc in steps:
    box(s, 0.7, y, 0.7, 0.7, fill=BLUE, shape=MSO_SHAPE.OVAL)
    text(s, 0.7, y, 0.7, 0.7, [[Rn(n_, 22, WHITE, True, False, HEAD)]], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 1.7, y + 0.05, 3.2, 0.5, [[Rn(head_, 19, WHITE, True, False, HEAD)]])
    text(s, 4.9, y + 0.08, 7.9, 0.7, [[Rn(desc, 14.5, ICE)]])
    y += 1.0
pagenum(s)

# =========================================================================== #
# 6. Horizon
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Time horizon", "Cross-section reverses; individual coins trend at 1-4 weeks")
pic(s, "figures/A_horizon_scan.png", 0.45, 1.8, w=8.4, h=3.9)
card(s, 9.05, 1.9, 3.6, 1.5, "CS 1-day (research)", num(hz("Cross-sectional", 1)), "negative = reversal", CORAL)
card(s, 9.05, 3.55, 3.6, 1.5, "TS 30-day (research)", num(hz("Time-series", 30)), "time-series momentum", NAVY)
card(s, 9.05, 5.2, 3.6, 1.5, "1-hour CS (research)", num(IH.iloc[0]["Gross Sharpe IS"]), "reversal, partly bid-ask bounce", GOLD)
footer(s, f"Dark bars drive decisions; light bars (hold-out) shown for transparency only. 1-day reversal loses money net: {num(hz('Cross-sectional', 1, 'Net7 IS'))} at 7 bps.")
pagenum(s)

# =========================================================================== #
# 7. Activity + seasonality
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Activity and seasonality", "Weekends favour trends; volume shocks mark retracing spikes")
pic(s, "figures/B_activity_volume.png", 0.45, 1.8, w=6.3, h=3.0)
pic(s, "figures/C_day_of_week.png", 6.75, 1.8, w=6.3, h=3.0)
a = lambda L, v: ACT[(ACT.lookback_days == L) & (ACT.variant == v)]["Gross IS"].iloc[0]
bullets(s, 0.7, 5.0, 5.9, 1.9, [
    f"1-day reversal is stronger in high-activity coins ({num(a(1, 'High-activity coins only'))}) than low-activity ({num(a(1, 'Low-activity coins only'))}) - the opposite of the uninformed-trading story.",
    "Volume-shock weighting tilts toward momentum but not enough to be profitable.",
], size=13, gap=8)
bullets(s, 7.0, 5.0, 5.8, 1.9, [
    f"TS momentum: weekend Sharpe {num(WKD.loc['TS momentum (blend)', 'Weekend Sharpe'])} vs weekday {num(WKD.loc['TS momentum (blend)', 'Weekday Sharpe'])}.",
    "Tuesday is the worst day for trend-following in both versions.",
], size=13, gap=8)
pagenum(s)

# =========================================================================== #
# 8. Themes + correlation
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Themes and correlation", "What worked in 2021-23 did not all persist")
pic(s, "figures/D_theme_indices.png", 0.45, 1.8, w=6.6, h=3.3)
rows = [("Signal (momentum sign)", "Research", "Hold-out")]
t14 = THM[THM.Strategy == "Theme L=14d H=7d"].iloc[0]
rows.append(("Theme 14d, hold 7d", num(t14["Gross IS"]), num(t14["Gross OOS"])))
for k in ["Residual vs market L=60d", "Residual vs theme L=60d", "Residual vs theme L=1d"]:
    rows.append((k.replace("L=", ""), num(COR.loc[k, "Gross IS"]), num(COR.loc[k, "Gross OOS"])))
rows.append(("Cointegrated pairs", num(COR.loc["Cointegrated pairs (Kalman, walk-forward)", "Gross IS"]),
             num(COR.loc["Cointegrated pairs (Kalman, walk-forward)", "Gross OOS"])))
grid_table(s, 7.35, 1.9, [3.0, 1.1, 1.1], rows, rh=0.5, size=12.5)
bullets(s, 0.7, 5.35, 12, 1.6, [
    ("Themes: ", "theme momentum was the best research-period momentum signal, then flattened in the hold-out."),
    ("Correlation: ", "residuals reverse in 2021-23 (negative = reversal); pairs lost money then and worked later - unstable relationships."),
], size=13.5, gap=8)
pagenum(s)

# =========================================================================== #
# 9. Macro
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Macro: volatility and dislocation", "High implied vol breaks trends, in both periods")
pic(s, "figures/G_macro_regimes.png", 0.4, 1.75, w=12.5, h=3.8)
card(s, 0.7, 5.55, 3.9, 1.45, "TS momentum, DVOL low / high (research)",
     f"{num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'Low'))} / {num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'High'))}", "gross Sharpe", NAVY, vsize=26)
card(s, 4.75, 5.55, 3.9, 1.45, "Same, hold-out",
     f"{num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'Low', 'OOS'))} / {num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'High', 'OOS'))}", "pattern repeats out of sample", GREEN, vsize=26)
box(s, 8.8, 5.55, 3.85, 1.45, fill=NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
text(s, 9.05, 5.65, 3.45, 1.25, [[Rn("The DVOL filter (trend-following off in the top third of implied vol) was selected on 2021-23 and is the component that held up.", 12.5, WHITE, True)]], anchor=MSO_ANCHOR.MIDDLE)
pagenum(s)

# =========================================================================== #
# 10. Selection
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Mechanical selection", "Family winners on 2021-23, and how they did after")
top = SEL.sort_values("Selection IS", ascending=False).groupby(["book", "family"], sort=False).head(1).sort_values(["book", "Selection IS"], ascending=[True, False])
rows = [("Best candidate per family", "Book", "IS net", "Hold-out net")]
chosen = set(S["momentum_members"] + S["reversal_members"])
hl = set()
for i, (_, r) in enumerate(top.iterrows(), 1):
    cost_col = "Net20 OOS" if r.book == "Momentum" else "Net7 OOS"
    rows.append((pretty(r.Strategy), r.book, num(r["Selection IS"]), num(r[cost_col])))
    if r.Strategy in chosen:
        hl.add(i)
grid_table(s, 0.7, 1.85, [5.6, 1.5, 1.2, 1.5], rows, rh=0.46, hl=hl, size=12, head_size=12)
text(s, 0.7, 6.55, 12, 0.5, [[Rn("Highlighted = selected (positive IS net Sharpe, top three families per book). Cross-sectional momentum never cleared 20 bps.", 12, GREY, False, True)]])
pagenum(s)

# =========================================================================== #
# 11. Execution + weighting
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Execution and weighting", "Costs bite hard; the books diversify each other")
pic(s, "figures/H_cost_sweep.png", 0.45, 1.8, w=6.6, h=3.4)
rows = [("Weighting", "IS", "Hold-out")]
for m in WTS.index:
    rows.append((m, num(WTS.loc[m, "Sharpe IS"]), num(WTS.loc[m, "Sharpe OOS"])))
grid_table(s, 7.35, 1.9, [3.0, 1.0, 1.2], rows, rh=0.5, hl={1 + list(WTS.index).index(best_m)}, size=12.5)
bullets(s, 0.7, 5.45, 12, 1.5, [
    ("Execution: ", f"{S['execution_selected']['Momentum']} for momentum, {S['execution_selected']['Reversal'].lower()} for reversal (chosen on 2021-23). Hold-out Sharpe falls to {num(SWP.loc[20, 'Combined hold-out'])} if every trade costs 20 bps."),
    ("Diversification: ", f"momentum and reversal books correlate {num(CORR.loc['Momentum book', 'Reversal book'])}; ensemble hold-out {num(RB.iloc[0]['Combined Sharpe OOS'])} vs single-best {num(RB.iloc[1]['Combined Sharpe OOS'])}."),
], size=13.5, gap=8)
pagenum(s)

# =========================================================================== #
# 12. Performance (hold-out first)
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Performance evaluation", "Hold-out first, with alpha t and correlation to BTC")
keys = [CMB, MOM20, REV7, PRS, EW, BTC]
labs = ["Combined portfolio", "Momentum book (20 bps)", "Reversal book (7 bps)", "Cointegrated pairs", "Equal-weight crypto", "Buy & hold BTC"]
rows = [("Strategy", "Hold-out Sharpe", "Research Sharpe", "Hold-out return", "Hold-out max DD", "Hold-out alpha t", "Beta", "Corr BTC")]
for k, lab in zip(keys, labs):
    r = OOS.loc[k]
    rows.append((lab, num(r["Sharpe"]), num(INS.loc[k, "Sharpe"]), pct(r["Ann.Return"]), pct(r["MaxDD"]),
                 num(r["Alpha t"]), num(r["Beta"]), num(r["Corr BTC"])))
yy = grid_table(s, 0.7, 1.85, [3.0, 1.35, 1.35, 1.35, 1.35, 1.35, 0.9, 1.15], rows, rh=0.6, hl={1}, size=13, head_size=11.5)
text(s, 0.7, yy + 0.15, 12, 0.6, [[Rn(f"Hold-out {S['oos_start']} to {S['sample_end']}; research {S['bt_start']} to {S['is_end']}. Sharpe x sqrt(252). Alpha / beta / correlation vs daily BTC returns, Newey-West t.", 12, GREY, False, True)]])
pagenum(s)

# =========================================================================== #
# 13. Equity + V1 vs V2
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Results", "Growth of $1, and what the corrections changed")
pic(s, "figures/J_equity_curves.png", 0.45, 1.7, w=7.6, h=3.6)
rows = [("Combined Sharpe", "V1", "V1 @252", "V2")]
rows.append(("Full backtest", num(V1["sharpe_full_365"]), num(V1["sharpe_full_252"]), num(cf["Sharpe"])))
rows.append(("Hold-out", num(V1["sharpe_oos_365"]), num(V1["sharpe_oos_252"]), num(co["Sharpe"])))
rows.append(("Hold-out alpha t", num(V1["alpha_t_oos"]), num(V1["alpha_t_oos"]), num(co["Alpha t"])))
rows.append(("Corr BTC (full)", num(V1["corr_btc_full"]), num(V1["corr_btc_full"]), num(cf["Corr BTC"])))
grid_table(s, 8.3, 1.9, [1.9, 0.8, 0.95, 0.8], rows, rh=0.55, hl={2}, size=12.5, head_size=12)
bullets(s, 0.7, 5.55, 12, 1.4, [
    ("Convention: ", "sqrt(252) lowers every Sharpe by 17%."),
    ("Universe + protocol: ", f"survivorship-free coins and decisions on 2021-23 only take the hold-out from {num(V1['sharpe_oos_252'])} to {num(co['Sharpe'])}. The lower number is the credible one."),
], size=13.5, gap=8)
pagenum(s)

# =========================================================================== #
# 14. Conclusion
# =========================================================================== #
s = slide(); bg(s, NAVY)
box(s, 8.8, -1.4, 6, 6, fill=NAVY2, shape=MSO_SHAPE.OVAL)
text(s, 0.8, 0.7, 12, 0.4, [[Rn("CONCLUSION", 14, ICE, True)]])
text(s, 0.8, 1.15, 11.5, 1.0, [[Rn("How you select matters as much as what you select", 32, WHITE, True, False, HEAD)]])
bullets(s, 0.8, 2.4, 8.4, 3.4, [
    ("Patterns are real: ", "cross-sectional reversal, 1-4 week trends, weekend and implied-vol effects."),
    ("Most do not survive costs ", "or an honest hold-out."),
    ("One survivor: ", "time-series momentum with a DVOL filter."),
    ("Next: ", "paper-trade it live; add funding costs and a liquidity screen."),
], size=16, gap=14, color=WHITE, mcolor=ICE)
box(s, 0.8, 6.0, 11.7, 1.05, fill=NAVY2, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
for i, (lab, val) in enumerate([("Hold-out Sharpe", num(co["Sharpe"])), ("Hold-out alpha t", num(co["Alpha t"])),
                                ("Corr to BTC", num(co["Corr BTC"])), ("Research Sharpe", num(ci["Sharpe"]))]):
    fx = 1.1 + i * 2.9
    text(s, fx, 6.12, 2.8, 0.55, [[Rn(val, 26, WHITE, True, False, HEAD)]])
    text(s, fx, 6.66, 2.8, 0.3, [[Rn(lab.upper(), 11.5, ICE, True)]])
pagenum(s)

prs.save(OUTFILE)
print(f"saved {OUTFILE} with {len(prs.slides._sldIdLst)} slides")
