# 🎬 Demo Cheat-Sheet — Example Inputs

Copy these into the form (Company name / Location / Tax ID). Each shows a different feature.
Best pitch order: **1 → 3 → 4 → 5**.

### 1) Duplicate already in your list
- Company: `Cognizant`  ·  Location: `India`
- → Finds Cognizant & Cognizant Technology Solutions already in your list.

### 2) Catches a subsidiary (different name) via public registry
- Company: `IBM`  ·  Location: `United States`
- → IBM Credit LLC / IBM JF LLC flagged because parent = International Business Machines Corporation.

### 3) Smart — does NOT wrongly merge look-alikes
- Company: `Infosys`  ·  Location: `India`
- → Real Infosys = match, but "Capital Infosys" / "Ravi Infosys" = "Looks new" (different companies).

### 4) 🔑 Tax ID catches a duplicate even with a different name
- Company: `Cognizant Corp`  ·  Location: `India`  ·  Tax ID: `29ABCDE1234F1Z5`
- → Matching Tax ID flags the Cognizant records as 100% duplicate despite the different name.

### 5) ⭐ Live EU VIES legitimacy check (real, free, official)
- Company: `Google Ireland`  ·  Location: `Ireland`  ·  Tax ID: `IE6388047V`
- → Green banner: "✅ VAT verified by EU VIES — GOOGLE IRELAND LIMITED"
- More real valid VATs: `IE9700053D` (Apple Distribution), `LU26375245` (Amazon Europe), `BE0417497106` (AB InBev)
- Invalid demo: any name · `Germany` · `DE000000000` → "not found in EU VIES"

### 6) A brand-new supplier (safe to add)
- Company: `Zxqwvfoo Traders`  ·  Location: `India`
- → "Looks like a new supplier."

### More name-variation duplicates
- `Alpha Consulting` / India (legal suffix)
- `ABC Pharma Services` / India (word order)
- `Blue-Tech R&D` / Germany (spacing)
- `Parent Company` / India (parent/child)

Tip: the example chips in the sidebar (Cognizant, IBM, Infosys, Alpha Consulting, Google live VAT) run these instantly.
