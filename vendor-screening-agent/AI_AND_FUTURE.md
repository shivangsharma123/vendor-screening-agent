# 🤖 Our AI + Future Scope — Simple Guide

*Everything you need to confidently answer "Did you use AI?" — plus where this can go next. Written in plain words.*

---

## 1. What AI are we using? (simple)

We use **classical AI / Machine Learning** built for one job: **figuring out if two company names are the same company** (this is called **"entity resolution"** — the same tech behind duplicate-detection in SAP and Informatica).

| # | The AI technique | In plain words | Tool |
|---|---|---|---|
| 1 | **Fuzzy matching** (Levenshtein, Jaro-Winkler) | Matches names even with typos, extra words, or different order | `rapidfuzz` |
| 2 | **TF-IDF + cosine similarity** | An ML way to measure how similar two texts are | `scikit-learn` |
| 3 | **Random Forest classifier** | An ML model that double-checks the match score | `scikit-learn` |
| 4 | **Smart rules** (acronyms, containment, corroboration) | "IBM = International Business Machines"; rejects "Capital Infosys" | our code |
| 5 | **Live registry validation** (GLEIF + EU VIES) | Confirms the company is real & legitimate, live | free public APIs |

👉 We do **NOT** use ChatGPT / an LLM at runtime. We use the AI that's *right* for this problem: explainable, fast, and auditable.

---

## 2. "Did you use AI?" — what to SAY (word for word)

> **"Yes. We use AI for entity resolution — the machine-learning discipline of deciding whether two records are the same real-world company. Specifically: fuzzy string matching, TF-IDF text-similarity, and a Random Forest classifier, combined with smart rules and live validation against public company registries. We deliberately avoided a large language model, because in regulated pharma the decision has to be explainable and auditable — our tool shows exactly *why* it flagged a match, and a human always makes the final call."**

That's it. Confident, honest, correct.

---

## 3. Follow-up questions (and easy answers)

**"Is fuzzy matching really AI?"**
> "Yes — approximate string matching and record-linkage are well-established AI/ML techniques. It's 'narrow AI' focused on similarity and classification, which is exactly what deduplication needs."

**"Did you use ChatGPT / an LLM?"**
> "Not at runtime — on purpose. An LLM can hallucinate and can't clearly explain why it merged two vendors. Our approach is deterministic and shows every signal, which matters for compliance. We can add an LLM later for plain-language explanations, but the decision stays rule-based."

**"What data is the Random Forest trained on?"** *(be honest)*
> "Right now on synthetic data, because we don't yet have a labelled set of real duplicate decisions — so it's a 25% secondary cross-check; the transparent rules are the primary engine. The honest next step is to retrain it on real human decisions, which our tool already logs in its audit trail."

**"How accurate is it?"**
> "On our test cases it correctly matches all the known duplicate types and correctly rejects look-alikes like 'Capital Infosys'. We measure it with automated tests; a formal precision/recall report on a labelled set is a next step."

---

## 4. Future scope (where this can go) 🚀

*Pick a few of these for your "Future Scope" slide.*

**Near-term (easy, high value)**
1. **Train the Random Forest on REAL data** — every Reuse/Review/Create click is saved in our audit log; that becomes the labelled training data to make the ML genuinely learned, not synthetic.
2. **Turn on the Website/Domain signal** — once vendor websites are in the data, domain matching becomes a strong disambiguator.
3. **Live GST validation for India** — add the official GST check (free-tier API) alongside EU VIES.
4. **Formal evaluation report** — publish precision / recall / false-positive rate on a labelled set.

**Medium-term**
5. **Bank-account matching** — catches duplicates *and* fraud (same bank account under different names) — a top real-world MDM signal.
6. **Sanctions / denied-party screening** — check vendors against public sanctions lists for compliance.
7. **Bulk mode** — upload a whole vendor file and get a full duplicate report at once.
8. **SAP / MDM integration** — plug directly into the vendor-creation workflow so it runs automatically before a record is saved.

**Advanced / optional**
9. **Semantic embeddings** — use AI embeddings for even smarter "different name, same company" matching.
10. **LLM for explanations only** — use an LLM to write a friendly plain-English reason, while keeping the decision rule-based and auditable.
11. **Power BI dashboard** — management view of data-quality score, duplicates prevented, and savings (data files already generated).

---

## 5. One-line summary (memorize)

> **"We use explainable AI for entity resolution — fuzzy matching + text-similarity + a Random Forest + live public-registry validation — chosen over an LLM because pharma needs decisions that are accurate, auditable, and human-controlled. Next, we'll train the model on the real decisions our tool already captures."**

---

*You're ready to answer any AI question with confidence — and show a clear, credible roadmap. 🌟*
