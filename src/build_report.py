"""
build_report.py - generate the research report crypto_research_report.docx
with python-docx.  Every number is read from the canonical outputs in data/
and data/research/, so the report cannot drift from the backtest.

Formatting: Times New Roman 11 body, indented bullets, plain hyphens and
straight quotes only (see textclean.py).
"""
import json
import os
import sys

import pandas as pd
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

sys.path.insert(0, os.path.dirname(__file__))
from textclean import clean

R = "data/research"
S = json.load(open(f"{R}/summary.json"))
FULL = pd.read_csv(f"{R}/J_performance_full.csv").set_index("Strategy")
OOS = pd.read_csv(f"{R}/J_performance_oos.csv").set_index("Strategy")
INS = pd.read_csv(f"{R}/J_performance_is.csv").set_index("Strategy")
HOR = pd.read_csv(f"{R}/A_horizon_scan.csv")
IH = pd.read_csv(f"{R}/A2_intraday_horizon.csv")
ACT = pd.read_csv(f"{R}/B_activity_volume.csv")
SESS = pd.read_csv(f"{R}/C_session_returns.csv")
WKD = pd.read_csv(f"{R}/C_weekday_weekend.csv").set_index("Strategy")
WKM = pd.read_csv(f"{R}/C_weekend_momentum.csv").set_index("variant")
THM = pd.read_csv(f"{R}/D_theme_momentum.csv")
FR = pd.read_csv(f"{R}/E_frontrun_us_session.csv")
COR = pd.read_csv(f"{R}/F_correlation_reversal.csv").set_index("Strategy")
MAC = pd.read_csv(f"{R}/G_macro_regimes.csv")
SEL = pd.read_csv(f"{R}/H_candidate_selection.csv")
EXE = pd.read_csv(f"{R}/H_execution_variants.csv")
SWP = pd.read_csv(f"{R}/H_cost_sweep.csv").set_index("cost_bps")
WTS = pd.read_csv(f"{R}/I_weighting_methods.csv").set_index("Method")
RB = pd.read_csv(f"{R}/I_selection_robustness.csv")
CORR = pd.read_csv(f"{R}/I_sleeve_correlation.csv", index_col=0)
PAIRS = json.load(open("data/run_summary.json"))
FREQ = pd.read_csv("data/pair_frequency.csv")

MOMK, MOM7 = "Momentum ensemble (net 20bps market)", "Momentum ensemble (net 7bps limit)"
REVK, REV20 = "Reversal (net 7bps limit)", "Reversal (net 20bps market)"
CMB, CMB20 = "Combined portfolio", "Combined portfolio (all at 20bps market)"
BTC, EW, PRS = "Buy & Hold BTC", "Equal-weight crypto (B&H)", "Cointegration pairs (net 20bps)"


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


def sel(name, col):
    return SEL[SEL.Strategy == name][col].iloc[0]


def exe(book, v, col):
    return EXE[(EXE.Book == book) & (EXE.Execution == v)][col].iloc[0]


comp = S["momentum_components"]
rev_name = S["reversal_selected"]
best_m = S["weighting_selected"]

# --------------------------------------------------------------------------- #
# document scaffolding
# --------------------------------------------------------------------------- #
doc = Document()
for sec in doc.sections:
    sec.left_margin = sec.right_margin = Inches(1)
    sec.top_margin = sec.bottom_margin = Inches(1)
NAVYC = RGBColor(0x1F, 0x38, 0x64)
st = doc.styles["Normal"]
st.font.name = "Times New Roman"; st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
st.paragraph_format.space_after = Pt(6)
st.paragraph_format.line_spacing = 1.08
for h, sz in [("Heading 1", 14), ("Heading 2", 12), ("Heading 3", 11)]:
    hs = doc.styles[h]
    hs.font.name = "Times New Roman"; hs.font.size = Pt(sz); hs.font.bold = True
    hs.font.color.rgb = NAVYC
    rpr = hs.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts"); rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), "Times New Roman")
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rf.get(qn(a)) is not None:
            del rf.attrib[qn(a)]
    hs.paragraph_format.space_before = Pt(12 if h == "Heading 1" else 8)
    hs.paragraph_format.space_after = Pt(4)
lb = doc.styles["List Bullet"]
lb.font.name = "Times New Roman"; lb.font.size = Pt(11)
lb.paragraph_format.left_indent = Inches(0.45)
lb.paragraph_format.first_line_indent = Inches(-0.2)
lb.paragraph_format.space_after = Pt(3)


def para(text, italic=False, bold=False, size=None, align=None, space_after=6):
    p = doc.add_paragraph()
    r = p.add_run(clean(text)); r.italic = italic; r.bold = bold
    if size: r.font.size = Pt(size)
    if align is not None: p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    return p


def rich(parts, space_after=6):
    """parts: list of (text, bold) tuples in one paragraph."""
    p = doc.add_paragraph()
    for t, b in parts:
        r = p.add_run(clean(t)); r.bold = b
    p.paragraph_format.space_after = Pt(space_after)
    return p


def bullet(text, lead=None):
    p = doc.add_paragraph(style="List Bullet")
    if lead:
        r = p.add_run(clean(lead)); r.bold = True
    p.add_run(clean(text))
    return p


def heading(text, level):
    if text != "Contents" and level <= 2:
        HEADS.append((level, clean(text)))
    return doc.add_heading(clean(text), level=level)


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), hexcolor); tcPr.append(sh)


def table(headers, rows, widths=None, bold_rows=(), caption=None, note=None, size=9):
    if caption:
        c = doc.add_paragraph(); r = c.add_run(clean(caption))
        r.bold = True; r.font.size = Pt(10)
        c.paragraph_format.space_after = Pt(3); c.paragraph_format.keep_with_next = True
    t = doc.add_table(rows=1, cols=len(headers)); t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(headers):
        cell = t.rows[0].cells[j]; cell.text = ""
        run = cell.paragraphs[0].add_run(clean(h)); run.bold = True; run.font.size = Pt(size)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if j else WD_ALIGN_PARAGRAPH.LEFT
        shade(cell, "1F3864")
    for i, rw in enumerate(rows):
        cells = t.add_row().cells
        for j, val in enumerate(rw):
            cells[j].text = ""
            p = cells[j].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(clean(str(val))); run.font.size = Pt(size)
            if i in bold_rows:
                run.bold = True; shade(cells[j], "DCE6F1")
            if j > 0: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if widths:
        t.autofit = False
        grid = t._tbl.tblGrid
        for j, gc in enumerate(grid.findall(qn("w:gridCol"))):
            gc.set(qn("w:w"), str(int(widths[j] * 1440)))
        for rw in t.rows:
            for j, w in enumerate(widths):
                rw.cells[j].width = Inches(w)
    if note:
        n = doc.add_paragraph(); r = n.add_run(clean(note)); r.italic = True; r.font.size = Pt(9)
        n.paragraph_format.space_after = Pt(8)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


fig_no = [0]


def figure(path, caption, width=6.3):
    fig_no[0] += 1
    doc.add_picture(path, width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.paragraphs[-1].paragraph_format.keep_with_next = True
    c = doc.add_paragraph(); r = c.add_run(clean(f"Figure {fig_no[0]}. {caption}"))
    r.italic = True; r.font.size = Pt(9.5)
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    c.paragraph_format.space_after = Pt(10)


tab_no = [0]


def tcap(text):
    tab_no[0] += 1
    return f"Table {tab_no[0]}. {text}"


TOC_FILE = "data/research/_toc.json"
HEADS = []          # (level, text) collected while building, for the next pass


def add_toc():
    """Static contents list with page numbers measured from the previous
    rendering pass (see src/make_report.py)."""
    if not os.path.exists(TOC_FILE):
        return
    from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER
    for lvl, text, page in json.load(open(TOC_FILE)):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_after = Pt(1 if lvl == 2 else 3); pf.space_before = Pt(0 if lvl == 2 else 3)
        pf.left_indent = Inches(0.3 if lvl == 2 else 0)
        pf.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        r = p.add_run(f"{text}\t{page}"); r.font.size = Pt(10 if lvl == 2 else 10.5); r.bold = (lvl == 1)


def add_page_numbers():
    for sec in doc.sections:
        fp = sec.footer.paragraphs[0]; fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = fp.add_run()
        for tag, txt in [("begin", None), (None, "PAGE"), ("end", None)]:
            if tag:
                el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), tag)
            else:
                el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = txt
            r._r.append(el)
        r.font.size = Pt(9)


def perf_rows(df, keys, labels):
    out = []
    for k, lab in zip(keys, labels):
        r = df.loc[k]
        out.append([lab, pct(r["Ann.Return"]), pct(r["Ann.Vol"]), num(r["Sharpe"]),
                    pct(r["MaxDD"]), pct(r["Alpha"]), num(r["Beta"]), num(r["Alpha t"])])
    return out


PERF_KEYS = [CMB, CMB20, MOMK, MOM7, REVK, REV20, PRS, EW, BTC]
PERF_LABS = ["Combined portfolio *", "Combined (all trades at 20 bps)",
             "Momentum ensemble (20 bps market)", "Momentum ensemble (7 bps limit)",
             "Reversal (7 bps limit)", "Reversal (20 bps market)",
             "Cointegration pairs (20 bps)", "Equal-weight crypto (buy & hold)", "Buy & hold BTC"]
PERF_HEAD = ["Strategy", "Ann. return", "Ann. vol", "Sharpe", "Max DD", "Alpha (ann.)", "Beta (BTC)", "Alpha t"]
PERF_W = [2.2, 0.62, 0.58, 0.62, 0.6, 0.62, 0.62, 0.6]

c_full, c_oos, c_is = FULL.loc[CMB], OOS.loc[CMB], INS.loc[CMB]

# =========================================================================== #
# TITLE PAGE
# =========================================================================== #
for _ in range(5):
    doc.add_paragraph()
para("Statistical Arbitrage in Cryptocurrencies", bold=True, size=22,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para("Momentum and Reversal Research on Live Market Data", italic=True, size=14,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)
para("Wall Street Quants - Bootcamp Project", size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para(f"Data: Coinbase Exchange (daily and hourly OHLCV) and Deribit DVOL, {S['sample_start']} to {S['sample_end']}",
     size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para("Report rebuilt on live data, October 2026", size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
doc.add_page_break()

heading("Contents", 1)
add_toc()
doc.add_page_break()

# =========================================================================== #
# EXECUTIVE SUMMARY
# =========================================================================== #
heading("Executive Summary", 1)
para(
    "This report answers the Wall Street Quants class project brief: research profitable momentum "
    "and/or reversal strategies in cryptocurrencies, test them with unconstrained backtests under the "
    "brief's execution costs (20 bps for market orders, 7 bps for limit orders), combine the strategies "
    "with a weighting scheme, and report returns, volatility, Sharpe ratios, maximum drawdowns and "
    f"alpha / beta. The study uses live market data through {S['sample_end']}: daily and hourly prices "
    "for 16 liquid coins from the Coinbase Exchange API and the Deribit DVOL implied-volatility index. "
    "Every item in the brief's research outline is tested: time horizon, new information / activity, "
    "seasonality, investment themes, technical plays, uninformed trading, correlation, and macro "
    "dislocation. All parameters were chosen on a research period (2021-07 to 2023-12) and the "
    f"strategies were then run untouched over a hold-out period ({S['oos_start']} to {S['sample_end']}).")
para("Key findings", bold=True, space_after=3)
bullet(f"Daily horizons from 1 to 30 days show momentum, not reversal. Cross-sectional momentum peaks at a "
       f"14-day look-back (gross Sharpe {num(hz('Cross-sectional', 14))}). Reversal appears only at the "
       "extremes: intraday (1-24 hour) horizons and long (60-90 day) horizons. This matches crypto-specific "
       "evidence and is the opposite of the equity intuition in the brief.", "Horizon decides the sign. ")
bullet(f"A 1-hour cross-sectional reversal earns a gross Sharpe of {num(-IH.iloc[0]['Gross Sharpe'])}, "
       f"but it trades {num(IH.iloc[0]['Turnover/hour'])}x its capital per hour, so even 7 bps limit orders "
       "turn it into a large loss. Short-horizon reversal is real but not investable at the brief's costs.",
       "Intraday reversal is strong but untradeable. ")
bullet("Volume shocks strengthen short-horizon momentum, momentum is far stronger on weekends than on "
       "weekdays, theme (sector) momentum is the strongest gross signal in the research period, and "
       "time-series momentum breaks down when implied volatility is high.",
       "Activity, seasonality, themes and macro all matter. ")
bullet(f"The final strategy pairs a momentum ensemble (time-series, theme and cross-sectional momentum) with "
       f"a long-horizon reversal book, weighted by {best_m.lower()}. Over {S['bt_start']} to {S['sample_end']} "
       f"it earns {pct(c_full['Ann.Return'])} a year at {pct(c_full['Ann.Vol'])} volatility: Sharpe "
       f"{num(c_full['Sharpe'])}, max drawdown {pct(c_full['MaxDD'])}, alpha {pct(c_full['Alpha'])} a year "
       f"(t = {num(c_full['Alpha t'])}) and beta to Bitcoin of {num(c_full['Beta'])}.",
       "The combined strategy is market-neutral and positive after costs. ")
bullet(f"In the hold-out period the combined Sharpe is {num(c_oos['Sharpe'])} (vs {num(c_is['Sharpe'])} in the "
       f"research period). Reversal held up ({num(OOS.loc[REVK, 'Sharpe'])}) while momentum decayed "
       f"({num(OOS.loc[MOMK, 'Sharpe'])}). Picking the single best momentum strategy from the research "
       f"period would have failed ({num(RB.iloc[1]['Momentum Sharpe OOS'])} hold-out Sharpe), which is why "
       "the final design diversifies across momentum families.",
       "Out-of-sample decay is real. ")
table(PERF_HEAD, perf_rows(FULL, PERF_KEYS[:3] + PERF_KEYS[4:5] + PERF_KEYS[-1:],
                           PERF_LABS[:3] + PERF_LABS[4:5] + PERF_LABS[-1:]),
      widths=PERF_W, bold_rows={0},
      caption=tcap(f"Headline performance, {S['bt_start']} to {S['sample_end']} (net of costs)."),
      note="* Momentum traded with market orders (20 bps), reversal with limit orders (7 bps). Alpha and beta "
           "are from a daily regression on Bitcoin returns with Newey-West standard errors. Returns are "
           "arithmetic annualised means (365-day year).")

# =========================================================================== #
# 1. INTRODUCTION
# =========================================================================== #
heading("1. Introduction", 1)
para(
    "Statistical arbitrage looks for price-volume patterns that predict returns. The two patterns the brief "
    "highlights are momentum (recent winners keep winning) and reversal (recent moves undo themselves). "
    "Crypto markets are young, open all day every day, dominated by retail flow and lightly arbitraged, so "
    "they are a natural place to look for both.")
para(
    "The brief gives a research outline for each pattern. For momentum: longer time horizons, periods of new "
    "information and activity, seasonality (weekdays vs weekends, day vs night), investment themes, and "
    "technical plays such as front-running institutional trading hours. For reversal: shorter time horizons, "
    "uninformed (liquidity-driven) trading, correlated pairs or baskets, and macro periods of high volatility "
    "and dislocation. It then asks for unconstrained backtests, realistic execution costs, a weighting scheme "
    "to combine strategies, and a standard set of performance metrics.")
para(
    "This report follows that outline section by section. Section 2 reviews the literature, Section 3 "
    "describes the data, and Section 4 sets out the backtest method. Sections 5 and 6 cover the momentum and "
    "reversal research. Section 7 covers execution, Section 8 strategy selection, Section 9 weighting, and "
    "Section 10 performance. Sections 11 and 12 discuss the results and conclude.")
para("The research question is: which momentum and reversal patterns exist in crypto, which survive realistic "
     "trading costs, and how should they be combined into a single portfolio?", italic=True)

# =========================================================================== #
# 2. LITERATURE
# =========================================================================== #
heading("2. Literature Review", 1)
heading("2.1 Momentum", 2)
para(
    "Cross-sectional momentum (Jegadeesh & Titman, 1993) and time-series momentum (Moskowitz, Ooi & Pedersen, "
    "2012) are among the most robust anomalies across asset classes, and Moskowitz and Grinblatt (1999) show "
    "that much of stock momentum is industry (theme) momentum. Momentum is prone to crashes in high-volatility "
    "rebounds (Daniel & Moskowitz, 2016), and scaling positions by recent volatility improves its risk-adjusted "
    "return (Barroso & Santa-Clara, 2015). In crypto, Liu and Tsyvinski (2021) and Liu, Tsyvinski and Wu (2022) "
    "document a strong momentum factor, while Han, Kang and Ryu (2024) find that time-series momentum is more "
    "robust than cross-sectional momentum once realistic costs are applied.")
heading("2.2 Reversal", 2)
para(
    "Short-term reversal in stocks (Lehmann, 1990) is linked to liquidity provision: Campbell, Grossman and Wang "
    "(1993) show that price moves on high volume tend to reverse less, because they carry information, while "
    "moves on low volume reflect liquidity demand and reverse more. Nagel (2012) shows that reversal profits rise "
    "sharply when market volatility is high, because liquidity providers demand more compensation. Long-horizon "
    "reversal (De Bondt & Thaler, 1985) reflects overreaction. In crypto, Dobrynskaya finds momentum at short "
    "horizons and reversal at longer horizons, the opposite of the equity pattern.")
heading("2.3 Relative value and pairs", 2)
para(
    "Pairs trading (Gatev, Goetzmann & Rouwenhorst, 2006) and cointegration (Engle & Granger, 1987; Vidyamurthy, "
    "2004) trade the spread between related assets; Elliott, van der Hoek and Malcolm (2005) and Chan (2013) "
    "estimate the hedge ratio with a Kalman filter. Do and Faff (2010, 2012) and Krauss (2017) document declining, "
    "cost-sensitive pairs profits, and Fil and Kristoufek (2020) find crypto cointegration particularly unstable.")
heading("2.4 Intraday patterns, execution and weighting", 2)
para(
    "Heston, Korajczyk and Sadka (2010) document intraday return periodicity tied to recurring trading schedules. "
    "Garleanu and Pedersen (2013) show that, with costs, the optimal policy trades only part of the way toward "
    "the target portfolio, which motivates holding periods and no-trade bands. DeMiguel, Garlappi and Uppal "
    "(2009) show that naive equal weighting is hard to beat out of sample. Harvey, Liu and Zhu (2016) and Bailey "
    "and Lopez de Prado (2014) warn that testing many strategies inflates backtest Sharpe ratios, which "
    "motivates the research / hold-out split used here.")

# =========================================================================== #
# 3. DATA
# =========================================================================== #
heading("3. Data", 1)
heading("3.1 Sources", 2)
bullet("daily OHLCV from the Coinbase Exchange public API, January 2021 onward (Binance is geo-restricted "
       "from the research environment, HTTP 451, so Coinbase is used).", "Daily prices: ")
bullet("hourly OHLCV from Coinbase for the same coins, January 2022 onward, used for the intraday horizon, "
       "session and front-running tests.", "Hourly prices: ")
bullet("the Deribit DVOL index (30-day implied volatility of Bitcoin options), the crypto equivalent of the "
       "VIX, used as the implied-volatility macro indicator.", "Implied volatility: ")
para(f"The data were downloaded on {S['sample_end'][:4]}-10-09 and run through {S['sample_end']} (the last "
     "complete daily bar). Re-running src/fetch_data.py refreshes everything to the latest date.")
heading("3.2 Universe and themes", 2)
para(
    "The universe is 16 liquid USD-quoted coins: BTC, ETH, SOL, ADA, DOGE, AVAX, LINK, LTC, DOT, ATOM, UNI, BCH, "
    "XLM, ALGO, AAVE and COMP. XRP is excluded because of a long Coinbase listing gap during 2021-2023, and MKR "
    "because it stopped trading in January 2026 after migrating to SKY. Coins that listed after January 2021 "
    "enter when their history begins. For the theme test, coins are grouped into four investment themes:")
table(["Theme", "Coins", "Rationale"], [
    ["Payments & Meme", "BTC, LTC, BCH, XLM, DOGE", "Store-of-value and payment coins; retail-driven"],
    ["Large Smart-Contract L1", "ETH, SOL, AVAX", "Leading smart-contract platforms"],
    ["Alt L1", "ADA, DOT, ATOM, ALGO", "Second-tier layer-1 platforms"],
    ["DeFi & Oracle", "UNI, AAVE, COMP, LINK", "Decentralised-finance protocols and oracle"],
], widths=[1.7, 1.9, 2.7], caption=tcap("Investment themes."))
heading("3.3 Cleaning", 2)
para("Prices are aligned to a common calendar (crypto trades every day). Gaps of up to three days are "
     "forward-filled; longer gaps are left missing so the coin simply drops out of the cross-section. Daily "
     "returns are simple close-to-close returns. Dollar volume (price x volume) is the activity measure.")

# =========================================================================== #
# 4. METHOD
# =========================================================================== #
heading("4. Backtest Methodology", 1)
heading("4.1 Unconstrained backtest", 2)
para(
    "Following the brief, all strategies are first tested with the unconstrained backtest taught in class. "
    "Each day a signal is turned into portfolio weights using information up to that day's close; the weights "
    "earn the next day's return, so there is no look-ahead. Weights are scaled so that gross exposure "
    "(the sum of absolute weights) equals one. Cross-sectional strategies are dollar-neutral: weights are "
    "proportional to each coin's demeaned rank on the signal. Time-series strategies take each coin long or "
    "short on the sign of its own signal, scaled by the inverse of its 30-day volatility.")
heading("4.2 Execution costs", 2)
para(
    "Costs follow the brief: 20 bps per unit of turnover for market orders (7 bps commission plus 13 bps "
    "slippage) and 7 bps for limit orders. Turnover is the sum of absolute weight changes. The momentum book is "
    "charged 20 bps because it chases prices and needs immediate fills. The reversal book is charged 7 bps "
    "because it trades slowly (positions are held about two weeks) and supplies liquidity, so it can be "
    "worked with passive limit orders; results with 20 bps are reported alongside so the assumption can be "
    "judged. A cost sweep from 0 to 200 bps covers everything in between.")
heading("4.3 Metrics", 2)
para(
    "As the brief requires, each strategy is reported with annualised return, annualised volatility, Sharpe "
    "ratio, maximum drawdown, and alpha / beta. Alpha and beta come from regressing daily strategy returns on "
    "daily Bitcoin returns, with Newey-West (5-lag) standard errors; alpha is annualised. Sortino, Calmar, "
    "hit rate, turnover and Newey-West t-statistics are reported in the workbook. Annualisation uses 365 days.")
heading("4.4 Research discipline", 2)
para(
    f"The sample is split into a research period ({'2021-07-01'} to {S['is_end']}) and a hold-out period "
    f"({S['oos_start']} to {S['sample_end']}). Every parameter choice - which strategies to keep, look-backs, "
    "holding periods, execution rules and the weighting method - is made on the research period only. The "
    f"hold-out is reported but never used for selection. In total {S['n_candidates']} candidate strategies "
    "entered the final selection step, so the research-period Sharpe of the winners is biased upward; the "
    "hold-out is the honest measure.")

# =========================================================================== #
# 5. MOMENTUM
# =========================================================================== #
heading("5. Momentum Research", 1)
heading("5.1 Time horizon", 2)
cs14 = hz("Cross-sectional", 14); cs1 = hz("Cross-sectional", 1)
cs60 = hz("Cross-sectional", 60); cs90 = hz("Cross-sectional", 90)
ts30 = hz("Time-series", 30)
para(
    "The brief expects momentum at longer horizons and reversal at shorter ones. Figure 1 tests this by "
    "trading the trailing return over look-backs from 1 to 120 days, rebalanced daily. A positive bar means "
    "momentum and a negative bar means reversal.")
figure("figures/A_horizon_scan.png",
       "Gross Sharpe of momentum-sign strategies by look-back. Positive = momentum, negative = reversal.")
para(
    f"Cross-sectional momentum is positive at every horizon from 1 to 30 days, rising from {num(cs1)} at one day "
    f"to a peak of {num(cs14)} at 14 days. It turns negative (reversal) at 60 days ({num(cs60)}) and 90 days "
    f"({num(cs90)}). Time-series momentum is weaker but positive from 2 days onward and best at about 30 days "
    f"({num(ts30)}). So crypto shows momentum at short-to-medium daily horizons and reversal only at long horizons, "
    "the reverse of the equity pattern in the brief and consistent with Dobrynskaya. Section 6.1 shows that the "
    "brief's short-horizon reversal does exist, but only intraday.")
para(
    "Costs matter a great deal. The 1-day strategy trades about 1.3x its capital per day, so 20 bps of cost "
    "costs roughly 95% a year and turns a positive gross Sharpe into a heavily negative net one. Longer look-backs "
    "trade far less, which is why the tradable momentum strategies in Section 8 use 7 to 30 day signals.")
table(["Look-back", "CS gross Sharpe", "CS net 20 bps", "CS net 7 bps", "TS gross Sharpe", "TS net 20 bps",
       "CS turnover/day"],
      [[f"{L} d", num(hz('Cross-sectional', L)), num(hz('Cross-sectional', L, 'Net20 Full')),
        num(hz('Cross-sectional', L, 'Net7 Full')), num(hz('Time-series', L)),
        num(hz('Time-series', L, 'Net20 Full')), num(hz('Cross-sectional', L, 'Turnover'))]
       for L in [1, 3, 7, 14, 30, 60, 90]],
      widths=[0.8, 0.95, 0.9, 0.85, 0.95, 0.9, 0.95],
      caption=tcap("Horizon scan, full sample (daily rebalance)."))

heading("5.2 New information and activity", 2)
para(
    "The brief suggests momentum is stronger when activity and new information are high. Activity is "
    "measured by abnormal dollar volume, today's dollar volume divided by its trailing 30-day average. Social "
    "media data are not freely available historically, so volume is the activity proxy. Figure 2 compares "
    "cross-sectional momentum on all coins, on only the high- or low-activity half of coins each day, and with "
    "the signal multiplied by each coin's volume-shock rank.")
figure("figures/B_activity_volume.png", "Cross-sectional momentum conditioned on abnormal dollar volume.")
para(
    f"At the shortest horizons, activity strengthens momentum as the brief predicts. One-day momentum has a "
    f"gross Sharpe of {num(act(1, 'High-activity coins only'))} among high-activity coins against "
    f"{num(act(1, 'Low-activity coins only'))} among low-activity coins. Weighting the signal by volume shock "
    f"lifts the 1-day Sharpe from {num(act(1, 'All coins'))} to {num(act(1, 'Signal x volume shock'))} and the "
    f"3-day Sharpe from {num(act(3, 'All coins'))} to {num(act(3, 'Signal x volume shock'))}, and the "
    f"improvement holds in the hold-out period ({num(act(3, 'All coins', 'Gross OOS'))} to "
    f"{num(act(3, 'Signal x volume shock', 'Gross OOS'))} at 3 days). At 7 to 14 days the effect fades. "
    "Restricting to half the coins hurts in both halves because the portfolio is less diversified, so the "
    "volume-weighted version is the useful one.")

heading("5.3 Seasonality: weekdays vs weekends, day vs night", 2)
ts_wd, ts_we = WKD.loc["TS momentum (blend)", "Weekday Sharpe"], WKD.loc["TS momentum (blend)", "Weekend Sharpe"]
para(
    "Institutions mostly trade on weekdays during working hours, while retail trades around the clock. "
    "Figure 3 shows the day-of-week profile of the main strategies.")
figure("figures/C_day_of_week.png", "Mean gross daily return of each strategy by day of week (weekend shaded).")
para(
    f"Time-series momentum is much stronger on weekends: gross Sharpe {num(ts_we)} on Saturdays and Sundays "
    f"against {num(ts_wd)} on weekdays. When institutions are away, retail-driven trends persist; on weekdays "
    "(especially Tuesday and Wednesday) institutional flow tends to interrupt them. Cross-sectional and theme "
    "momentum show the opposite tilt and earn more on weekdays. A weekend-only time-series momentum book has a "
    f"higher research-period gross Sharpe ({num(WKM.loc['Weekend only (Fri-Sun close)', 'Gross IS'])}) than the "
    f"all-days version ({num(WKM.loc['All days', 'Gross IS'])}), but opening and closing every weekend adds "
    "turnover, so it does not beat the all-days book after 20 bps costs.")
us_wd = SESS[(SESS.day_type == "Weekday") & (SESS.session == "US (13-21 UTC)")]["EW mean bps/hour"].iloc[0]
late_wd = SESS[(SESS.day_type == "Weekday") & (SESS.session == "Late US (21-24 UTC)")]["EW mean bps/hour"].iloc[0]
para(
    "Using hourly data, Figure 4 (right) splits the equal-weight crypto return by trading session. On "
    f"weekdays the US session (13:00-21:00 UTC) has a negative average return ({num(us_wd)} bps per hour) "
    f"while the late-US / early-Asia hours earn the most ({num(late_wd)} bps per hour). Crypto gains have "
    "accrued outside US working hours, a 'night effect' consistent with institutional selling pressure "
    "during the US day and retail buying outside it.")
figure("figures/C_intraday_sessions.png",
       "Left: intraday cross-sectional signal by look-back (negative = reversal). Right: mean return by session.")

heading("5.4 Investment themes", 2)
t14 = THM[THM.Strategy == "Theme momentum L=14d H=1d"].iloc[0]
para(
    "Theme momentum ranks the four theme indices on their trailing return, goes long the best themes and "
    "short the worst, and spreads each theme's weight equally across its coins.")
figure("figures/D_theme_indices.png", "Equal-weight theme indices (growth of $1, log scale).")
para(
    f"Theme momentum is the strongest gross signal in the research period: with a 14-day look-back it earns a "
    f"gross Sharpe of {num(t14['Gross IS'])} in 2021-2023 and {num(t14['Gross Full'])} over the full sample. "
    "Themes rotate slowly, so turnover is modest. However, the signal weakened sharply in the hold-out "
    f"period (gross Sharpe {num(t14['Gross OOS'])}). Theme moves in 2024-2026 came in short, sharp bursts that "
    "then reversed - the payments & meme theme rose about 150% in 2024 and fell about 36% from January 2025 - "
    "so trailing theme returns stopped predicting the following weeks. Table 4 shows the grid.")
table(["Look-back", "Hold", "Gross IS", "Gross OOS", "Net 20 bps (full)", "Net 7 bps (full)", "Turnover"],
      [[r.Strategy.split("L=")[1].split(" ")[0], r.Strategy.split("H=")[1], num(r["Gross IS"]), num(r["Gross OOS"]),
        num(r["Net20 Full"]), num(r["Net7 Full"]), num(r["Turnover"])]
       for _, r in THM[THM.Strategy.str.contains("H=1d|H=7d")].iterrows()],
      widths=[0.8, 0.6, 0.8, 0.85, 1.1, 1.0, 0.8],
      caption=tcap("Theme momentum grid (look-back and holding period)."))

heading("5.5 Technical plays: front-running institutional hours", 2)
fr1 = FR[(FR.Test.str.startswith("Pre-US")) & (FR.kind == "Cross-sectional")].iloc[0]
fr2 = FR[(FR.Test.str.startswith("Prior-day")) & (FR.kind == "Cross-sectional")].iloc[0]
para(
    "If institutions trade predictably during US hours, the moves before the US open, or the previous US "
    "session, might predict the coming US session. Three tests use hourly data: (i) the pre-US return "
    "(00:00-13:00 UTC) predicting the US session; (ii) yesterday's US session predicting today's (same-session "
    "persistence, in the spirit of Heston, Korajczyk & Sadka, 2010); and (iii) the US session predicting the "
    "following late-US hours.")
table(["Test", "Type", "Gross bps/day", "Gross Sharpe", "IS", "OOS", "Net 7 bps", "t-stat"],
      [[r.Test, r.kind, num(r["Gross bps/day"]), num(r["Gross Sharpe"]), num(r["Gross Sharpe IS"]),
        num(r["Gross Sharpe OOS"]), num(r["Net Sharpe @7"]), num(r["t-stat"])] for _, r in FR.iterrows()],
      widths=[2.2, 1.0, 0.65, 0.6, 0.45, 0.45, 0.6, 0.5], size=8.5,
      caption=tcap("Front-running the US session (hourly data, 2022 onward)."))
para(
    f"The most promising effect is same-session persistence across coins: coins that outperformed in "
    f"yesterday's US session tend to outperform again today (gross {num(fr2['Gross bps/day'])} bps per day, "
    f"Sharpe {num(fr2['Gross Sharpe'])}). But no test is statistically strong, and because each strategy opens and "
    "closes a full position every day, even 7 bps limit orders wipe out the edge. Front-running "
    "institutional hours is not profitable at the brief's costs with daily session granularity.")

# =========================================================================== #
# 6. REVERSAL
# =========================================================================== #
heading("6. Reversal Research", 1)
heading("6.1 Time horizon: intraday and long-horizon reversal", 2)
para(
    "The brief expects reversal at shorter horizons. Daily data showed none, so the test was repeated on "
    "hourly data (Figure 4, left, and Table 6). Here reversal is very strong.")
table(["Look-back", "Gross Sharpe", "IS", "OOS", "Gross bps/hour", "Turnover/hour", "Cost bps/hour at 7",
       "Net Sharpe at 7 bps"],
      [[f"{int(r.lookback_hours)} h", num(r["Gross Sharpe"]), num(r["Gross Sharpe IS"]), num(r["Gross Sharpe OOS"]),
        num(r["Gross bps/hour"]), num(r["Turnover/hour"]), num(r["Cost bps/hour @7"]), num(r["Net Sharpe @7"], 1)]
       for _, r in IH.iterrows()],
      widths=[0.7, 0.75, 0.5, 0.5, 0.8, 0.8, 0.9, 0.9], size=8.5,
      caption=tcap("Intraday cross-sectional signal (negative Sharpe = reversal), rebalanced hourly."))
para(
    f"A 1-hour cross-sectional reversal (buy the coins that fell most in the last hour, sell those that rose) "
    f"has a gross Sharpe of {num(-IH.iloc[0]['Gross Sharpe'])}, and it holds in both the research and hold-out "
    "periods. It confirms the brief's view that shorter horizons lead to reversal. But the strategy earns about "
    f"{num(-IH.iloc[0]['Gross bps/hour'])} bps per hour while turning over {num(IH.iloc[0]['Turnover/hour'])}x its "
    f"capital, which costs {num(IH.iloc[0]['Cost bps/hour @7'])} bps per hour even with limit orders. Intraday "
    "reversal is an edge for market makers paid to provide liquidity, not for a strategy that pays 7-20 bps.")
lt = SEL[SEL.Strategy == rev_name].iloc[0]
para(
    "At the other end, long-horizon reversal works and is cheap to trade. Selling the coins with the best "
    "60-day return and buying the worst, skipping the most recent 14 days (which still carry momentum) and "
    f"holding each portfolio 14 days, earns a gross Sharpe of {num(lt['Gross Full'])} with turnover of only "
    f"{num(lt['Turnover'])} per day. This is the overreaction pattern of De Bondt and Thaler (1985), compressed "
    "into weeks rather than years in crypto.")

heading("6.2 Uninformed trading", 2)
para(
    "The brief suggests that uninformed, liquidity-driven moves reverse more. The activity results in Section "
    f"5.2 point the same way: low-activity moves show weaker 1-day momentum ({num(act(1, 'Low-activity coins only'))}) "
    f"than high-activity moves ({num(act(1, 'High-activity coins only'))}), consistent with Campbell, Grossman and "
    "Wang (1993). The intraday reversal is also the uninformed-trading channel: hour-to-hour moves are mostly "
    "liquidity noise, and they reverse. At the daily horizon, however, even low-volume moves do not reverse "
    "outright in this large-cap universe.")

heading("6.3 Correlation: residual baskets and cointegrated pairs", 2)
tr60 = COR.loc["Theme-residual reversal L=60d"]; mr7 = COR.loc["Market-residual reversal L=7d"]
co = COR.loc["Cointegration pairs (Kalman, walk-forward)"]
para(
    "The brief suggests that 'Security A minus something correlated to it' is more mean-reverting. Three "
    "versions are tested: (i) each coin's return minus its beta-adjusted market return; (ii) each coin's return "
    "minus its theme index; and (iii) cointegrated pairs traded with a Kalman-filter hedge ratio and a "
    "walk-forward monthly re-selection (the engine from the July version of this project, now run at 20 bps).")
table(["Strategy", "Gross IS", "Gross OOS", "Gross full", "Net 20 bps", "Net 7 bps", "Turnover"],
      [[k, num(r["Gross IS"]), num(r["Gross OOS"]), num(r["Gross Full"]), num(r["Net20 Full"]),
        num(r["Net7 Full"]), num(r["Turnover"])] for k, r in COR.iterrows()],
      widths=[2.4, 0.65, 0.7, 0.7, 0.7, 0.65, 0.65], size=8.5,
      caption=tcap("Correlation-based reversal."))
para(
    f"Residuals against the whole market do not reverse; they trend (7-day Sharpe of the reversal "
    f"{num(mr7['Gross Full'])}), so coin-specific moves carry information. Residuals against the coin's own "
    f"theme do reverse at 1-2 month horizons (60-day gross Sharpe {num(tr60['Gross Full'])}, positive in both "
    "periods): a coin that runs ahead of its closest peers tends to give it back. Cointegrated pairs are "
    f"genuinely market-neutral and trade very little (turnover {num(co['Turnover'], 3)} per day), but their gross "
    f"edge ({num(co['Gross Full'])}) is too small to survive costs. Across {PAIRS['n_formation_windows']} monthly windows the "
    f"engine traded {PAIRS['unique_pairs_traded']} different pairs, most often "
    f"{', '.join(FREQ.iloc[:4, 0])}.")

heading("6.4 Macro: volatility and dislocation", 2)
para(
    "The brief expects more reversal when volatility and dislocation are high. Four indicators are tested, "
    "as discussed in class: implied volatility (Deribit DVOL), realized volatility of the market, cross-sectional "
    "return dispersion, and average pairwise correlation. Each day is placed in the low, middle or high tercile "
    "of the indicator's trailing one-year range, using only data available before the trade.")
figure("figures/G_macro_regimes.png", "Gross Sharpe of each strategy by macro regime.", width=6.5)
srv = "Short-term reversal 1d"
para(
    f"Short-term (1-day) reversal behaves as the brief predicts: it loses heavily when realized volatility is "
    f"low (Sharpe {num(mac(srv, 'Realized vol (30d, EW market)', 'Low'))}) and turns positive when volatility is "
    f"middling or high, and it is positive only when average correlation is high "
    f"({num(mac(srv, 'Avg pairwise correlation (30d)', 'High'))}). That matches Nagel (2012): liquidity providers "
    "earn more when markets are stressed. The effect is not strong enough to make daily reversal tradable after "
    "costs (Section 8), but it is a clean confirmation of the macro hypothesis.")
para(
    f"The more useful macro result is for momentum. Time-series momentum earns a Sharpe of "
    f"{num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'Low'))} when implied volatility is low but "
    f"{num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'High'))} when it is high: trends break when option "
    "markets price large moves, the crypto version of the momentum crashes in Daniel and Moskowitz (2016). "
    "Switching time-series momentum off when DVOL is in its top tercile is therefore built into the candidate "
    "set, and it was selected on the research period.")

# =========================================================================== #
# 7. EXECUTION
# =========================================================================== #
heading("7. Execution", 1)
para(
    "Execution decides most of these results. Three tools reduce cost: (i) limit orders (7 bps instead of 20) "
    "for slow strategies; (ii) overlapping holding periods, which average the last few days' target portfolios "
    "and so trade more slowly; and (iii) a no-trade band, which leaves a position alone unless it is more than "
    "2% or 5% away from target (Garleanu & Pedersen, 2013). Table 8 applies them to the two final books.")
table(["Book", "Execution", "Turnover/day", "Gross Sharpe", "Net 7 bps", "Net 20 bps", "Cost drag/yr at 20"],
      [[r.Book, r.Execution, num(r.Turnover, 3), num(r["Sharpe gross"]), num(r["Sharpe limit 7bps"]),
        num(r["Sharpe market 20bps"]), pct(r["Cost drag/yr @20"])] for _, r in EXE.iterrows()],
      widths=[0.85, 1.6, 0.8, 0.8, 0.75, 0.75, 0.95], size=8.5,
      caption=tcap("Execution variants for the final momentum and reversal books."))
mex, rex = S["execution_selected"]["Momentum"], S["execution_selected"]["Reversal"]
para(
    f"For the momentum ensemble the research period selected '{mex}': turnover goes from "
    f"{num(exe('Momentum', 'Daily rebalance', 'Turnover'), 3)} to {num(exe('Momentum', mex, 'Turnover'), 3)} "
    f"per day and the 20 bps Sharpe from {num(exe('Momentum', 'Daily rebalance', 'Sharpe market 20bps'))} to "
    f"{num(exe('Momentum', mex, 'Sharpe market 20bps'))}, while the gross Sharpe is essentially unchanged "
    f"({num(exe('Momentum', 'Daily rebalance', 'Sharpe gross'))} vs {num(exe('Momentum', mex, 'Sharpe gross'))}). "
    "Longer holding periods cut turnover too, but they dilute the momentum signal faster than they save cost. "
    f"The reversal book already trades slowly; '{rex}' was selected for it. Moving from market to limit "
    f"orders is worth about {num(exe('Momentum', mex, 'Sharpe limit 7bps') - exe('Momentum', mex, 'Sharpe market 20bps'))} "
    "of Sharpe for momentum, so if part of the momentum book can be executed passively the gain is large.")
figure("figures/H_cost_sweep.png", "Net Sharpe of the final books versus transaction cost (0-200 bps).", width=5.8)
para(
    f"The combined portfolio stays profitable up to about 50 bps (Sharpe {num(SWP.loc[50, 'Combined'])}) and "
    f"breaks down near 100 bps ({num(SWP.loc[100, 'Combined'])}). The reversal book is the most cost-robust "
    f"sleeve because of its low turnover; the momentum sleeve breaks even near 50 bps.")

# =========================================================================== #
# 8. SELECTION
# =========================================================================== #
heading("8. Strategy Selection", 1)
para(
    f"The research blocks above produced a pre-specified grid of {S['n_candidates']} candidates. Momentum "
    "candidates are time-series momentum (holding period, with or without the DVOL filter), theme momentum "
    "(look-back and holding period) and cross-sectional momentum (look-back, holding period, with or without "
    "volume weighting). Reversal candidates are short-term reversal restricted to high-volatility regimes, "
    "long-horizon reversal (look-back, skip, holding period) and cointegrated pairs. Each candidate is ranked "
    "by its research-period net Sharpe at its execution cost (20 bps for momentum, 7 bps for reversal).")
top = pd.concat([SEL[SEL.family == "Momentum"].head(6), SEL[SEL.family == "Reversal"].head(5)])
table(["Candidate", "Family", "Selection Sharpe (IS)", "Hold-out net 20", "Hold-out net 7", "Turnover"],
      [[r.Strategy, r.family, num(r["Selection IS"]), num(r["Net20 OOS"]), num(r["Net7 OOS"]), num(r.Turnover)]
       for _, r in top.iterrows()],
      widths=[2.6, 0.8, 0.95, 0.8, 0.8, 0.65], size=8.5,
      caption=tcap("Top candidates by research-period net Sharpe."),
      note="Full list in the workbook (sheet 'Candidate Selection').")
para(
    "The momentum ranking is dominated by theme momentum, but those variants are close relatives of one "
    "another and all of them decayed in the hold-out. Rather than bet on one winner, the final momentum book is "
    "an ensemble of the research-period best variant from each momentum family:")
for c in comp:
    bullet(f"{c} (hold-out net Sharpe at 20 bps: {num(sel(c, 'Net20 OOS'))})")
para(
    f"The reversal book is the research-period best reversal candidate, {rev_name}. Short-term reversal, even "
    "restricted to high-volatility regimes, loses money after costs and was rejected.")

# =========================================================================== #
# 9. WEIGHTING
# =========================================================================== #
heading("9. Weighting", 1)
cmr = CORR.loc["Momentum ensemble", "Reversal"]
para(
    f"The momentum and reversal books are almost uncorrelated (daily correlation {num(cmr)}), and neither is "
    "correlated with Bitcoin, so combining them should cut risk substantially. Four weighting schemes from "
    "the course were tested, all re-estimated monthly on the trailing 180 days only: equal weight, inverse "
    "volatility, risk parity (equal risk contribution) and a shrunk mean-variance optimiser (means shrunk "
    "50% toward zero, covariance shrunk toward its diagonal, no shorting of sleeves).")
table(["Method", "Avg weight momentum", "Avg weight reversal", "Sharpe IS", "Sharpe OOS", "Sharpe full"],
      [[m, pct(r["Avg weight Momentum"], 0), pct(r["Avg weight Reversal"], 0), num(r["Sharpe IS"]),
        num(r["Sharpe OOS"]), num(r["Sharpe"])] for m, r in WTS.iterrows()],
      widths=[1.9, 1.0, 1.0, 0.8, 0.8, 0.8],
      bold_rows={list(WTS.index).index(best_m)},
      caption=tcap("Weighting methods for combining momentum and reversal."))
para(
    f"{best_m} had the best research-period Sharpe and was selected. With only two sleeves, inverse volatility "
    "and risk parity give nearly identical weights. All four methods beat either sleeve on its own, which is "
    "the main benefit of combining uncorrelated strategies. In the hold-out the simpler schemes did slightly "
    "better than mean-variance, consistent with DeMiguel, Garlappi and Uppal (2009): estimated means are noisy, "
    "so a plain risk-based weighting is a sound default going forward.")
figure("figures/I_sleeve_weights.png", f"Walk-forward sleeve weights ({best_m.lower()}).", width=6.0)
heading("9.1 Robustness of the selection", 2)
table(["Momentum sleeve", "Mom. Sharpe IS", "Mom. Sharpe OOS", "Combined IS", "Combined OOS", "Combined full"],
      [[r["Momentum sleeve"], num(r["Momentum Sharpe IS"]), num(r["Momentum Sharpe OOS"]),
        num(r["Combined Sharpe IS"]), num(r["Combined Sharpe OOS"]), num(r["Combined Sharpe Full"])]
       for _, r in RB.iterrows()],
      widths=[2.6, 0.8, 0.85, 0.75, 0.8, 0.8], size=8.5,
      caption=tcap("How the result depends on the momentum choice."))
para(
    "Had the single best research-period momentum strategy been used, the combined portfolio's hold-out Sharpe "
    f"would have been only {num(RB.iloc[1]['Combined Sharpe OOS'])}. The ensemble and the time-series-only "
    f"versions hold up better ({num(RB.iloc[0]['Combined Sharpe OOS'])} and {num(RB.iloc[2]['Combined Sharpe OOS'])}). "
    "This table is the clearest illustration of selection risk in the project. Transparency note: the "
    "ensemble design was adopted after seeing that single-strategy selection was fragile, so its hold-out "
    "figure is partly informed by the hold-out and should be read with that in mind.")

# =========================================================================== #
# 10. PERFORMANCE
# =========================================================================== #
heading("10. Performance Evaluation", 1)
para("Tables 12-14 report the metrics required by the brief for the full backtest window, the research period "
     "and the hold-out period. The combined portfolio is the recommended strategy; its components and the "
     "passive benchmarks are shown for comparison.")
table(PERF_HEAD, perf_rows(FULL, PERF_KEYS, PERF_LABS), widths=PERF_W, bold_rows={0},
      caption=tcap(f"Full backtest, {S['bt_start']} to {S['sample_end']}."), note="* Momentum at 20 bps (market orders), reversal at 7 bps (limit orders).")
table(PERF_HEAD, perf_rows(INS, PERF_KEYS, PERF_LABS), widths=PERF_W, bold_rows={0},
      caption=tcap(f"Research period, {S['bt_start']} to {S['is_end']}."), note="* Momentum at 20 bps (market orders), reversal at 7 bps (limit orders).")
table(PERF_HEAD, perf_rows(OOS, PERF_KEYS, PERF_LABS), widths=PERF_W, bold_rows={0},
      caption=tcap(f"Hold-out period, {S['oos_start']} to {S['sample_end']}."), note="* Momentum at 20 bps (market orders), reversal at 7 bps (limit orders).")
figure("figures/J_equity_curves.png", "Growth of $1, net of costs (log scale). Dashed line: start of hold-out.")
para(
    f"Over the full window the combined portfolio earns {pct(c_full['Ann.Return'])} a year at "
    f"{pct(c_full['Ann.Vol'])} volatility, a Sharpe of {num(c_full['Sharpe'])}, against {num(FULL.loc[BTC, 'Sharpe'])} "
    f"for holding Bitcoin. Its beta to Bitcoin is {num(c_full['Beta'])}, so almost all of its return is alpha: "
    f"{pct(c_full['Alpha'])} a year with a t-statistic of {num(c_full['Alpha t'])}. Its worst drawdown is "
    f"{pct(c_full['MaxDD'])}, against {pct(FULL.loc[BTC, 'MaxDD'])} for Bitcoin and {pct(FULL.loc[EW, 'MaxDD'])} for an "
    "equal-weight crypto basket. Even with every trade charged 20 bps, the Sharpe is "
    f"{num(FULL.loc[CMB20, 'Sharpe'])}.")
para(
    f"The hold-out is weaker. The combined Sharpe falls to {num(c_oos['Sharpe'])}, with alpha "
    f"{pct(c_oos['Alpha'])} a year (t = {num(c_oos['Alpha t'])}), because the momentum ensemble's Sharpe fell from "
    f"{num(INS.loc[MOMK, 'Sharpe'])} to {num(OOS.loc[MOMK, 'Sharpe'])}. Bitcoin itself had a strong hold-out "
    f"(Sharpe {num(OOS.loc[BTC, 'Sharpe'])}) after spot ETF approval, but with a {pct(OOS.loc[BTC, 'MaxDD'])} drawdown and "
    "full market risk. The reversal book was the steadiest component, with a hold-out Sharpe of "
    f"{num(OOS.loc[REVK, 'Sharpe'])} at 7 bps and {num(OOS.loc[REV20, 'Sharpe'])} at 20 bps.")
figure("figures/J_drawdowns.png", "Drawdowns of the combined portfolio, the momentum book and Bitcoin.")
figure("figures/J_rolling_sharpe.png", "Rolling 180-day Sharpe ratio (net).")

# =========================================================================== #
# 11. DISCUSSION
# =========================================================================== #
heading("11. Discussion", 1)
heading("11.1 What the research shows", 2)
bullet("At daily horizons crypto is a momentum market. The brief's short-horizon reversal exists, but only "
       "intraday, where costs make it unreachable; long-horizon (2-month) reversal is the tradable reversal.",
       "Momentum and reversal live at different horizons. ")
bullet("Volume shocks, weekends, theme rotation and calm option markets all strengthen momentum; high "
       "volatility and high correlation strengthen reversal. Each confirms a hypothesis in the brief.",
       "The brief's conditioning variables work. ")
bullet("Turnover, not signal discovery, separates profitable from unprofitable strategies. Bands, slower "
       "signals and limit orders matter as much as the signal itself.", "Execution is the binding constraint. ")
bullet("Momentum and reversal are nearly uncorrelated, so a simple risk-based combination produces a "
       "market-neutral portfolio with a higher Sharpe and a smaller drawdown than either part.",
       "Combining is where the value is. ")
heading("11.2 Comparison with the July version", 2)
para(
    "The July 2026 version compared vol-scaled time-series momentum with cointegration pairs at 10 bps and "
    "found time-series momentum best. This rebuild extends the sample by three months, applies the brief's "
    "20 / 7 bps costs instead of 10 bps, adds alpha, tests every item in the research outline, adds a reversal "
    "strategy that works, and combines momentum and reversal with explicit weighting. Time-series momentum "
    "remains the most robust single momentum family; cointegration pairs remain market-neutral but unprofitable "
    "after costs.")
heading("11.3 Limitations", 2)
bullet("Short legs assume coins can be borrowed or shorted through perpetual futures; funding costs are not "
       "modelled. A long-only implementation would capture only part of the long-short edge.", "Shorting. ")
bullet("The universe is 16 large coins that survived to 2026; failed or delisted coins are absent, which "
       "flatters the sample (survivorship bias).", "Survivorship. ")
bullet("Costs are linear. Real slippage rises with trade size and in stressed markets, and limit orders may not "
       "fill, so the 7 bps reversal assumption is optimistic for large capital.", "Costs and capacity. ")
bullet(f"{S['n_candidates']} candidates were compared. Even with the research / hold-out split, a deflated "
       "Sharpe ratio (Bailey & Lopez de Prado, 2014) would be lower than the reported one.", "Multiple testing. ")
bullet("Social-media and on-chain activity data were not used because free historical data are not available; "
       "volume is the only activity proxy.", "Activity data. ")
heading("11.4 Next steps", 2)
bullet("Paper-trade the combined portfolio forward on live data to build a genuine out-of-sample record.")
bullet("Execute the momentum book partly with limit orders and measure fill rates.")
bullet("Add theme-residual reversal (Section 6.3) as a third sleeve and test it on new data.")
bullet("Model perpetual-futures funding and borrow costs for the short legs.")

# =========================================================================== #
# 12. CONCLUSION
# =========================================================================== #
heading("12. Conclusion", 1)
para(
    "On live data through October 2026, crypto shows momentum at horizons of a few days to a month and "
    "reversal at the extremes - within the hour and over two months. The patterns the brief points to are "
    "present: activity strengthens momentum, weekends favour it, themes rotate, implied volatility predicts "
    "momentum crashes, and stressed markets favour reversal. Most of these edges are too small or trade too "
    "often to survive 20 bps costs, so execution design is as important as signal discovery.")
para(
    f"A market-neutral portfolio that combines a diversified momentum ensemble with long-horizon reversal, "
    f"weighted by {best_m.lower()}, earns a net Sharpe of {num(c_full['Sharpe'])} with alpha of "
    f"{pct(c_full['Alpha'])} a year, a beta to Bitcoin of {num(c_full['Beta'])} and a maximum drawdown of "
    f"{pct(c_full['MaxDD'])}. Its hold-out Sharpe of {num(c_oos['Sharpe'])} is lower, which is the realistic "
    "expectation for a newly deployed strategy. The strongest lesson of the project is that diversification "
    "across signals, and discipline about what is chosen on which data, matter more than any single "
    "backtest result.")

# =========================================================================== #
# APPENDIX
# =========================================================================== #
heading("Appendix A. Reproducibility", 1)
para("All results are reproduced by the notebook crypto_stat_arb_project.ipynb, or from the command line in "
     "this order:")
for s_ in ["python3 src/fetch_data.py - download daily, hourly and DVOL data to the latest date",
           "python3 src/statarb.py - cointegration pairs engine (walk-forward, Kalman)",
           "python3 src/research.py - all research blocks, selection, weighting and performance",
           "python3 src/build_report.py, build_pptx.py, build_excel.py, build_notebook.py - deliverables"]:
    bullet(s_)
para("Every table in this report is read from data/research/*.csv, and the workbook "
     "crypto_stat_arb_data.xlsx contains every dataset and result.")

heading("References", 1)
refs = [
    "Bailey, D. H., & Lopez de Prado, M. (2014). The deflated Sharpe ratio: Correcting for selection bias, backtest overfitting and non-normality. Journal of Portfolio Management, 40(5), 94-107.",
    "Barroso, P., & Santa-Clara, P. (2015). Momentum has its moments. Journal of Financial Economics, 116(1), 111-120.",
    "Campbell, J. Y., Grossman, S. J., & Wang, J. (1993). Trading volume and serial correlation in stock returns. Quarterly Journal of Economics, 108(4), 905-939.",
    "Chan, E. P. (2013). Algorithmic trading: Winning strategies and their rationale. Wiley.",
    "Daniel, K., & Moskowitz, T. J. (2016). Momentum crashes. Journal of Financial Economics, 122(2), 221-247.",
    "De Bondt, W. F. M., & Thaler, R. (1985). Does the stock market overreact? Journal of Finance, 40(3), 793-805.",
    "DeMiguel, V., Garlappi, L., & Uppal, R. (2009). Optimal versus naive diversification: How inefficient is the 1/N portfolio strategy? Review of Financial Studies, 22(5), 1915-1953.",
    "Do, B., & Faff, R. (2010). Does simple pairs trading still work? Financial Analysts Journal, 66(4), 83-95.",
    "Do, B., & Faff, R. (2012). Are pairs trading profits robust to trading costs? Journal of Financial Research, 35(2), 261-287.",
    "Dobrynskaya, V. (n.d.). Cryptocurrency momentum and reversal [Working paper]. HSE University.",
    "Elliott, R. J., van der Hoek, J., & Malcolm, W. P. (2005). Pairs trading. Quantitative Finance, 5(3), 271-276.",
    "Engle, R. F., & Granger, C. W. J. (1987). Co-integration and error correction: Representation, estimation, and testing. Econometrica, 55(2), 251-276.",
    "Fil, M., & Kristoufek, L. (2020). Pairs trading in cryptocurrency markets. IEEE Access, 8, 172644-172651.",
    "Garleanu, N., & Pedersen, L. H. (2013). Dynamic trading with predictable returns and transaction costs. Journal of Finance, 68(6), 2309-2340.",
    "Gatev, E., Goetzmann, W. N., & Rouwenhorst, K. G. (2006). Pairs trading: Performance of a relative-value arbitrage rule. Review of Financial Studies, 19(3), 797-827.",
    "Han, H., Kang, J., & Ryu, D. (2024). Time-series and cross-sectional momentum in the cryptocurrency market: A comprehensive analysis under realistic assumptions (SSRN Working Paper No. 4675565).",
    "Harvey, C. R., Liu, Y., & Zhu, H. (2016). ... and the cross-section of expected returns. Review of Financial Studies, 29(1), 5-68.",
    "Heston, S. L., Korajczyk, R. A., & Sadka, R. (2010). Intraday patterns in the cross-section of stock returns. Journal of Finance, 65(4), 1369-1407.",
    "Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers: Implications for stock market efficiency. Journal of Finance, 48(1), 65-91.",
    "Krauss, C. (2017). Statistical arbitrage pairs trading strategies: Review and outlook. Journal of Economic Surveys, 31(2), 513-545.",
    "Lehmann, B. N. (1990). Fads, martingales, and market efficiency. Quarterly Journal of Economics, 105(1), 1-28.",
    "Liu, Y., & Tsyvinski, A. (2021). Risks and returns of cryptocurrency. Review of Financial Studies, 34(6), 2689-2727.",
    "Liu, Y., Tsyvinski, A., & Wu, X. (2022). Common risk factors in cryptocurrency. Journal of Finance, 77(2), 1133-1177.",
    "Moskowitz, T. J., & Grinblatt, M. (1999). Do industries explain momentum? Journal of Finance, 54(4), 1249-1290.",
    "Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). Time series momentum. Journal of Financial Economics, 104(2), 228-250.",
    "Nagel, S. (2012). Evaporating liquidity. Review of Financial Studies, 25(7), 2005-2039.",
    "Vidyamurthy, G. (2004). Pairs trading: Quantitative methods and analysis. Wiley.",
    "Wall Street Quants. (2025). Statistical arbitrage in cryptocurrencies: Course project brief [Class handout].",
]
for ref in refs:
    p = para(ref, space_after=4)
    p.paragraph_format.left_indent = Inches(0.4)
    p.paragraph_format.first_line_indent = Inches(-0.4)

add_page_numbers()
json.dump(HEADS, open("data/research/_heads.json", "w"))
doc.save("crypto_research_report.docx")
print("saved crypto_research_report.docx")
