# 📊 Power BI Dashboard — Beginner Step-by-Step

*You're new to Power BI? Perfect — so is this guide's assumption. Just follow each step. You'll build a real dashboard in ~20 minutes. 🙂*

---

## What is Power BI (in one line)?
It's a **free Microsoft tool that turns a spreadsheet into charts and dashboards** by dragging and dropping — no coding.

## How it fits our project
Our screening app makes the decisions. Power BI is the **"management view"** on top of it — it shows leadership *how clean the vendor data is* and *how much the tool is helping*. It reads the data files we already generated.

---

## Step 0 — Generate the data files (already done, but here's how to refresh)
In the project folder terminal:
```
python3 scripts/export_powerbi.py      # Mac
py scripts\export_powerbi.py           # Windows
```
This creates 3 files in **`data/powerbi/`**:

| File | What's in it |
|---|---|
| `kpi_summary.csv` | The big numbers (health score, savings, totals) |
| `duplicate_clusters.csv` | Every duplicate group found in the vendor list |
| `decisions_log.csv` | A sample of screening decisions (Reuse/Review/Create) over time |

---

## Step 1 — Install Power BI Desktop (free, Windows)
1. Open the **Microsoft Store** on Windows.
2. Search **"Power BI Desktop"** → click **Get / Install** (it's free).
3. Open it. Close the welcome popup.

*(Mac note: Power BI Desktop is Windows-only. On a Mac, do this part on a Windows PC — that's why we made simple CSVs, so it's easy to move.)*

---

## Step 2 — Load the 3 data files
Do this **three times**, once per file:
1. Top menu → **Home → Get data → Text/CSV**.
2. Pick a file from `data/powerbi/` (start with `kpi_summary.csv`).
3. Click **Load**.
4. Repeat for `duplicate_clusters.csv` and `decisions_log.csv`.

You'll now see all 3 tables on the right in the **Data / Fields** panel. ✅

---

## Step 3 — Build PAGE 1: "Vendor Data Quality"

*(A "visual" = a chart. You add one by clicking its icon in the **Visualizations** panel, then dragging fields onto it.)*

**Visual 1 — Health score (a big number)**
- Click the **Card** visual icon.
- Drag **`Data_quality_score`** (from kpi_summary) onto it.
- 👉 Shows **77.8**. *(Tip: if it shows a sum, that's fine — there's only one row.)*

**Visual 2 — Duplicate clusters (big number)**
- Click **Card** again → drag **`Duplicate_clusters`**. 👉 Shows **21**.

**Visual 3 — Estimated saving (big number)**
- Click **Card** → drag **`Estimated_annual_saving_USD`**. 👉 Shows **55,000**.

**Visual 4 — Duplicates by country (bar chart)**
- Click **Clustered bar chart**.
- Drag **`country`** (from duplicate_clusters) to **Y-axis**.
- Drag **`vendor_name`** to **X-axis** — it will auto-change to **"Count of vendor_name"**.
- 👉 Bar chart of how many duplicate records per country.

**Visual 5 — The duplicate list (table)**
- Click the **Table** visual.
- Drag these fields onto it (in order): **`cluster_id`, `vendor_name`, `country`, `top_match_score`, `is_keeper`**.
- 👉 A clean table showing each duplicate group (e.g. *Alpha Consulting + Alpha Consulting Ltd.*).

Arrange them nicely: 3 cards across the top, bar chart bottom-left, table bottom-right.

---

## Step 4 — Build PAGE 2: "Screening Impact"
Add a new page: click the **+** at the bottom-left.

**Visual 1 — Total decisions (Card)**
- **Card** → drag **`decision`** (from decisions_log) → change it to **Count** (click the little arrow on the field → "Count").

**Visual 2 — Duplicates prevented (Card)**
- **Card** → drag **`duplicate_prevented`** → set to **Count**.
- Then click the visual → **Filters** panel → filter `duplicate_prevented` = **Yes**.
- 👉 Shows how many duplicates the tool stopped.

**Visual 3 — Decision breakdown (Donut chart)**
- Click **Donut chart**.
- Drag **`decision`** to **Legend**, and **`decision`** again to **Values** (it becomes Count).
- 👉 A donut showing Reuse vs Review vs Create.

**Visual 4 — Decisions over time (Column chart)**
- Click **Stacked column chart**.
- Drag **`date`** to **X-axis**, **`decision`** to **Y-axis** (Count) and to **Legend**.
- 👉 Shows activity over the days.

**Visual 5 — By user (bar chart)** *(optional)*
- **Clustered bar chart** → **`user`** on Y-axis, **`decision`** (Count) on X-axis.

---

## Step 5 — Make it look good (2 min)
- Click any chart → **Format** (paint-roller icon) → turn **Title** on and rename it (e.g. "Data Quality Score").
- Give each page a title text box: **Insert → Text box** → type "Vendor Data Quality" and "Screening Impact".
- Pick a color theme: **View → Themes** → choose one you like (a purple one matches our app 😄).

---

## Step 6 — Save & present
- **File → Save** (saves a `.pbix` file).
- To present: just show the two pages full-screen (**View → Full screen**), or **File → Export → PDF** for slides.

---

## What to SAY when you show it (simple)
> "Our screening app stops duplicates one by one. This Power BI dashboard is the big picture for management: **Page 1** shows our vendor data is 77.8% clean with 21 duplicate groups worth ~$55k/year to fix. **Page 2** shows the tool in action — how many suppliers were screened and how many duplicates we prevented. And it's all in Power BI, which Novo already uses."

---

## Why this earns points 🎯
- Uses **Power BI** — one of Novo's **approved tools** (the deck asked to build on approved platforms).
- Answers **"business impact / ROI"** and **"adoption / success metrics"** judge questions.
- Shows the app isn't a toy — it **feeds enterprise reporting**.

*That's it — you just learned Power BI by building something real. Nice work! 🚀*
