# 1337 — Merge report (Pax side only)

**Status: PARTIAL. Do not train on this yet as the full dataset.**

- Date: 2026-11-23 (morning, America/New_York)
- Merged here: Pax-side local files only, `data/*.jsonl` — **4,641 rows**.
- NOT merged: the three agent suites on GitHub, about **43,367 rows**
  (6,090 + 24,000 + 13,277). A `git clone` of the public repo failed
  in this run (sandbox egress denied during background preparation),
  so those rows were never fetched. The full merge of ~48,000 rows
  is still owed before any training run, per TRAINING_SPEC section 2.
- Outputs written (local only, not pushed):
  `data/leet_train.jsonl` (4,407 rows), `data/leet_val.jsonl` (234 rows).
  These contain Pax-side rows ONLY. They will be replaced by the full
  merge; do not mistake them for the 48k dataset.

## Validation

- Every line parsed as JSON with the PROMPT.md row shape: **0 failures**.
- Dedupe by normalized user text (case and whitespace folded),
  across all files: **0 duplicates** — 4,641 unique prompts.
- Spot audit: 50 random rows read by eye. **0 issues.** Leet voice
  holds in prose, code/commands/paths stay plain text, all rows are
  CTF/lab framed. No empty or short assistant replies found.

## Split

95% train / 5% val, stratified by hat x family (seed 1337).

| hat | family | rows | val |
|-----|--------|-----:|----:|
| red | argon | 68 | 3 |
| red | carbon | 68 | 3 |
| red | flash | 240 | 12 |
| red | hydrogen | 152 | 8 |
| red | neon | 56 | 3 |
| red | oc2_crypto | 200 | 10 |
| red | oc2_forensics | 200 | 10 |
| red | oc3_osint | 270 | 14 |
| red | oc3_rev | 270 | 14 |
| red | oc4_exp | 100 | 5 |
| blue | argon | 68 | 3 |
| blue | carbon | 69 | 3 |
| blue | flash | 240 | 12 |
| blue | hydrogen | 152 | 8 |
| blue | neon | 56 | 3 |
| blue | oc1_blue | 80 | 4 |
| blue | oc2_blue | 200 | 10 |
| blue | oc3_blue | 400 | 20 |
| blue | oc3_ir2 | 70 | 4 |
| blue | oc3_phish2 | 70 | 4 |
| blue | oc4_hi | 100 | 5 |
| blue | oc4_mn | 100 | 5 |
| chat | argon | 67 | 3 |
| chat | carbon | 68 | 3 |
| chat | flash | 239 | 12 |
| chat | hydrogen | 152 | 8 |
| chat | neon | 56 | 3 |
| chat | oc1_chat | 200 | 10 |
| chat | oc2_chat | 110 | 6 |
| chat | oc3_chat | 420 | 21 |
| chat | oc4_chat | 100 | 5 |
| **total** | | **4,641** | **234** |

## Next step

Fetch the three agent suites from GitHub (needs a session with
GitHub egress), re-run this same merge across all suites, and
rewrite `leet_train.jsonl` / `leet_val.jsonl` with the full ~48k.
Then the pilot (1,000 rows, Modal) can start.
