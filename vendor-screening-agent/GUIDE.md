# 🧭 Vendor Screening Agent — The Complete, Simple Guide

*Read this start to finish. It explains everything in plain words — no tech background needed. Take a breath; you've got this. 🙂*

---

## 1. What is this project? (the simplest explanation)

Imagine a company has a giant address book of all its **suppliers** (the companies it buys things from). Over the years, the **same supplier gets written down many times** with slightly different names — like saving your friend as "Sam", "Samuel", and "Sam ❤️" in your phone. Now you have three contacts for one person. Messy!

**Our project is a smart helper that checks the address book *before* you add a new supplier.** You type a company name, and it instantly tells you:

> *"Wait — we already have this company! Use the existing one."*
> or
> *"This one is new — go ahead and add it."*

That's it. It stops duplicate suppliers from being created.

---

## 2. What problem does it solve? (why anyone cares)

When the same supplier exists many times in the system:

- 💸 **Money looks scattered** — you paid one company $1M, but it shows as $300k + $400k + $300k across three records. You can't see the real total, so you lose bargaining power.
- 📊 **Reports become wrong** — dashboards need constant manual fixing.
- ⏰ **People waste hours** — cleaning up and merging duplicates by hand.
- ⚠️ **Risk** — you might add a company that isn't even real.

Our tool prevents all of this **at the moment of creation** — the cheapest place to fix it.

---

## 3. How does it work inside? (5 easy steps)

Think of the agent as a careful librarian doing 5 quick things:

1. **Clean** 🧽 — tidies the name you typed (removes "Ltd", "Pvt", extra spaces, fixes word order).
2. **Find** 🔎 — looks through your existing supplier list for look-alikes.
3. **Compare** ⚖️ — checks name, location, and other clues (not just the name!).
4. **Validate** 🌍 — checks a **free public company registry (GLEIF)** to confirm the company is **real**, and to spot if it's actually a **branch/child of a company you already have**.
5. **Recommend** ✅ — gives a clear answer and lets **a human decide**. The computer suggests; the person clicks the final choice.

**Golden rule it follows:** a matching *name alone* is never enough to call something a duplicate. It also needs supporting proof (same location, official ID, or same parent company). That's why it correctly knows *"Cognizant"* and *"Cognizant Chemical"* are **different companies**.

---

## 4. How to run it on your computer (step by step)

*Don't worry — just follow along. Each step is one line to type.*

### What you need first
- A **Mac or Linux/Windows** computer.
- **Python 3** installed. To check, open the **Terminal** app and type:
  ```
  python3 --version
  ```
  If it shows a number like `Python 3.11.x`, you're good. If not, install Python from https://www.python.org/downloads/ (just click Download and Next→Next).

### Step 1 — Open the project folder
In Terminal, type this and press Enter:
```
cd ~/Desktop/vendor-screening-agent
```
*(This means "go into the project folder on the Desktop".)*

### Step 2 — Start it (the easy way)
```
./run.sh
```
This one command installs everything it needs (first time only, ~1 minute) and starts the app.

> If `./run.sh` says "permission denied", run this once: `chmod +x run.sh` then try again.
> If you prefer to do it manually instead of run.sh:
> ```
> pip3 install -r requirements.txt
> python3 -m uvicorn app.main:app --port 8000
> ```

### Step 3 — Open it in your browser
When the Terminal shows a line like *"Uvicorn running on http://127.0.0.1:8000"*, open your web browser (Chrome) and go to:

```
http://127.0.0.1:8000
```

🎉 That's it — the app is running on your computer!

### Step 4 — Stop it when done
Go back to the Terminal window and press **Ctrl + C**.

### If something goes wrong (quick fixes)
- **Page won't open?** Make sure the Terminal still shows "Uvicorn running". If it closed, run `./run.sh` again.
- **"Port already in use"?** Something is already running on 8000. Close it, or start on another port: `python3 -m uvicorn app.main:app --port 8001` and open `http://127.0.0.1:8001`.
- **No internet?** The public-registry check needs internet. Without it, the app still works using your own supplier list.

---

## 5. How to use it (click-by-click)

1. On the left, type a **Company name** (e.g. `Cognizant`) and a **Location** (e.g. `India`).
   - *Even faster:* click one of the **example chips** (Cognizant, IBM, Infosys, Alpha Consulting).
2. Click **Check now**.
3. In ~1–2 seconds you'll see:
   - A big **verdict banner** at the top (the overall answer).
   - **Result cards** — each is one possible match.

### How to read a result card
- **The ring number (0–100)** = how strong the match is. Higher = more likely the same company.
- **The colored badge:**
  - 🟣 **Already exists** → very likely the same company — reuse it.
  - 🟡 **Worth a review** → looks close; a person should double-check.
  - 🟢 **Looks new** → probably a different/new company.
- **The source line (very important!):**
  - 🟣 **IN YOUR SUPPLIER LIST** + a `V####` id → **this is already in YOUR database.**
  - 🟢 **VERIFIED IN PUBLIC REGISTRY** + a long code → found in the **public company registry** (confirms it's a real company; may not be in your database yet).
- **"Why it matches"** = the plain-English reasons (name match, same country, same corporate group).
- **The pills** (Name 100% · Location 100% · Registry 90%) = the individual clues.

### The three buttons (they really work!)
- **Reuse existing** → "Use the record we already have." Nothing new is created. ✅ (This is the win — no duplicate!)
- **Review** → "Not sure — send it to a colleague to confirm."
- **Create new** → "This really is new — add it." (It actually adds the company to the database, and you'll find it next time you search.)

Every click is saved in the **"Recent decisions"** list in the sidebar — that's your record of what happened.

---

## 6. How to present it (your 5-minute script)

*Keep it simple and confident. Here's a flow you can follow almost word-for-word.*

**① The hook (30 sec)**
> "Big companies accidentally save the same supplier many times under different names. That scatters spend, breaks reports, and wastes hours cleaning up. We built an AI helper that catches duplicates *before* they're created."

**② Show it — Cognizant (1 min)**
- Click the **Cognizant** example.
- Point at the banner: *"It instantly says: this supplier already exists — reuse it."*
- Point at the 🟣 cards: *"These are already in our own database."*
- Point at the 🟢 cards: *"And it confirmed the company is real in the public registry."*

**③ The clever part — IBM (1 min)**
- Click **IBM**.
- Show the line *"Same corporate group as your vendor 'IBM'"*.
> "Even when the names look different, it catches that these are **branches of IBM** — using the public corporate-family data. Most simple tools can't do this."

**④ The safety part — Infosys (1 min)**
- Click **Infosys**.
- Point at **Capital Infosys / Ravi Infosys → "Looks new"**.
> "These just share the word 'Infosys' but are **different companies** — and the tool correctly does *not* merge them. We never wrongly combine two real suppliers. A human always makes the final call."

**⑤ Close (30 sec)**
> "So: cleaner data, no duplicate suppliers, real companies verified, and money and hours saved — with a human always in control. Thank you!"

### Simple slide order (if you make slides)
1. Title
2. The Problem (duplicate suppliers)
3. Our Solution (screen before you create)
4. How it works (the 5 steps)
5. Live demo (Cognizant / IBM / Infosys)
6. Benefits & savings
7. Thank you / Questions

---

## 7. Questions judges might ask (with easy answers)

- **"What's the business impact?"**
  > "Cleaner vendor data means accurate spend, better supplier deals, fewer manual clean-up hours, and lower risk."

- **"How is this different from just name-matching?"**
  > "We combine name + location + official registry + corporate-family links, and we never call something a duplicate on the name alone. That's how we avoid wrong merges."

- **"Does it scale?"**
  > "Yes — the same engine works for thousands of vendors, and the exact approach also works for other master data like customers or employees."

- **"Is it safe / who decides?"**
  > "The AI only recommends. A person clicks Reuse, Review, or Create — every decision is logged."

- **"What did you use?"**
  > "Python, a fast matching engine, and the free public GLEIF company registry — all on approved, standard tools."

- **"What are the limits?" (be honest — judges love honesty)**
  > "The public registry doesn't cover every tiny company, and savings figures are illustrative. Next steps: connect a website/tax-ID check for even stronger proof."

---

## 8. How to put it online (optional — for a shareable link)

**Fastest (for the demo):** keep it running locally and create a temporary public link:
```
brew install ngrok      # one time
ngrok http 8000         # gives a public https link to share
```

**Free permanent hosting: Render.com**
1. Put the project folder on GitHub.
2. On render.com → New → Web Service → connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   *(We already included a `Procfile` so Render/Railway detect this automatically.)*
5. Deploy → you get a public link like `https://yourapp.onrender.com`.

*(Note: on free hosting, newly "Created" vendors reset when the app redeploys — that's fine for a demo.)*

---

## 9. What's inside the project (so you know where things are)

```
vendor-screening-agent/
├─ app/                     ← the brain (Python)
│  ├─ main.py               starts the app
│  ├─ config.py             the settings (score thresholds, etc.)
│  ├─ scoring.py            the smart name-matching
│  ├─ gleif.py              talks to the public company registry
│  ├─ screening.py          puts it all together
│  └─ api/routes.py         the web addresses (/screen, /decision…)
├─ templates/index.html     ← the page you see
├─ static/                  ← the look (styles.css) and behaviour (app.js)
├─ data/                    ← the supplier list (the "database" CSV)
├─ tests/                   ← automatic checks (all passing ✅)
├─ requirements.txt         ← the list of things to install
├─ run.sh                   ← the one-command starter
├─ Procfile                 ← for online hosting
├─ GUIDE.md                 ← this friendly guide
└─ DOCUMENTATION.txt        ← the detailed technical report
```

---

## 10. One-line pitch (memorize this 💬)

> **"Before you add a new supplier, our AI instantly checks whether it already exists — even under a different name or as a subsidiary — using your own data plus public company registries, so you stop creating duplicates and keep your vendor data clean and trustworthy."**

---

*You're ready. Run it, click an example, and tell the story. Good luck — you've built something genuinely useful. 🚀*
