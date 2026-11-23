# 1337 Synthetic Dataset Suite (`agent 3`)

Generated with **Gemini 4 Carbon** (`gemini-4-carbon`) for fine-tuning **Qwen Coder + LoRA** into **1337**.
Every row uses the verbatim `PROMPT.md` system persona, preserves **100% plain-text runnable code, CLI flags, tool arguments, JSON schemas, queries, and file paths**, and applies natural leetspeak (`a=4, e=3, i=1, o=0, s=5, t=7, g=9, z=2`) strictly in prose.

---

## Inventory (`28` JSONL files — `13,277` verified rows)

### Phase 1 — Core Red / Blue Single-Turn SFT (`4,060` rows)
| File | Rows | Families | Description |
| :--- | ---: | :--- | :--- |
| `data/red_train.jsonl` | 2,030 | `203` × 10 Red families | CTF, lab range, sandbox & conceptual offensive mechanics + fixes |
| `data/blue_train.jsonl` | 2,030 | `203` × 10 Blue families | Log triage, alert investigation, IR, detection rules, hunting & hardening |

### Phase 2 — Agentic, Conversational, General Coding, Eval & DPO (`3,417` rows)
| File | Rows | Breakdown | Description |
| :--- | ---: | :--- | :--- |
| `data/multiturn_train.jsonl` | 807 | 20 `mt-*` families | 2–3 turn (`5–7` message) iterative CTF & live DFIR sessions |
| `data/coding_train.jsonl` | 600 | `60` × 10 families | Pure Rust/Go/C++/Python/TS/SQL coding & hacker tooling (anti-forgetting) |
| `data/dpo_pairs.jsonl` | 510 | `102` × 5 reasons | Preference pairs (`leet-in-code`, `plain-english-drift`, `unreadable-overleet`, `fluff-and-lectures`, `incomplete-fix`) |
| `data/agentic_train.jsonl` | 500 | `50` × 10 families | Native `tool_calls` (`read_file`, `grep_search`, `edit_file`, `run_command`) + error recovery |
| `data/purple_train.jsonl` | 400 | `40` × 10 families | Break (lab root cause) $\rightarrow$ Patch (code diff) $\rightarrow$ Detect (rule/query) |
| `data/val.jsonl` | 400 | Stratified (`split: "val"`) | Held-out evaluation benchmark across tracks (`0` overlap with `train`) |
| `data/boundary_train.jsonl` | 200 | `40` × 5 families | Crisp 1-line in-character scope guardrails + `allow-tricky-benign` anti-overrefusal |

### Phase 3 — Code-Model & Security-Engineering Specializations (`2,800` rows)
| File | Rows | Breakdown | Description |
| :--- | ---: | :--- | :--- |
| `data/fim_completion_train.jsonl` | 400 | `50` × 8 families | Prefix + `<FIM>` + suffix context-aware code & Sigma rule infill |
| `data/pr_review_train.jsonl` | 400 | `50` × 8 families | Unified `git diff` PR reviews (`APPROVE` clean code + `REQUEST_CHANGES` fixes) |
| `data/architecture_threatmodel_train.jsonl` | 400 | `80` × 5 families | Trust-boundary reviews, zero-trust PKI, multi-tenancy & AI/RAG architecture |
| `data/translate_modernize_train.jsonl` | 400 | `50` × 8 families | Legacy C/Python/JS/SQL/`iptables` $\rightarrow$ safe Rust/C++20/TS/`nftables` ports |
| `data/rootcause_postmortem_train.jsonl` | 400 | `50` × 8 families | 3-artifact outage & security incident causal-chain synthesis |
| `data/structured_json_train.jsonl` | 200 | `40` × 5 families | 1337 summary + strict `json.loads`-validated SARIF / OpenVEX / OCSF payloads |
| `data/log_to_rule_train.jsonl` | 200 | `40` × 5 families | Benign baseline noise + anomaly $\rightarrow$ false-positive-filtered detection rules |
| `data/decompile_to_source_train.jsonl` | 200 | `40` × 5 families | `x86_64` / `ARM64` / Ghidra / bytecode / Wasm $\rightarrow$ clean C/Rust/Python source |
| `data/terminal_oneliners_train.jsonl` | 200 | `40` × 5 families | Fast-reflex 2–4 line `jq` / `tshark` / `openssl` / `/proc` shell answers |

### Phase 4 — Deep Reasoning, Multi-File Repos, REPLs, Fuzzing & Specs (`3,000` rows)
| File | Rows | Breakdown | Description |
| :--- | ---: | :--- | :--- |
| `data/repl_sessions_train.jsonl` | 400 | `80` × 5 families | Stateful `(gdb)`/`pwndbg`, `(lldb)`, `psql`, `sqlite3`, `python3 -i` & `openssl` REPLs |
| `data/fuzz_and_test_train.jsonl` | 400 | `80` × 5 families | `libFuzzer`, Rust `proptest`, Python `Hypothesis`, TS `fast-check` & Foundry invariants |
| `data/reasoning_cot_train.jsonl` | 400 | `80` × 5 families | Optional `<think>...</think>` plain-text math/logic scratchpad + `1337` final answer |
| `data/skeptical_verify_train.jsonl` | 300 | `60` × 5 families | False-premise & security-myth traps (anti-sycophancy) |
| `data/long_context_repo_train.jsonl` | 300 | `60` × 5 families | Multi-file (`3–4` file) repository audits catching cross-file interaction bugs |
| `data/mental_trace_train.jsonl` | 300 | `60` × 5 families | Step-by-step C integer promotions, Rust lifetimes, SQL `NULL` & bitwise dry-runs |
| `data/rule_transpiler_train.jsonl` | 300 | `60` × 5 families | Cross-stack ports (`Sigma` $\leftrightarrow$ `SQL` $\leftrightarrow$ `KQL` $\leftrightarrow$ `jq` $\leftrightarrow$ `Rego` $\leftrightarrow$ `Suricata`) |
| `data/safe_hardening_train.jsonl` | 200 | `40` × 5 families | Production-safe hardening configs + breakage warnings + canary rollout steps |
| `data/toolsmith_mcp_train.jsonl` | 200 | `40` × 5 families | Sandboxed MCP servers & defensive CLIs in TypeScript, Python, Rust & Go |
| `data/spec_to_parser_train.jsonl` | 200 | `40` × 5 families | RFC wire-diagrams / BNF specs $\rightarrow$ bounds-checked encoders & decoders |

---

## Recommended Training Recipe (Qwen Coder + LoRA on Modal)

1. **Stage 1 — Supervised Fine-Tuning (SFT)**
   * **Standard Fast Build (`11,967` train rows):** Concatenate all `*_train.jsonl` files **except** `reasoning_cot_train.jsonl` (keep `val.jsonl` as `eval_dataset`).
   * **Reasoning-Capable Build (`12,367` train rows):** Include `reasoning_cot_train.jsonl` so `<think>...</think>` activates on hard math/crypto/concurrency problems.
   * Shuffle deterministically (`seed=1337`) after concatenation; mask loss to `assistant` turns (including `tool_calls`).
2. **Stage 2 — Preference Alignment (DPO / ORPO)**
   * Run 1 epoch of DPO (`beta=0.1`, `lr=5e-6`) on `data/dpo_pairs.jsonl` (`510` pairs) to lock in **zero leetspeak inside code blocks** and **zero preachy filler**.
3. **Verification**
   * Run `python3 "/Users/test/Desktop/1337/agent 3/verify_all.py"` anytime to re-audit all 28 files.
