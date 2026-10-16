"""
Manufacturing Operations Data Model: synthetic source system generator.

Every number in here is invented. The shape of the business is modelled on
publicly available information (product profiles, sites, price notices,
lead times). Data quality problems are planted deliberately so the warehouse
layer has something real to catch.
"""
import os
import random
import numpy as np
import pandas as pd

SEED = 2026
rng = np.random.default_rng(SEED)
random.seed(SEED)

OUT = os.path.join(os.path.dirname(__file__), "raw")
os.makedirs(OUT, exist_ok=True)

START = pd.Timestamp("2024-07-01")
END = pd.Timestamp("2026-09-30")

# ---------------------------------------------------------------- calendar
def first_tuesday_nov(y):
    d = pd.Timestamp(f"{y}-11-01")
    while d.weekday() != 1:
        d += pd.Timedelta(days=1)
    return d

closed = set()
closed_reason = {}
def _close(d, why):
    d = pd.Timestamp(d)
    closed.add(d)
    closed_reason.setdefault(d, why)
for y in (2024, 2025, 2026):
    _close(first_tuesday_nov(y), "Melbourne Cup")
    _close(first_tuesday_nov(y) - pd.Timedelta(days=1), "Company Day")
    for d in pd.date_range(f"{y}-12-22", f"{y + 1}-01-07"):
        _close(d, "Christmas shutdown")
for d, why in [("2025-01-27", "Australia Day"), ("2025-03-10", "Labour Day"), ("2025-04-18", "Good Friday"),
               ("2025-04-21", "Easter Monday"), ("2025-04-25", "Anzac Day"), ("2025-06-09", "King's Birthday"),
               ("2025-09-26", "AFL Grand Final Friday"), ("2026-01-26", "Australia Day"), ("2026-03-09", "Labour Day"),
               ("2026-04-03", "Good Friday"), ("2026-04-06", "Easter Monday"), ("2026-04-27", "Anzac Day (observed)"),
               ("2026-06-08", "King's Birthday"), ("2026-09-25", "AFL Grand Final Friday")]:
    _close(d, why)

all_days = pd.date_range(START, END)
work_days = pd.DatetimeIndex([d for d in all_days if d.weekday() < 5 and d not in closed])
work_set = set(work_days)

def add_business_days(d, n):
    step = 1 if n >= 0 else -1
    d = pd.Timestamp(d)
    left = abs(int(n))
    while left > 0:
        d += pd.Timedelta(days=step)
        if d.weekday() < 5 and d not in closed:
            left -= 1
    return d

# ---------------------------------------------------------------- products
products = pd.DataFrame([
    ["PNL-51", "Fire Rated Panel 51mm",            "Panel",     "51mm", "m2",   58.00, 0.61],
    ["PNL-64", "Fire Rated Panel 64mm",            "Panel",     "64mm", "m2",   66.00, 0.60],
    ["PNL-78", "Fire Rated Panel 78mm",            "Panel",     "78mm", "m2",   79.00, 0.58],
    ["TRK-C51", "C Track 51mm",                  "Track",     "51mm", "lm",    9.50, 0.55],
    ["TRK-C64", "C Track 64mm",                  "Track",     "64mm", "lm",   10.50, 0.55],
    ["TRK-C78", "C Track 78mm",                  "Track",     "78mm", "lm",   12.00, 0.55],
    ["ANG-STL", "Steel Angle 50x50",             "Accessory", None,   "lm",    7.00, 0.50],
    ["SEAL-FR", "Fire Rated Sealant 600ml",      "Accessory", None,   "each", 24.00, 0.45],
    ["FIX-PK",  "Fixing Pack (100)",             "Accessory", None,   "pack", 32.00, 0.40],
], columns=["sku", "description", "category", "profile", "uom", "base_price", "cost_ratio"])

# ---------------------------------------------------------------- quarterly price list
quarters = pd.date_range("2024-07-01", "2026-07-01", freq="QS-JUL")
quarters = pd.DatetimeIndex(sorted(set(pd.date_range("2024-07-01", "2026-09-30", freq="QS"))))

def fy_quarter_label(d):
    fy = d.year + 1 if d.month >= 7 else d.year
    q = {7: 1, 8: 1, 9: 1, 10: 2, 11: 2, 12: 2, 1: 3, 2: 3, 3: 3, 4: 4, 5: 4, 6: 4}[d.month]
    return f"FY{str(fy)[2:]} Q{q}"

price_rows = []
current = dict(zip(products.sku, products.base_price))
for i, qs in enumerate(quarters):
    qe = (qs + pd.offsets.QuarterEnd(0))
    if i > 0:
        for _, p in products.iterrows():
            if qs == pd.Timestamp("2025-07-01") and p.category in ("Panel", "Track"):
                current[p.sku] *= 1.025          # public notice: 2.5% panels and tracks
            elif qs == pd.Timestamp("2026-07-01") and p.category in ("Panel", "Track"):
                current[p.sku] *= 1.030          # assumed
            elif p.category == "Accessory":
                current[p.sku] *= 1 + rng.choice([0.0, 0.0, 0.01, 0.015])
    for _, p in products.iterrows():
        price_rows.append([p.sku, qs.date(), qe.date(), fy_quarter_label(qs), round(current[p.sku], 2)])
price_list = pd.DataFrame(price_rows, columns=["sku", "effective_from", "effective_to", "price_period", "list_price"])

def list_price(sku, d):
    d = pd.Timestamp(d).date()
    r = price_list[(price_list.sku == sku) & (price_list.effective_from <= d) & (price_list.effective_to >= d)]
    return float(r.list_price.iloc[0])

price_lookup = {}
for _, r in price_list.iterrows():
    for d in pd.date_range(r.effective_from, r.effective_to):
        price_lookup[(r.sku, d)] = r.list_price

# ---------------------------------------------------------------- sites and fuel levy (SharePoint lists)
sites = pd.DataFrame([
    ["VIC-BAY", "Bayswater Manufacturing and Warehouse", "VIC", "Manufacturing", "1998-01-01", None],
    ["NSW-WH",  "NSW Warehouse",                          "NSW", "Warehouse",     "2015-01-01", None],
    ["QLD-STA", "Stapylton Warehouse",                    "QLD", "Warehouse",     "2025-05-12", None],
    ["QLD-OLD", "Previous QLD Warehouse",                 "QLD", "Warehouse",     "2015-01-01", "2025-05-11"],
], columns=["site_code", "site_name", "state", "site_type", "active_from", "active_to"])

fuel_levy = pd.DataFrame([
    ["2024-07-01", "2026-03-15", 0.000, "No levy"],
    ["2026-03-16", "2026-06-14", 0.075, "Temporary fuel levy introduced"],
    ["2026-06-15", "2026-12-31", 0.050, "Levy reduced as fuel prices eased"],
], columns=["effective_from", "effective_to", "levy_rate_on_freight", "note"])

def levy_rate(d):
    d = pd.Timestamp(d)
    for _, r in fuel_levy.iterrows():
        if pd.Timestamp(r.effective_from) <= d <= pd.Timestamp(r.effective_to):
            return r.levy_rate_on_freight
    return 0.0

# ---------------------------------------------------------------- CRM accounts
prefix = ["Northgate", "Bayline", "Eastside", "Summit", "Ironbark", "Coastal", "Metro", "Harbourline",
          "Ridgeway", "Southern Cross", "Bluestone", "Westpoint", "Highline", "Parkside", "Redgum",
          "Kingsway", "Riverbend", "Granite", "Silverleaf", "Oakridge", "Crestline", "Fairview",
          "Lakeside", "Stonebridge", "Clearwater", "Hillcrest", "Pinnacle", "Arrow", "Foundry", "Keystone"]
suffix_builder = ["Constructions", "Building Group", "Projects", "Developments"]
suffix_installer = ["Interiors", "Partitions", "Fire Walls", "Ceilings and Walls", "Drywall Services", "Linings"]
suffix_dist = ["Building Supplies", "Trade Supplies"]

state_w = {"VIC": 0.45, "NSW": 0.30, "QLD": 0.20, "SA": 0.03, "TAS": 0.02}
acc_rows, used = [], set()
for i in range(72):
    t = rng.choice(["Builder", "Installer", "Distributor"], p=[0.38, 0.52, 0.10])
    suf = {"Builder": suffix_builder, "Installer": suffix_installer, "Distributor": suffix_dist}[t]
    while True:
        name = f"{random.choice(prefix)} {random.choice(suf)} Pty Ltd"
        if name not in used:
            used.add(name)
            break
    st = rng.choice(list(state_w), p=list(state_w.values()))
    tier = rng.choice(["A", "B", "C"], p=[0.2, 0.45, 0.35])
    acc_rows.append([f"ACC-{1001 + i}", name, t, st, tier,
                     (START - pd.Timedelta(days=int(rng.integers(90, 3000)))).date()])
accounts = pd.DataFrame(acc_rows, columns=["account_id", "account_name", "account_type", "state", "price_tier", "created_date"])
discount_by_tier = {"A": 0.10, "B": 0.05, "C": 0.0}

# ---------------------------------------------------------------- CRM projects
suburbs = {
    "VIC": ["Docklands", "Southbank", "Box Hill", "Footscray", "Ringwood", "Preston", "Brunswick",
            "Cremorne", "Doncaster", "Werribee", "Richmond", "Collingwood", "Glen Waverley", "Dandenong"],
    "NSW": ["Parramatta", "Rhodes", "Chatswood", "Liverpool", "Zetland", "Macquarie Park", "Penrith",
            "Mascot", "Ryde", "Wollongong"],
    "QLD": ["Fortitude Valley", "Southport", "Broadbeach", "Woolloongabba", "Chermside", "Robina",
            "Newstead", "Toowong"],
    "SA": ["Adelaide", "Bowden"],
    "TAS": ["Hobart"],
}
type_by_segment = {
    "High-Rise & Commercial": ["Tower", "Commercial Centre", "Office Tower", "Hotel", "Plaza", "Health Hub"],
    "Multi-Residential": ["Residences", "Apartments", "Living", "Build to Rent", "Terraces"],
    "Industrial & Cinema": ["Cinema", "Logistics Centre", "Data Hall", "Cold Store", "Warehouse Fitout"],
    "Tunnels & Infrastructure": ["Tunnel Package", "Rail Station Services", "Ventilation Building", "Substation"],
}
messy_state = {
    "VIC": ["VIC", "Victoria", "vic", "VIC ", "Vic."],
    "NSW": ["NSW", "New South Wales", "nsw", "N.S.W."],
    "QLD": ["QLD", "Queensland", "qld", "Qld"],
    "SA":  ["SA", "South Australia"],
    "TAS": ["TAS", "Tasmania"],
}
proj_rows, pnames = [], set()
builders = accounts[accounts.account_type == "Builder"]
for i in range(560):
    created = START - pd.Timedelta(days=420) + pd.Timedelta(days=int(rng.integers(0, 1220)))
    if created > END - pd.Timedelta(days=20):
        created = END - pd.Timedelta(days=int(rng.integers(20, 120)))
    seg_p = [0.32, 0.43, 0.15, 0.10] if created < pd.Timestamp("2025-07-01") else [0.28, 0.40, 0.14, 0.18]
    seg = rng.choice(list(type_by_segment), p=seg_p)
    st = rng.choice(list(state_w), p=list(state_w.values()))
    while True:
        letter = random.choice(["", "", " A", " B", " Stage 2"])
        nm = f"{random.choice(suburbs[st])} {random.choice(type_by_segment[seg])}{letter}"
        if nm not in pnames:
            pnames.add(nm)
            break
    stage = rng.choice(["Won", "Lost", "Quoted", "Lead"], p=[0.58, 0.20, 0.14, 0.08])
    est_m2 = float(np.clip(rng.lognormal(7.3, 0.7), 300, 12000))
    if seg == "Tunnels & Infrastructure":
        est_m2 *= 1.6
    st_text = st if rng.random() > 0.18 else random.choice(messy_state[st])
    b = builders[builders.state == st]
    b = b if len(b) else builders
    builder_id = b.sample(1, random_state=int(rng.integers(0, 1e6))).account_id.iloc[0]
    won_date = created + pd.Timedelta(days=int(rng.integers(20, 140))) if stage == "Won" else pd.NaT
    if pd.notna(won_date) and won_date > END:
        stage, won_date = "Quoted", pd.NaT
    proj_rows.append([f"SUG-{20450 + i}", nm, seg, st_text, stage, builder_id, created.date(),
                      round(est_m2, 0), round(est_m2 * 68, 0),
                      won_date.date() if pd.notna(won_date) else None])
projects = pd.DataFrame(proj_rows, columns=["project_id", "project_name", "segment", "state", "stage",
                                            "builder_account_id", "created_date", "est_m2", "est_value", "won_date"])

# ---------------------------------------------------------------- ERP orders and lines
site_for_state = {"VIC": "VIC-BAY", "SA": "VIC-BAY", "TAS": "VIC-BAY", "NSW": "NSW-WH", "QLD": "QLD-STA"}
def true_state(txt):
    t = str(txt).strip().upper().replace(".", "")
    return {"VICTORIA": "VIC", "NEW SOUTH WALES": "NSW", "QUEENSLAND": "QLD",
            "SOUTH AUSTRALIA": "SA", "TASMANIA": "TAS"}.get(t, t)

def mangle_name(n):
    r = rng.random()
    if r < 0.74:
        return n
    if r < 0.88:
        return random.choice([n.upper(), n.lower(), n.replace(" ", "  "), f"{n} ", f" {n}", n.replace(" ", "-")])
    if r < 0.97:
        return (n.replace("Tower", "Twr").replace("Apartments", "Apts").replace("Residences", "Resi")
                 .replace("Commercial Centre", "Comm Ctr").replace("Logistics Centre", "Logistics Ctr")
                 .replace("Stage 2", "Stg2") + ("" if rng.random() < 0.5 else " - Level 3-12"))
    return ""

order_rows, line_rows = [], []
oid, lid = 100001, 1
won = projects[projects.stage == "Won"].copy()
installers_by_state = {s: g.account_id.tolist() for s, g in accounts[accounts.account_type != "Builder"].groupby("state")}
all_installers = accounts[accounts.account_type != "Builder"].account_id.tolist()

# active window for each won project
won["true_state"] = won.state.apply(true_state)
won["active_from"] = pd.to_datetime(won.won_date) + pd.to_timedelta(rng.integers(25, 100, len(won)), unit="D")
won["active_to"] = won.active_from + pd.to_timedelta(rng.integers(90, 480, len(won)), unit="D")
won["installer"] = [random.choice(installers_by_state.get(st, all_installers)) for st in won.true_state]

# monthly revenue target: ~20.5M FY25, growth ~7% a year, construction seasonality
season = {7: 1.00, 8: 1.05, 9: 1.05, 10: 1.08, 11: 1.06, 12: 0.72, 1: 0.62, 2: 1.00,
          3: 1.10, 4: 0.92, 5: 1.08, 6: 1.06}
norm = sum(season.values()) / 12
avg_order_value = 13800.0
daily_orders = {}
for d in work_days:
    years = (d - START).days / 365.25
    month_rev = 20.5e6 / 12 * (1.07 ** years) * season[d.month] / norm
    n_work = sum(1 for x in work_days if x.year == d.year and x.month == d.month)
    daily_orders[d] = month_rev / avg_order_value / n_work

for od in work_days:
    live = won[(won.active_from <= od) & (won.active_to >= od)]
    if live.empty:
        continue
    n_today = rng.poisson(daily_orders[od])
    for _ in range(n_today):
        p = live.sample(1, weights=live.est_m2, random_state=int(rng.integers(0, 1e9))).iloc[0]
        st = p.true_state
        candidates = installers_by_state.get(st, all_installers)
        cust = p.installer if rng.random() < 0.8 else (p.builder_account_id if rng.random() < 0.6 else random.choice(candidates))
        tier = accounts.loc[accounts.account_id == cust, "price_tier"].iloc[0]
        ship = site_for_state[st]
        if ship == "QLD-STA" and od < pd.Timestamp("2025-05-12"):
            ship = "QLD-OLD"
        if ship != "VIC-BAY" and rng.random() < 0.14:
            ship = "VIC-BAY"   # interstate fulfilment when local stock is short

        prof = rng.choice(["51mm", "64mm", "78mm"], p=[0.30, 0.45, 0.25])
        if p.segment == "Tunnels & Infrastructure":
            prof = rng.choice(["64mm", "78mm"], p=[0.35, 0.65])
        m2 = float(np.clip(rng.lognormal(5.0, 0.55), 20, 1200))

        non_stock = prof == "78mm" or m2 > 500
        requested = add_business_days(od, int(rng.integers(4, 19)))
        promised = add_business_days(od, int(rng.integers(10, 21)) if non_stock else int(rng.integers(3, 6)))
        if prof == "78mm" and pd.Timestamp("2026-02-01") <= od <= pd.Timestamp("2026-04-15"):
            promised = add_business_days(promised, int(rng.integers(5, 12)))
        r = rng.random()
        slip = 0 if r < 0.86 else (int(rng.integers(1, 8)) if r < 0.97 else -1)
        dispatch = add_business_days(promised, slip)

        status = "Dispatched"
        if dispatch > END:
            status, dispatch = "Open", pd.NaT
        if rng.random() < 0.02:
            status, dispatch = "Cancelled", pd.NaT

        base_freight = {"VIC-BAY": (180, 450), "NSW-WH": (200, 520), "QLD-STA": (220, 540), "QLD-OLD": (220, 540)}[ship]
        freight = rng.uniform(*base_freight) * (1 + m2 / 900)
        if ship == "VIC-BAY" and st != "VIC":
            freight += rng.uniform(850, 1900)
        freight = round(freight, 2)
        levy = round(freight * levy_rate(od), 2)

        order_rows.append([f"SO-{oid}", od.date(), cust, mangle_name(p.project_name), ship,
                           requested.date(), promised.date(),
                           dispatch.date() if pd.notna(dispatch) else None, status, freight, levy])

        disc = discount_by_tier[tier]
        p_sku = f"PNL-{prof[:2]}"
        t_sku = f"TRK-C{prof[:2]}"
        lns = [(p_sku, round(m2, 1)),
               (t_sku, round(m2 * rng.uniform(0.75, 1.0), 1)),
               ("SEAL-FR", max(1, int(m2 / rng.uniform(15, 25)))),
               ("FIX-PK", max(1, int(m2 / rng.uniform(35, 50))))]
        if rng.random() < 0.35:
            lns.append(("ANG-STL", round(m2 * rng.uniform(0.1, 0.3), 1)))
        for sku, qty in lns:
            lp = price_lookup[(sku, od)]
            up = round(lp * (1 - disc) * rng.uniform(0.985, 1.0), 2)
            if rng.random() < 0.004:
                up = round(up * random.choice([10, 0.1]), 2)   # keying error
            line_rows.append([lid, f"SO-{oid}", sku, qty, up, disc])
            lid += 1
        oid += 1

orders = pd.DataFrame(order_rows, columns=["order_id", "order_date", "customer_account_id", "project_ref",
                                           "ship_from_site", "requested_date", "promised_date",
                                           "dispatch_date", "order_status", "freight_cost", "fuel_levy"])
lines = pd.DataFrame(line_rows, columns=["line_id", "order_id", "sku", "qty", "unit_price", "discount_pct"])

# planted problem: a handful of completed orders with no dispatch date
idx = orders[orders.order_status == "Dispatched"].sample(frac=0.005, random_state=SEED).index
orders.loc[idx, "dispatch_date"] = None

# planted problem: duplicated export rows
dup_ids = orders.sample(frac=0.012, random_state=SEED + 1).order_id
orders = pd.concat([orders, orders[orders.order_id.isin(dup_ids)]], ignore_index=True)
lines = pd.concat([lines, lines[lines.order_id.isin(dup_ids)]], ignore_index=True)

orders = orders.sort_values(["order_date", "order_id"]).reset_index(drop=True)

# ---------------------------------------------------------------- production (Bayswater only)
panel_demand = (lines.merge(orders.drop_duplicates("order_id")[["order_id", "order_date"]], on="order_id")
                .query("sku.str.startswith('PNL')", engine="python"))
panel_demand["order_date"] = pd.to_datetime(panel_demand.order_date)
daily_need = panel_demand.groupby("sku").qty.sum() / len(work_days)

prod_rows = []
for d in work_days:
    down = rng.random() < 0.025
    for sku in ["PNL-51", "PNL-64", "PNL-78"]:
        if down:
            prod_rows.append([d.date(), "VIC-BAY", sku, 0.0, 0.0, "Planned maintenance"])
            continue
        out = daily_need[sku] * rng.uniform(0.85, 1.2)
        if sku == "PNL-78" and pd.Timestamp("2026-02-01") <= d <= pd.Timestamp("2026-04-15"):
            out *= rng.uniform(0.35, 0.65)    # coil shortage
        scrap = out * rng.uniform(0.012, 0.042)
        prod_rows.append([d.date(), "VIC-BAY", sku, round(out, 1), round(scrap, 1), None])
production = pd.DataFrame(prod_rows, columns=["production_date", "site_code", "sku", "m2_produced", "m2_scrapped", "downtime_reason"])

# ---------------------------------------------------------------- weekly inventory snapshots
od_clean = orders.drop_duplicates("order_id")
ship_lines = lines.drop_duplicates("line_id").merge(
    od_clean[["order_id", "ship_from_site", "dispatch_date"]], on="order_id")
ship_lines = ship_lines.dropna(subset=["dispatch_date"])
ship_lines["week"] = pd.to_datetime(ship_lines.dispatch_date).dt.to_period("W-SUN").dt.end_time.dt.normalize()
weekly_ship = ship_lines.groupby(["ship_from_site", "sku", "week"]).qty.sum()

weeks = pd.date_range(START, END, freq="W-SUN")
inv_rows = []
for site in ["VIC-BAY", "NSW-WH", "QLD-OLD", "QLD-STA"]:
    for sku in products.sku:
        avg = weekly_ship.loc[site, sku].mean() if (site, sku) in weekly_ship.index.droplevel(2) else 0
        if not avg or np.isnan(avg):
            avg = 5.0
        on_hand = avg * rng.uniform(3, 5)
        for w in weeks:
            if site == "QLD-OLD" and w > pd.Timestamp("2025-05-11"):
                break
            if site == "QLD-STA" and w < pd.Timestamp("2025-05-12"):
                continue
            shipped = weekly_ship.get((site, sku, w), 0.0)
            target = avg * rng.uniform(3, 5)
            receipts = max(0.0, target - on_hand + shipped) * rng.uniform(0.6, 1.0)
            if sku in ("PNL-78", "TRK-C78") and pd.Timestamp("2026-02-01") <= w <= pd.Timestamp("2026-04-20"):
                receipts *= 0.35
            on_hand = max(0.0, on_hand + receipts - shipped)
            inv_rows.append([w.date(), site, sku, round(on_hand, 1), round(receipts, 1), round(shipped, 1)])
inventory = pd.DataFrame(inv_rows, columns=["snapshot_week_ending", "site_code", "sku", "qty_on_hand", "qty_received_week", "qty_shipped_week"])

# ---------------------------------------------------------------- purchasing
materials = pd.DataFrame([
    ["RM-COIL", "Galvanised Steel Coil",         "t",     1450.0],
    ["RM-CEM",  "Cement",                         "t",      310.0],
    ["RM-AGG",  "Lightweight Aggregate Additive", "t",      520.0],
    ["RM-FOAM", "Foaming Agent",                  "L",        6.8],
    ["RM-SEAL", "Sealant Bulk Cartridges",        "each",     9.4],
    ["RM-PLT",  "Timber Pallets",                 "each",    21.0],
], columns=["material_code", "material_name", "uom", "base_unit_cost"])
suppliers = pd.DataFrame([
    ["SUP-01", "Pacific Coil Trading",   "Import",   "RM-COIL", (70, 100), 0.30],
    ["SUP-02", "Southern Strip Steel",   "Domestic", "RM-COIL", (35, 60),  0.15],
    ["SUP-03", "Bayside Cement Co",      "Domestic", "RM-CEM",  (5, 12),   0.08],
    ["SUP-04", "Lite Aggregates Aust",   "Domestic", "RM-AGG",  (10, 21),  0.10],
    ["SUP-05", "ChemFoam Industrial",    "Domestic", "RM-FOAM", (7, 14),   0.08],
    ["SUP-06", "SealTech Supplies",      "Domestic", "RM-SEAL", (7, 18),   0.10],
    ["SUP-07", "Eastern Pallet Recyclers", "Domestic", "RM-PLT", (3, 7),   0.05],
], columns=["supplier_id", "supplier_name", "origin", "material_code", "lead_days", "late_prob"])

po_rows, poid = [], 50001
for _, s in suppliers.iterrows():
    freq_days = {"RM-COIL": 21 if s.origin == "Import" else 30, "RM-CEM": 7, "RM-AGG": 14,
                 "RM-FOAM": 21, "RM-SEAL": 28, "RM-PLT": 10}[s.material_code]
    d = START - pd.Timedelta(days=60)
    base = materials.set_index("material_code").loc[s.material_code, "base_unit_cost"]
    while d <= END:
        qty = {"RM-COIL": rng.uniform(40, 90), "RM-CEM": rng.uniform(25, 45), "RM-AGG": rng.uniform(8, 18),
               "RM-FOAM": rng.uniform(800, 1600), "RM-SEAL": rng.uniform(2000, 5000), "RM-PLT": rng.uniform(80, 180)}[s.material_code]
        quoted = int(rng.integers(*s.lead_days))
        expected = d + pd.Timedelta(days=quoted)
        late = 0
        if rng.random() < s.late_prob:
            late = int(rng.integers(5, 31))
        if s.material_code == "RM-COIL" and pd.Timestamp("2025-11-15") <= d <= pd.Timestamp("2026-01-31"):
            late += int(rng.integers(15, 35))   # the coil disruption
        received = expected + pd.Timedelta(days=late)
        drift = 1 + (d - START).days / 365 * 0.04
        cost = round(base * drift * rng.uniform(0.96, 1.06), 2)
        po_rows.append([f"PO-{poid}", s.supplier_id, s.material_code, d.date(), expected.date(),
                        received.date() if received <= END else None, round(qty, 1), cost])
        poid += 1
        d += pd.Timedelta(days=int(freq_days * rng.uniform(0.8, 1.25)))
purchase_orders = pd.DataFrame(po_rows, columns=["po_number", "supplier_id", "material_code", "po_date",
                                                 "expected_date", "received_date", "qty", "unit_cost"])

# ---------------------------------------------------------------- write exports
products.drop(columns=["cost_ratio"]).rename(columns={"base_price": "launch_price"}).to_csv(f"{OUT}/erp_products.csv", index=False)
pd.DataFrame({"sku": products.sku, "std_cost_ratio": products.cost_ratio}).to_csv(f"{OUT}/erp_standard_cost.csv", index=False)
price_list.to_csv(f"{OUT}/erp_price_list.csv", index=False)
accounts.to_csv(f"{OUT}/crm_accounts_export.csv", index=False)
projects.to_csv(f"{OUT}/crm_projects_export.csv", index=False)
orders.to_csv(f"{OUT}/erp_sales_orders.csv", index=False)
lines.to_csv(f"{OUT}/erp_sales_order_lines.csv", index=False)
production.to_csv(f"{OUT}/prod_daily_output.csv", index=False)
inventory.to_csv(f"{OUT}/wms_inventory_weekly.csv", index=False)
materials.to_csv(f"{OUT}/erp_raw_materials.csv", index=False)
suppliers.drop(columns=["lead_days", "late_prob"]).to_csv(f"{OUT}/erp_suppliers.csv", index=False)
purchase_orders.to_csv(f"{OUT}/erp_purchase_orders.csv", index=False)
sites.to_csv(f"{OUT}/sharepoint_sites.csv", index=False)
fuel_levy.to_csv(f"{OUT}/sharepoint_fuel_levy_rates.csv", index=False)

pd.DataFrame(sorted((d.date(), r) for d, r in closed_reason.items()),
             columns=["calendar_date", "reason"]).to_csv(f"{OUT}/sharepoint_company_calendar.csv", index=False)
print("done")
