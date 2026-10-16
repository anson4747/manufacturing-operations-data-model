"""
Builds the README figures from the gold layer, in light and dark variants.
Run after run_pipeline.py:  python docs/make_figures.py
"""
import os
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "img")
os.makedirs(OUT, exist_ok=True)
con = duckdb.connect(os.path.join(HERE, "..", "warehouse.duckdb"), read_only=True)
df = lambda sql: con.execute(sql).fetchdf()

THEMES = {
    "light": dict(fg="#0b0b0b", fg2="#52514e", muted="#8a8984", grid="#e4e3de", tile="#f6f5f2",
                  tile_edge="#e4e3de", s1="#2a78d6", s2="#eb6834", s3="#1baf7a", s4="#6250d6",
                  neutral="#b9b8b2", band="#eb6834"),
    "dark": dict(fg="#f0efec", fg2="#c3c2b7", muted="#8f8e88", grid="#33332f", tile="#1f1f1d",
                 tile_edge="#33332f", s1="#3987e5", s2="#d95926", s3="#199e70", s4="#9085e9",
                 neutral="#5c5b56", band="#d95926"),
}
plt.rcParams.update({"font.family": "Inter", "font.size": 11, "axes.titleweight": "semibold",
                     "svg.fonttype": "none"})

FY26 = ("2025-07-01", "2026-06-30")
SHORTAGE = (pd.Timestamp("2026-02-01"), pd.Timestamp("2026-03-31"))


def style_axis(ax, t):
    ax.set_facecolor("none")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(colors=t["fg2"], length=0, labelsize=10)
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, name, theme):
    fig.savefig(os.path.join(OUT, f"{name}-{theme}.png"), dpi=200, transparent=True, bbox_inches="tight",
                pad_inches=0.15)
    plt.close(fig)


# ------------------------------------------------------------------ data
panel = """(SELECT o.*, (SELECT max(p.profile) FROM gold.fact_sales_line l JOIN gold.dim_product p USING(sku)
            WHERE l.order_id=o.order_id AND p.category='Panel') AS prof FROM gold.fact_sales_order o)"""
otd_all = df(f"""SELECT d.month_start m, avg(on_time_promise) p, avg(request_met) r
    FROM gold.fact_sales_order f JOIN gold.dim_date d ON d.date=f.order_date
    WHERE is_valid_for_delivery_kpi AND d.fy='FY26' GROUP BY 1 ORDER BY 1""")
otd_78 = df(f"""SELECT d.month_start m, avg(on_time_promise) p, avg(request_met) r
    FROM {panel} f JOIN gold.dim_date d ON d.date=f.order_date
    WHERE is_valid_for_delivery_kpi AND prof='78mm' AND d.fy='FY26' GROUP BY 1 ORDER BY 1""")
coil = df(f"""SELECT d.month_start m, avg(coalesce(days_late,0)) late
    FROM gold.fact_purchase_order f JOIN gold.dim_date d ON d.date=f.po_date
    WHERE material_code='RM-COIL' AND is_received AND d.date BETWEEN '{FY26[0]}' AND '{FY26[1]}' GROUP BY 1 ORDER BY 1""")
prod = df(f"""SELECT d.month_start m, sum(m2_produced) m2 FROM gold.fact_production f
    JOIN gold.dim_date d ON d.date=f.production_date
    WHERE sku='PNL-78' AND d.date BETWEEN '{FY26[0]}' AND '{FY26[1]}' GROUP BY 1 ORDER BY 1""")
stock = df(f"""SELECT week_ending w, qty_on_hand q FROM gold.fact_inventory_weekly
    WHERE site_code='VIC-BAY' AND sku='PNL-78' AND week_ending BETWEEN '{FY26[0]}' AND '{FY26[1]}' ORDER BY 1""")
match = df("""SELECT project_match_method k, count(*) n FROM gold.fact_sales_order GROUP BY 1""").set_index("k").n
for frame in (otd_all, otd_78, coil, prod):
    frame["m"] = pd.to_datetime(frame["m"]) + pd.Timedelta(days=14)   # plot at mid month
stock["w"] = pd.to_datetime(stock["w"])

kpi = {
    "recovered": con.execute("""SELECT sum(l.net_revenue) FROM gold.fact_sales_line l JOIN gold.fact_sales_order o
        USING(order_id) WHERE o.project_match_method IN ('Normalised','Alias rule')""").fetchone()[0],
    "recovered_orders": int(match.get("Normalised", 0) + match.get("Alias rule", 0)),
    "gap": 100 * (otd_all.p.mean() - otd_all.r.mean()),
    "checks": con.execute("SELECT count(*) FROM gold.dq_results").fetchone()[0],
    "price_lines": con.execute("SELECT rows_failed FROM gold.dq_results WHERE check_id='DQ07'").fetchone()[0],
}
fy26 = con.execute("""SELECT avg(on_time_promise), avg(request_met) FROM gold.fact_sales_order f
    JOIN gold.dim_date d ON d.date=f.order_date WHERE is_valid_for_delivery_kpi AND d.fy='FY26'""").fetchone()
kpi["gap"] = 100 * (fy26[0] - fy26[1])


def month_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_xlim(pd.Timestamp("2025-07-01"), pd.Timestamp("2026-07-01"))


for name, t in THEMES.items():
    # ============================================================== hero
    fig = plt.figure(figsize=(12, 3.6))
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 12); ax.set_ylim(0, 3.6)
    tiles = [
        (f"${kpi['recovered']/1e6:.1f}M", f"revenue on {kpi['recovered_orders']} orders that a\nname only join would drop"),
        (f"{kpi['gap']:.0f} pts", "gap between two definitions\nof on time delivery"),
        (f"{kpi['checks']}", "data quality checks\nlogged on every load"),
        (f"{kpi['price_lines']}", "mispriced order lines\nflagged, not changed"),
    ]
    w, gap, x0 = 2.82, 0.18, 0.06
    for i, (big, small) in enumerate(tiles):
        x = x0 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 0.35), w, 2.9, boxstyle="round,pad=0,rounding_size=0.12",
                                    facecolor=t["tile"], edgecolor=t["tile_edge"], linewidth=1))
        ax.add_patch(FancyBboxPatch((x + 0.28, 2.72), 0.5, 0.07, boxstyle="round,pad=0,rounding_size=0.03",
                                    facecolor=[t["s1"], t["s2"], t["s3"], t["s4"]][i], edgecolor="none"))
        ax.text(x + 0.28, 2.05, big, fontsize=34, fontweight="bold", color=t["fg"], va="center")
        ax.text(x + 0.28, 0.98, small, fontsize=12.5, color=t["fg2"], va="center", linespacing=1.4)
    save(fig, "hero", name)

    # ============================================================== on time: two definitions
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    fig.patch.set_alpha(0)
    for ax, d, title in ((axes[0], otd_all, "All orders"), (axes[1], otd_78, "78mm panel orders")):
        style_axis(ax, t); month_axis(ax)
        ax.axvspan(*SHORTAGE, color=t["band"], alpha=0.10, linewidth=0)
        ax.plot(d.m, d.p * 100, color=t["s1"], linewidth=2.2, solid_capstyle="round")
        ax.plot(d.m, d.r * 100, color=t["s2"], linewidth=2.2, solid_capstyle="round")
        ax.scatter(d.m, d.p * 100, s=22, color=t["s1"], zorder=3, edgecolors="none")
        ax.scatter(d.m, d.r * 100, s=22, color=t["s2"], zorder=3, edgecolors="none")
        ax.set_ylim(-4, 104); ax.set_yticks([0, 25, 50, 75, 100])
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
        ax.set_title(title, loc="left", color=t["fg"], fontsize=12.5, pad=10)
        last = d.iloc[-1]
        ax.annotate(f"{last.p*100:.0f}%", (last.m, last.p * 100), xytext=(8, 0), textcoords="offset points",
                    va="center", color=t["fg"], fontsize=10, fontweight="semibold")
        ax.annotate(f"{last.r*100:.0f}%", (last.m, last.r * 100), xytext=(8, 0), textcoords="offset points",
                    va="center", color=t["fg"], fontsize=10, fontweight="semibold")
    axes[1].text(pd.Timestamp("2026-03-01"), 62, "steel coil\nshortage", ha="center", va="center",
                 color=t["fg2"], fontsize=9.5, linespacing=1.2)
    handles = [plt.Line2D([], [], color=t["s1"], linewidth=2.2, marker="o", markersize=5),
               plt.Line2D([], [], color=t["s2"], linewidth=2.2, marker="o", markersize=5)]
    fig.legend(handles, ["On time to our promise", "Customer's requested date met"], loc="upper left",
               bbox_to_anchor=(0.06, 1.06), ncol=2, frameon=False, labelcolor=t["fg2"], fontsize=10.5)
    fig.text(0.06, -0.02, "FY26 by order month. Same orders, two definitions.", color=t["muted"], fontsize=9.5)
    fig.subplots_adjust(wspace=0.12)
    save(fig, "on-time", name)

    # ============================================================== one disruption, four systems
    fig, axes = plt.subplots(4, 1, figsize=(12, 9.2), sharex=True)
    fig.patch.set_alpha(0)
    panels = [
        ("1  Purchasing: imported steel coil arrives late", "avg days late, by PO month"),
        ("2  Production: 78mm output drops", "m² produced per month"),
        ("3  Inventory: 78mm stock at the plant drains", "m² on hand, weekly"),
        ("4  Customers: 78mm requested dates stop being met", "% of orders, by order month"),
    ]
    for i, (ax, (title, unit)) in enumerate(zip(axes, panels)):
        style_axis(ax, t); month_axis(ax)
        if i > 0:
            ax.axvspan(*SHORTAGE, color=t["band"], alpha=0.10, linewidth=0)
        ax.set_title(title, loc="left", color=t["fg"], fontsize=12, pad=6)
        ax.text(1.0, 1.04, unit, transform=ax.transAxes, ha="right", va="bottom", color=t["muted"], fontsize=9.5)
    axes[0].bar(coil.m, coil.late, width=18, color=t["s1"], edgecolor="none")
    axes[0].set_ylim(0, 42)
    pk = coil.loc[coil.late.idxmax()]
    axes[0].annotate(f"{pk.late:.0f} days", (pk.m, pk.late), xytext=(0, 4), textcoords="offset points",
                     ha="center", va="bottom", color=t["fg"], fontsize=10, fontweight="semibold")
    axes[1].plot(prod.m, prod.m2, color=t["s1"], linewidth=2.2); axes[1].scatter(prod.m, prod.m2, s=22, color=t["s1"], zorder=3)
    axes[1].set_yticks([0, 3000, 6000, 9000]); axes[1].set_ylim(0, 9800)
    axes[1].yaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f}k")
    axes[2].plot(stock.w, stock.q, color=t["s1"], linewidth=2.0)
    axes[2].set_ylim(0, stock.q.max() * 1.15)
    axes[2].set_yticks([0, 2000, 4000]); axes[2].yaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f}k")
    axes[3].plot(otd_78.m, otd_78.r * 100, color=t["s2"], linewidth=2.2)
    axes[3].scatter(otd_78.m, otd_78.r * 100, s=22, color=t["s2"], zorder=3)
    axes[3].set_ylim(-4, 50); axes[3].yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    lo = prod.loc[prod.m2.idxmin()]
    axes[1].annotate(f"{lo.m2/1000:.1f}k", (lo.m, lo.m2), xytext=(0, -16), textcoords="offset points",
                     ha="center", color=t["fg"], fontsize=10, fontweight="semibold")
    axes[3].annotate("0% in Feb and Mar", (pd.Timestamp("2026-03-01"), 0), xytext=(0, 40), textcoords="offset points",
                     ha="center", color=t["fg"], fontsize=10, fontweight="semibold")
    fig.text(0.125, 0.035, "FY26. Shaded: February to March 2026. Coil is charted by order month; imported coil takes two to three months to land.",
             color=t["muted"], fontsize=9.5)
    fig.subplots_adjust(hspace=0.55)
    save(fig, "disruption", name)

    # ============================================================== order to project matching
    order = [("Exact", t["s1"]), ("Normalised", t["s3"]), ("Alias rule", t["s4"]), ("Blank", t["neutral"])]
    total = match.sum()
    fig, ax = plt.subplots(figsize=(12, 1.9))
    fig.patch.set_alpha(0); ax.axis("off"); ax.set_xlim(0, total); ax.set_ylim(-1.2, 1)
    left = 0
    spans = {}
    for k, c in order:
        n = match.get(k, 0)
        ax.barh(0, n - total * 0.002, left=left, height=0.62, color=c, edgecolor="none")
        spans[k] = (left, left + n, n)
        left += n
    x = 0
    for k, c in order:
        n = spans[k][2]
        ax.add_patch(FancyBboxPatch((x, -1.22), total * 0.008, 0.62, boxstyle="round,pad=0,rounding_size=0.0",
                                    facecolor=c, edgecolor="none"))
        ax.text(x + total * 0.016, -0.74, k, va="center", color=t["fg"], fontsize=11.5, fontweight="semibold")
        ax.text(x + total * 0.016, -1.08, f"{n:,} orders  ·  {n/total:.1%}", va="center", color=t["fg2"], fontsize=10.5)
        x += total * 0.25
    ax.set_ylim(-1.35, 0.45)
    save(fig, "matching", name)

print("figures written to", OUT)
