"""
Export CSV data files for Power BI.

Run from the project root:  python3 scripts/export_powerbi.py
Creates 3 files under data/powerbi/ that Power BI reads with Get Data -> CSV:
  1. duplicate_clusters.csv  - duplicate groups found in the vendor master
  2. kpi_summary.csv          - headline numbers (health score, savings, etc.)
  3. decisions_log.csv        - a realistic sample of screening decisions
"""
import csv
import os
import random
import sys
from datetime import datetime, timedelta

# make the app package importable when run from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rapidfuzz import fuzz
from app import data
from app.scoring import composite_name_score
from app.text_utils import name_core, country_sim

OUT_DIR = "data/powerbi"
COST_PER_DUPLICATE = 2500          # illustrative annual cost of one duplicate
CLUSTER_THRESHOLD = 0.85


class _UF:
    def __init__(self, n): self.p = list(range(n))
    def find(self, x):
        while self.p[x] != x: self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb: self.p[rb] = ra


def find_clusters(rows):
    n = len(rows)
    names = [str(r.get("vendor_name", "")) for r in rows]
    cores = [name_core(x) for x in names]
    uf = _UF(n)
    scores = {}
    for i in range(n):
        if not names[i]:
            continue
        for j in range(i + 1, n):
            if not names[j] or fuzz.token_set_ratio(cores[i], cores[j]) < 70:
                continue
            s = composite_name_score(names[i], names[j])["score"]
            if s >= CLUSTER_THRESHOLD and country_sim(rows[i].get("country", ""), rows[j].get("country", "")) >= 0.9:
                uf.union(i, j)
                scores[uf.find(i)] = max(scores.get(uf.find(i), 0), s)
    groups = {}
    for idx in range(n):
        if names[idx]:
            groups.setdefault(uf.find(idx), []).append(idx)
    clusters = [(root, members) for root, members in groups.items() if len(members) >= 2]
    return clusters, scores


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = data.get_master()
    rows = df.to_dict(orient="records")
    total = sum(1 for r in rows if str(r.get("vendor_name", "")).strip())

    clusters, scores = find_clusters(rows)

    # ---- 1. duplicate_clusters.csv ----
    dup_records = 0
    with open(f"{OUT_DIR}/duplicate_clusters.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cluster_id", "vendor_id", "vendor_name", "country", "city",
                    "cluster_size", "top_match_score", "is_keeper"])
        for cid, (root, members) in enumerate(clusters, 1):
            dup_records += len(members) - 1
            top = round(scores.get(root, 0) * 100, 1)
            for k, m in enumerate(members):
                r = rows[m]
                w.writerow([f"C{cid:03d}", r.get("vendor_id", ""), r.get("vendor_name", ""),
                            r.get("country", ""), r.get("city", ""), len(members), top,
                            "Yes" if k == 0 else "No"])

    health = round(100 * (total - dup_records) / total, 1) if total else 100.0
    saving = dup_records * COST_PER_DUPLICATE

    # ---- 2. kpi_summary.csv (WIDE: one row -> drag each column onto a Card) ----
    with open(f"{OUT_DIR}/kpi_summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Total_vendors", "Duplicate_clusters", "Redundant_records",
                    "Unique_entities", "Data_quality_score",
                    "Estimated_annual_saving_USD", "Cost_per_duplicate_USD"])
        w.writerow([total, len(clusters), dup_records, total - dup_records,
                    health, saving, COST_PER_DUPLICATE])

    # ---- 3. decisions_log.csv (realistic sample so charts look alive) ----
    random.seed(42)
    users = ["A. Sharma", "M. Iyer", "K. Patel", "R. Gupta", "S. Nair"]
    decisions = (["Reuse existing"] * 6 + ["Create new"] * 3 + ["Send to review"] * 2)
    names = [str(r.get("vendor_name", "")) for r in rows if str(r.get("vendor_name", "")).strip()]
    countries = [str(r.get("country", "")) for r in rows if str(r.get("country", "")).strip()]
    start = datetime(2026, 8, 15)
    with open(f"{OUT_DIR}/decisions_log.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "user", "vendor_name", "country", "decision", "match_percent", "duplicate_prevented"])
        for i in range(60):
            d = decisions[random.randrange(len(decisions))]
            dt = start + timedelta(days=random.randrange(0, 20), hours=random.randrange(9, 18))
            pct = random.randint(86, 100) if d == "Reuse existing" else (
                  random.randint(65, 84) if d == "Send to review" else random.randint(20, 64))
            w.writerow([dt.strftime("%Y-%m-%d"), random.choice(users),
                        random.choice(names), random.choice(countries), d, pct,
                        "Yes" if d == "Reuse existing" else "No"])

    print("Wrote Power BI data to", OUT_DIR + "/")
    print(f"  duplicate_clusters.csv  ({len(clusters)} clusters, {dup_records} redundant records)")
    print(f"  kpi_summary.csv         (health {health}/100, saving ${saving:,})")
    print("  decisions_log.csv       (60 sample decisions)")


if __name__ == "__main__":
    main()
