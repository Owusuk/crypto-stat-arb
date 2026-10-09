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

OUTFILE = "crypto_stat_arb_deck  -  Final.pptx"

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
FULL = pd.read_csv(f"{R}/J_performance_full.csv").set_index("Strategy")
OOS = pd.read_csv(f"{R}/J_performance_oos.csv").set_index("Strategy")
INS = pd.read_csv(f"{R}/J_performance_is.csv").set_index("Strategy")
HOR = pd.read_csv(f"{R}/A_horizon_scan.csv")
IH = pd.read_csv(f"{R}/A2_intraday_horizon.csv")
ACT = pd.read_csv(f"{R}/B_activity_volume.csv")
WKD = pd.read_csv(f"{R}/C_weekday_weekend.csv").set_index("Strategy")
SESS = pd.read_csv(f"{R}/C_session_returns.csv")
THM = pd.read_csv(f"{R}/D_theme_momentum.csv").set_index("Strategy")
FR = pd.read_csv(f"{R}/E_frontrun_us_session.csv")
COR = pd.read_csv(f"{R}/F_correlation_reversal.csv").set_index("Strategy")
MAC = pd.read_csv(f"{R}/G_macro_regimes.csv")
SEL = pd.read_csv(f"{R}/H_candidate_selection.csv").set_index("Strategy")
EXE = pd.read_csv(f"{R}/H_execution_variants.csv")
SWP = pd.read_csv(f"{R}/H_cost_sweep.csv").set_index("cost_bps")
WTS = pd.read_csv(f"{R}/I_weighting_methods.csv").set_index("Method")
RB = pd.read_csv(f"{R}/I_selection_robustness.csv")
CORR = pd.read_csv(f"{R}/I_sleeve_correlation.csv", index_col=0)

CMB, CMB20 = "Combined portfolio", "Combined portfolio (all at 20bps market)"
MOMK, REVK, REV20 = "Momentum ensemble (net 20bps market)", "Reversal (net 7bps limit)", "Reversal (net 20bps market)"
BTC, EW, PRS = "Buy & Hold BTC", "Equal-weight crypto (B&H)", "Cointegration pairs (net 20bps)"
cf, co_, ci = FULL.loc[CMB], OOS.loc[CMB], INS.loc[CMB]
best_m = S["weighting_selected"]


def pct(x, d=1):
    v = round(x * 100, d)
    return f"{0.0 if v == 0 else v:.{d}f}%"


def num(x, d=2):
    v = round(x, d)
    return f"{0.0 if v == 0 else v:.{d}f}"


def hz(kind, L, col="Gross Full"):
    return HOR[(HOR.kind == kind) & (HOR.lookback_days == L)][col].iloc[0]


def act(L, v, col="Gross Full"):
    return ACT[(ACT.lookback_days == L) & (ACT.variant == v)][col].iloc[0]


def mac(strat, ind, k):
    return MAC[(MAC.Strategy == strat) & (MAC.Indicator == ind)][f"{k} Sharpe"].iloc[0]


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
        el = sp._element.spPr
        ef = el.makeelement(qn('a:effectLst'), {})
        sh = ef.makeelement(qn('a:outerShdw'),
                            {'blurRad': '90000', 'dist': '38100', 'dir': '5400000', 'rotWithShape': '0'})
        clr = sh.makeelement(qn('a:srgbClr'), {'val': '1E2761'})
        alpha = clr.makeelement(qn('a:alpha'), {'val': '30000'})
        clr.append(alpha); sh.append(clr); ef.append(sh); el.append(ef)
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
text(s, 0.9, 1.55, 11, 0.5, [[Rn("WALL STREET QUANTS  |  BOOTCAMP PROJECT", 15, ICE, True)]])
text(s, 0.9, 2.15, 11.2, 2.0, [[Rn("Statistical Arbitrage in", 44, WHITE, True, False, HEAD)],
                              [Rn("Cryptocurrency Markets", 44, WHITE, True, False, HEAD)]], space_after=2)
text(s, 0.9, 4.05, 11, 0.6, [[Rn("Momentum and reversal research on live market data", 19, ICE, False, True)]])
chips = [("Net Sharpe (combined)", num(cf["Sharpe"])),
         ("Alpha per year", pct(cf["Alpha"])),
         ("Beta to Bitcoin", num(cf["Beta"]))]
cx = 0.9
for lab, val in chips:
    box(s, cx, 5.2, 3.5, 1.15, fill=NAVY2, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12)
    text(s, cx + 0.25, 5.35, 3.0, 0.6, [[Rn(val, 30, WHITE, True, False, HEAD)]])
    text(s, cx + 0.25, 5.93, 3.05, 0.35, [[Rn(lab, 12, ICE)]])
    cx += 3.75
text(s, 0.9, 6.85, 11.5, 0.4,
     [[Rn(f"Coinbase daily + hourly prices and Deribit DVOL  |  {S['sample_start']} to {S['sample_end']}  |  "
          f"net of 20 / 7 bps costs", 12, ICE)]])

# =========================================================================== #
# 2. Executive summary
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Executive summary", "Momentum + reversal: market-neutral, profitable after costs")
bullets(s, 0.7, 1.95, 6.2, 4.9, [
    ("Horizon decides the sign. ", f"Crypto shows momentum from 1 to 30 days (peak at 14 days, Sharpe {num(hz('Cross-sectional', 14))}). Reversal appears only intraday and at 60-90 days."),
    ("Intraday reversal is huge but untradeable. ", f"1-hour reversal has a gross Sharpe of {num(-IH.iloc[0]['Gross Sharpe'])}, but costs wipe it out."),
    ("The brief's conditioning variables work. ", "Volume shocks, weekends, themes and calm option markets strengthen momentum; stress strengthens reversal."),
    ("Final strategy: ", f"momentum ensemble + long-horizon reversal, {best_m.lower()} weights, market-neutral."),
    ("Honest hold-out: ", f"Sharpe {num(co_['Sharpe'])} in 2024-2026 vs {num(ci['Sharpe'])} in research. Reversal held up; momentum decayed."),
], size=14.5, gap=11)
cards = [("Net Sharpe", num(cf["Sharpe"]), f"vs {num(FULL.loc[BTC, 'Sharpe'])} for BTC", NAVY),
         ("Alpha / year", pct(cf["Alpha"]), f"t-stat {num(cf['Alpha t'])}", GREEN),
         ("Beta to BTC", num(cf["Beta"]), "market-neutral", BLUE),
         ("Max drawdown", pct(cf["MaxDD"]), f"vs {pct(FULL.loc[BTC, 'MaxDD'])} for BTC", CORAL)]
for i, (lab, val, sub, c) in enumerate(cards):
    card(s, 7.3 + (i % 2) * 2.95, 1.95 + (i // 2) * 2.25, 2.75, 2.0, lab, val, sub, c)
footer(s, f"Full backtest {S['bt_start']} to {S['sample_end']}; momentum at 20 bps market orders, reversal at 7 bps limit orders.")
pagenum(s)

# =========================================================================== #
# 3. The brief, item by item
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Research outline", "Every item in the brief, tested")
ts_wd, ts_we = WKD.loc["TS momentum (blend)", "Weekday Sharpe"], WKD.loc["TS momentum (blend)", "Weekend Sharpe"]
t14 = THM.loc["Theme momentum L=14d H=1d"]
fr2 = FR[(FR.Test.str.startswith("Prior-day")) & (FR.kind == "Cross-sectional")].iloc[0]
mom_items = [
    ("Time horizon", f"Momentum at 1-30 days (CS peak {num(hz('Cross-sectional', 14))})", GREEN),
    ("New info / activity", f"Volume shock lifts 3-day momentum {num(act(3, 'All coins'))} -> {num(act(3, 'Signal x volume shock'))}", GREEN),
    ("Seasonality", f"TS momentum: weekend Sharpe {num(ts_we)} vs weekday {num(ts_wd)}", GREEN),
    ("Themes", f"Theme momentum gross Sharpe {num(t14['Gross IS'])} (research); decayed after", GOLD),
    ("Technical plays", f"Front-running US session: {num(fr2['Gross bps/day'])} bps/day, not tradable", CORAL),
]
srv = "Short-term reversal 1d"
rev_items = [
    ("Time horizon", f"1-hour reversal gross Sharpe {num(-IH.iloc[0]['Gross Sharpe'])}; 60-day reversal tradable", GREEN),
    ("Uninformed trading", f"Low-activity moves: weaker 1-day momentum ({num(act(1, 'Low-activity coins only'))} vs {num(act(1, 'High-activity coins only'))})", GOLD),
    ("Correlation", f"Theme-residual reversal {num(COR.loc['Theme-residual reversal L=60d', 'Gross Full'])}; pairs fail after cost", GOLD),
    ("Macro", f"1-day reversal: {num(mac(srv, 'Realized vol (30d, EW market)', 'Low'))} in calm vs {num(mac(srv, 'Realized vol (30d, EW market)', 'Mid'))} in volatile", GREEN),
]
for col, (head, items, x) in enumerate([("HOW TO FIND MOMENTUM", mom_items, 0.7), ("HOW TO FIND REVERSAL", rev_items, 6.85)]):
    box(s, x, 1.85, 5.8, 0.55, fill=NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
    text(s, x + 0.25, 1.85, 5.4, 0.55, [[Rn(head, 14, WHITE, True)]], anchor=MSO_ANCHOR.MIDDLE)
    y = 2.55
    for name, res, c in items:
        box(s, x, y, 5.8, 0.82, fill=LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
        box(s, x, y, 0.12, 0.82, fill=c)
        text(s, x + 0.3, y + 0.08, 5.3, 0.35, [[Rn(name, 14, NAVY, True, False, HEAD)]])
        text(s, x + 0.3, y + 0.42, 5.4, 0.38, [[Rn(res, 12, GREY)]])
        y += 0.9
box(s, 6.85, 6.2, 0.25, 0.25, fill=GREEN); text(s, 7.15, 6.18, 1.6, 0.3, [[Rn("confirmed", 11, GREY)]])
box(s, 8.4, 6.2, 0.25, 0.25, fill=GOLD); text(s, 8.7, 6.18, 1.8, 0.3, [[Rn("partly / gross only", 11, GREY)]])
box(s, 10.45, 6.2, 0.25, 0.25, fill=CORAL); text(s, 10.75, 6.18, 1.6, 0.3, [[Rn("not found", 11, GREY)]])
pagenum(s)

# =========================================================================== #
# 4. Data and method
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Data and method", "Live data, unconstrained backtests, honest hold-out")
bullets(s, 0.7, 1.95, 6.0, 4.6, [
    ("Prices: ", "Coinbase daily OHLCV (2021 onward) and hourly OHLCV (2022 onward). Binance is geo-blocked here (HTTP 451)."),
    ("Implied vol: ", "Deribit DVOL, the crypto VIX."),
    ("Universe: ", "16 liquid coins in 4 themes; XRP (listing gap) and MKR (delisted Jan-2026) excluded."),
    ("Backtest: ", "unconstrained, gross exposure = 1, positions lagged one day, no look-ahead."),
    ("Costs: ", "20 bps per unit turnover for market orders, 7 bps for limit orders, sweep 0-200 bps."),
    ("Discipline: ", f"all choices made on {S['bt_start'][:4]}-{S['is_end'][:4]} data; {S['oos_start'][:4]}-{S['sample_end'][:4]} is an untouched hold-out."),
], size=14.5, gap=10)
stats = [(S["sample_end"], "data through"), ("16", "coins"), (str(S["n_candidates"]), "candidates tested"),
         ("668k", "hourly bars")]
for i, (val, lab) in enumerate(stats):
    x = 7.1 + (i % 2) * 2.85; y = 1.95 + (i // 2) * 1.5
    box(s, x, y, 2.65, 1.3, fill=NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1, shadow=True)
    text(s, x + 0.22, y + 0.15, 2.3, 0.6, [[Rn(val, 24 if len(val) > 6 else 30, WHITE, True, False, HEAD)]])
    text(s, x + 0.22, y + 0.85, 2.3, 0.35, [[Rn(lab.upper(), 11, ICE, True)]])
box(s, 7.1, 5.05, 5.5, 1.55, fill=LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
text(s, 7.35, 5.18, 5.1, 0.35, [[Rn("THEMES", 12, BLUE, True)]])
text(s, 7.35, 5.5, 5.1, 1.1, [[Rn("Payments & Meme: BTC LTC BCH XLM DOGE", 12, NAVY)],
                              [Rn("Large L1: ETH SOL AVAX   |   Alt L1: ADA DOT ATOM ALGO", 12, NAVY)],
                              [Rn("DeFi & Oracle: UNI AAVE COMP LINK", 12, NAVY)]], space_after=2)
pagenum(s)

# =========================================================================== #
# 5. Horizon
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Momentum vs reversal: time horizon", "Daily horizons show momentum; reversal lives at the extremes")
pic(s, "figures/A_horizon_scan.png", 0.5, 1.85, w=8.0, h=4.6)
card(s, 8.85, 1.95, 3.8, 1.55, "Peak momentum", num(hz("Cross-sectional", 14)), "cross-sectional, 14-day look-back")
card(s, 8.85, 3.65, 3.8, 1.55, "1-hour reversal", num(-IH.iloc[0]["Gross Sharpe"]), "gross Sharpe, hourly data", GREEN)
card(s, 8.85, 5.35, 3.8, 1.55, "Cost of 1-day signal", "~95%/yr", "1.3x turnover/day at 20 bps", CORAL)
footer(s, "Opposite of the equity pattern in the brief, consistent with crypto evidence (Dobrynskaya).")
pagenum(s)

# =========================================================================== #
# 6. Activity + seasonality
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Momentum: activity and seasonality", "Volume shocks and weekends strengthen momentum")
pic(s, "figures/B_activity_volume.png", 0.45, 1.8, w=6.3, h=3.0)
pic(s, "figures/C_day_of_week.png", 6.75, 1.8, w=6.3, h=3.0)
bullets(s, 0.7, 5.0, 5.9, 1.9, [
    f"Weighting by volume shock lifts 1-day momentum {num(act(1, 'All coins'))} -> {num(act(1, 'Signal x volume shock'))} and 3-day {num(act(3, 'All coins'))} -> {num(act(3, 'Signal x volume shock'))}.",
    f"Holds in the hold-out (3-day: {num(act(3, 'All coins', 'Gross OOS'))} -> {num(act(3, 'Signal x volume shock', 'Gross OOS'))}).",
], size=13.5, gap=8)
us_wd = SESS[(SESS.day_type == "Weekday") & (SESS.session == "US (13-21 UTC)")]["EW mean bps/hour"].iloc[0]
bullets(s, 7.0, 5.0, 5.8, 1.9, [
    f"TS momentum Sharpe {num(ts_we)} on weekends vs {num(ts_wd)} on weekdays: retail trends persist when institutions are away.",
    f"Hourly: the US session averages {num(us_wd)} bps/hour on weekdays; gains accrue outside US hours.",
], size=13.5, gap=8)
pagenum(s)

# =========================================================================== #
# 7. Themes + technical plays
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Momentum: themes and technical plays", "Themes worked, then decayed; front-running fails on cost")
pic(s, "figures/D_theme_indices.png", 0.45, 1.8, w=7.4, h=3.6)
rows = [("Theme look-back", "Gross IS", "Gross OOS", "Net 20 bps")]
for L in [7, 14, 21, 30]:
    r = THM.loc[f"Theme momentum L={L}d H=1d"]
    rows.append((f"{L} days", num(r["Gross IS"]), num(r["Gross OOS"]), num(r["Net20 Full"])))
grid_table(s, 8.15, 1.9, [1.7, 1.0, 1.05, 1.05], rows, rh=0.45, hl={2}, size=12.5)
box(s, 8.15, 4.4, 4.8, 2.4, fill=NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, shadow=True)
text(s, 8.4, 4.55, 4.4, 0.35, [[Rn("FRONT-RUNNING THE US SESSION", 12, ICE, True)]])
text(s, 8.4, 4.9, 4.4, 0.7, [[Rn(f"{num(fr2['Gross bps/day'])} bps/day", 28, WHITE, True, False, HEAD)]])
text(s, 8.4, 5.6, 4.4, 1.2, [[Rn(f"Coins that led yesterday's US session lead again (Sharpe {num(fr2['Gross Sharpe'])}, t = {num(fr2['t-stat'])}), but a full daily round trip costs more than the edge even at 7 bps.", 12, ICE)]])
text(s, 0.7, 5.6, 7.2, 1.2, [[Rn(f"Theme momentum was the strongest research-period signal (14-day gross Sharpe {num(t14['Gross IS'])}). In 2024-2026 theme moves came in sharp bursts that reversed, and the signal decayed to {num(t14['Gross OOS'])}.", 13.5, NAVY)]])
pagenum(s)

# =========================================================================== #
# 8. Reversal
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Reversal: horizon, uninformed trading, correlation", "Reversal is real; only the slow version pays")
pic(s, "figures/C_intraday_sessions.png", 0.45, 1.8, w=7.3, h=2.8)
lt = SEL.loc[S["reversal_selected"]]
rows = [("Reversal type", "Gross Sharpe", "Net cost", "Turnover")]
rows.append(("1-hour cross-sectional", num(-IH.iloc[0]["Gross Sharpe"]), num(IH.iloc[0]["Net Sharpe @7"], 0) + " @7", num(IH.iloc[0]["Turnover/hour"]) + "/h"))
rows.append(("Market-residual 7d", num(COR.loc["Market-residual reversal L=7d", "Gross Full"]), num(COR.loc["Market-residual reversal L=7d", "Net7 Full"]) + " @7", num(COR.loc["Market-residual reversal L=7d", "Turnover"]) + "/d"))
rows.append(("Theme-residual 60d", num(COR.loc["Theme-residual reversal L=60d", "Gross Full"]), num(COR.loc["Theme-residual reversal L=60d", "Net7 Full"]) + " @7", num(COR.loc["Theme-residual reversal L=60d", "Turnover"]) + "/d"))
rows.append(("Cointegrated pairs", num(COR.loc["Cointegration pairs (Kalman, walk-forward)", "Gross Full"]), num(COR.loc["Cointegration pairs (Kalman, walk-forward)", "Net20 Full"]) + " @20", num(COR.loc["Cointegration pairs (Kalman, walk-forward)", "Turnover"], 3) + "/d"))
rows.append(("60d, skip 14d (selected)", num(lt["Gross Full"]), num(lt["Net7 Full"]) + " @7", num(lt["Turnover"]) + "/d"))
grid_table(s, 7.95, 1.85, [2.3, 0.95, 0.95, 0.85], rows, rh=0.5, hl={5}, size=11.5, head_size=11)
bullets(s, 0.7, 4.85, 7.0, 2.0, [
    ("Short horizon: ", "hour-to-hour moves are liquidity noise and reverse strongly, but turnover makes it a market-maker's edge, not ours."),
    ("Correlation: ", "residuals vs the whole market trend; residuals vs the coin's own theme revert over 1-2 months."),
    ("Long horizon: ", "60-day losers beat 60-day winners - overreaction compressed into weeks."),
], size=13, gap=8)
pagenum(s)

# =========================================================================== #
# 9. Macro
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Macro: volatility and dislocation", "Stress helps reversal; high implied vol breaks momentum")
pic(s, "figures/G_macro_regimes.png", 0.4, 1.75, w=12.5, h=3.8)
card(s, 0.7, 5.55, 3.9, 1.45, "1-day reversal, calm vs volatile",
     f"{num(mac(srv, 'Realized vol (30d, EW market)', 'Low'))} / {num(mac(srv, 'Realized vol (30d, EW market)', 'Mid'))}", "Sharpe: low vs mid realized vol", vsize=26)
card(s, 4.75, 5.55, 3.9, 1.45, "TS momentum, implied vol",
     f"{num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'Low'))} / {num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'High'))}", "Sharpe: low vs high DVOL", CORAL, vsize=26)
box(s, 8.8, 5.55, 3.85, 1.45, fill=NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
text(s, 9.05, 5.65, 3.45, 1.25, [[Rn("Action: switch time-series momentum off when DVOL is in its top tercile (selected on the research period).", 13, WHITE, True)]], anchor=MSO_ANCHOR.MIDDLE)
pagenum(s)

# =========================================================================== #
# 10. Execution
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Execution", "Turnover, not signal discovery, is the binding constraint")
pic(s, "figures/H_cost_sweep.png", 0.45, 1.8, w=6.6, h=3.4)
mex, rex = S["execution_selected"]["Momentum"], S["execution_selected"]["Reversal"]
rows = [("Momentum book", "Turnover", "Gross", "7 bps", "20 bps")]
for v in ["Daily rebalance", "Hold 7d (overlapping)", "No-trade band 2%", "No-trade band 5%"]:
    r = EXE[(EXE.Book == "Momentum") & (EXE.Execution == v)].iloc[0]
    rows.append((v, num(r.Turnover, 3), num(r["Sharpe gross"]), num(r["Sharpe limit 7bps"]), num(r["Sharpe market 20bps"])))
hl = {1 + ["Daily rebalance", "Hold 7d (overlapping)", "No-trade band 2%", "No-trade band 5%"].index(mex)} if mex in ["Daily rebalance", "Hold 7d (overlapping)", "No-trade band 2%", "No-trade band 5%"] else set()
grid_table(s, 7.35, 1.9, [2.3, 0.95, 0.75, 0.75, 0.8], rows, rh=0.5, hl=hl, size=12, head_size=11.5)
bullets(s, 0.7, 5.45, 12, 1.5, [
    ("Bands beat holding periods: ", f"a 2% no-trade band cuts momentum turnover without diluting the signal (20 bps Sharpe {num(EXE[(EXE.Book=='Momentum')&(EXE.Execution=='Daily rebalance')]['Sharpe market 20bps'].iloc[0])} -> {num(EXE[(EXE.Book=='Momentum')&(EXE.Execution=='No-trade band 2%')]['Sharpe market 20bps'].iloc[0])})."),
    ("Limit orders: ", f"the slow reversal book is worked passively at 7 bps; the combined book stays positive to ~50 bps (Sharpe {num(SWP.loc[50, 'Combined'])})."),
], size=13.5, gap=8)
pagenum(s)

# =========================================================================== #
# 11. Selection + weighting
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Selection and weighting", "Diversify the momentum bet, then combine with reversal")
comp = S["momentum_components"]
box(s, 0.7, 1.85, 5.9, 2.55, fill=LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, shadow=True)
text(s, 0.95, 1.98, 5.5, 0.35, [[Rn("MOMENTUM ENSEMBLE (20 BPS)", 12, BLUE, True)]])
bullets(s, 0.95, 2.35, 5.5, 1.5, comp, size=13, gap=4)
text(s, 0.95, 3.5, 5.5, 0.35, [[Rn("REVERSAL (7 BPS)", 12, BLUE, True)]])
text(s, 0.95, 3.82, 5.5, 0.5, [[Rn(S["reversal_selected"], 13, NAVY)]])
rows = [("Weighting", "IS", "OOS", "Full")]
for m in WTS.index:
    rows.append((m, num(WTS.loc[m, "Sharpe IS"]), num(WTS.loc[m, "Sharpe OOS"]), num(WTS.loc[m, "Sharpe"])))
grid_table(s, 7.0, 1.85, [2.85, 0.85, 0.85, 0.85], rows, rh=0.5, hl={1 + list(WTS.index).index(best_m)}, size=12.5)
rows = [("If the momentum sleeve were...", "Hold-out Sharpe")]
labs = ["Ensemble (final)", "Single IS-best pick", "TS momentum only"]
for lab, (_, r) in zip(labs, RB.iterrows()):
    rows.append((lab, num(r["Combined Sharpe OOS"])))
grid_table(s, 0.7, 4.7, [3.6, 2.3], rows, rh=0.48, hl={1}, size=12.5)
text(s, 7.0, 4.75, 5.6, 2.0, [[Rn(f"Momentum and reversal correlate at only {num(CORR.loc['Momentum ensemble', 'Reversal'])}, so every weighting scheme beats either sleeve alone. {best_m} won on the research period; simpler risk-based weights did slightly better in the hold-out.", 13.5, NAVY)],
                              [Rn("Picking the single best momentum strategy would have failed out of sample - the main lesson on selection risk.", 13.5, CORAL, True)]], space_after=8)
pagenum(s)

# =========================================================================== #
# 12. Performance table
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Performance evaluation", "Returns, volatility, Sharpe, drawdown, alpha and beta")
keys = [CMB, CMB20, MOMK, REVK, PRS, EW, BTC]
labs = ["Combined portfolio", "Combined (all at 20 bps)", "Momentum ensemble", "Reversal (7 bps)",
        "Cointegration pairs", "Equal-weight crypto", "Buy & hold BTC"]
rows = [("Full backtest", "Return", "Vol", "Sharpe", "Max DD", "Alpha", "Beta", "OOS Sharpe")]
for k, lab in zip(keys, labs):
    r = FULL.loc[k]
    rows.append((lab, pct(r["Ann.Return"]), pct(r["Ann.Vol"]), num(r["Sharpe"]), pct(r["MaxDD"]),
                 pct(r["Alpha"]), num(r["Beta"]), num(OOS.loc[k, "Sharpe"])))
yy = grid_table(s, 0.7, 1.85, [3.1, 1.15, 1.15, 1.1, 1.2, 1.2, 1.0, 1.35], rows, rh=0.55, hl={1}, size=13)
text(s, 0.7, yy + 0.15, 12, 0.6, [[Rn(f"{S['bt_start']} to {S['sample_end']}. Alpha / beta vs Bitcoin (daily regression, Newey-West). Combined alpha t-stat {num(cf['Alpha t'])}. OOS = hold-out {S['oos_start']} onward.", 12, GREY, False, True)]])
pagenum(s)

# =========================================================================== #
# 13. Equity + drawdown
# =========================================================================== #
s = slide(); bg(s, WHITE)
title_bar(s, "Results", "Growth of $1: steady, market-neutral compounding")
pic(s, "figures/J_equity_curves.png", 0.45, 1.7, w=8.1, h=3.75)
rows = [("Combined vs BTC", "Sharpe", "BTC Sharpe", "Alpha / yr", "Max DD", "BTC Max DD")]
for lab, df in [("Research period", INS), ("Hold-out", OOS), ("Full", FULL)]:
    rows.append((lab, num(df.loc[CMB, "Sharpe"]), num(df.loc[BTC, "Sharpe"]), pct(df.loc[CMB, "Alpha"]),
                 pct(df.loc[CMB, "MaxDD"]), pct(df.loc[BTC, "MaxDD"])))
grid_table(s, 0.7, 5.5, [2.0, 1.1, 1.2, 1.25, 1.1, 1.25], rows, rh=0.36, hl={3}, size=11.5, head_size=11)
card(s, 8.85, 1.9, 3.8, 1.55, "Research period Sharpe", num(ci["Sharpe"]), f"{S['bt_start'][:4]}-{S['is_end'][:4]}, max DD {pct(ci['MaxDD'])}")
card(s, 8.85, 3.6, 3.8, 1.55, "Hold-out Sharpe", num(co_["Sharpe"]), f"2024-2026, alpha {pct(co_['Alpha'])}/yr", GOLD)
card(s, 8.85, 5.3, 3.8, 1.55, "Beta to BTC", num(cf["Beta"]), f"BTC drawdown {pct(FULL.loc[BTC, 'MaxDD'])}", BLUE, dark=True)
pagenum(s)

# =========================================================================== #
# 14. Conclusion
# =========================================================================== #
s = slide(); bg(s, NAVY)
box(s, 8.8, -1.4, 6, 6, fill=NAVY2, shape=MSO_SHAPE.OVAL)
text(s, 0.8, 0.7, 12, 0.4, [[Rn("CONCLUSION", 14, ICE, True)]])
text(s, 0.8, 1.15, 11.5, 1.0, [[Rn("Signals exist; execution and diversification decide", 32, WHITE, True, False, HEAD)]])
bullets(s, 0.8, 2.4, 8.2, 3.4, [
    ("Momentum at days-to-weeks, reversal at hours and months. ", "The brief's hypotheses on activity, seasonality, themes and macro are all visible in the data."),
    ("Costs kill fast signals. ", "Bands, slow signals and limit orders turn gross edges into net ones."),
    ("Combine uncorrelated sleeves. ", f"Momentum + reversal: Sharpe {num(cf['Sharpe'])}, beta {num(cf['Beta'])}."),
    ("Expect decay. ", f"Hold-out Sharpe {num(co_['Sharpe'])}; next step is live paper trading."),
], size=16, gap=14, color=WHITE, mcolor=ICE)
box(s, 0.8, 6.0, 11.7, 1.05, fill=NAVY2, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
fin = [("Net Sharpe", num(cf["Sharpe"])), ("Alpha / yr", pct(cf["Alpha"])),
       ("Beta", num(cf["Beta"])), ("Max DD", pct(cf["MaxDD"]))]
fx = 1.1
for lab, val in fin:
    text(s, fx, 6.12, 2.8, 0.55, [[Rn(val, 26, WHITE, True, False, HEAD)]])
    text(s, fx, 6.66, 2.8, 0.3, [[Rn(lab.upper(), 11.5, ICE, True)]])
    fx += 2.9
pagenum(s)

prs.save(OUTFILE)
print(f"saved {OUTFILE} with {len(prs.slides._sldIdLst)} slides")
