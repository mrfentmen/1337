#!/usr/bin/env python3
"""End-to-end integrity, schema, persona, and zero-leakage verifier for agent 3's 28 JSONL datasets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/test/Desktop/1337/agent 3")
import bank_expansion as be

DATA_DIR = Path("/Users/test/Desktop/1337/agent 3/data")
PROMPT_TEXT = Path("/Users/test/Desktop/1337/PROMPT.md").read_text(encoding="utf-8")


def main() -> None:
    assert be.PERSONA in PROMPT_TEXT, "PERSONA mismatch against PROMPT.md"

    jsonl_files = sorted(DATA_DIR.glob("*.jsonl"))
    assert len(jsonl_files) == 28, f"Expected 28 jsonl files, found {len(jsonl_files)}"

    global_ids: set[str] = set()
    train_users: set[str] = set()
    val_users: set[str] = set()
    dpo_users: set[str] = set()
    file_counts: list[tuple[str, int, str]] = []

    for p in jsonl_files:
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert lines, f"Empty file: {p.name}"
        for idx, ln in enumerate(lines, start=1):
            obj = json.loads(ln)
            rid = obj["id"]
            assert rid not in global_ids, f"Duplicate ID {rid} in {p.name}:{idx}"
            global_ids.add(rid)
            assert obj.get("generator") == "gemini-4-carbon", f"Bad generator in {rid}"

            msgs = obj["messages"]
            assert msgs[0] == {"role": "system", "content": be.PERSONA}, f"Bad system prompt in {rid}"
            u0 = be._extract_first_user(obj)
            assert u0 and len(u0.strip()) >= 15, f"Missing/short user prompt in {rid}"
            nu = be._norm_user(u0)

            if p.name == "dpo_pairs.jsonl":
                assert "chosen" in obj and "rejected" in obj
                assert be.has_natural_leet(obj["chosen"], min_words=3), f"DPO chosen missing leet in {rid}"
                assert not be.has_leet_inside_code(obj["chosen"]), f"DPO chosen has leet in code in {rid}"
                assert nu not in dpo_users, f"Duplicate DPO prompt in {rid}"
                dpo_users.add(nu)
            else:
                if p.name == "val.jsonl":
                    assert obj["split"] == "val"
                    assert nu not in val_users, f"Duplicate val prompt in {rid}"
                    val_users.add(nu)
                else:
                    assert obj["split"] == "train"
                    assert nu not in train_users, f"Duplicate train prompt in {rid}"
                    train_users.add(nu)

                if p.name == "structured_json_train.jsonl":
                    assert be.has_valid_json_block(msgs[-1]["content"]), f"Invalid JSON block in {rid}"
                elif p.name == "reasoning_cot_train.jsonl":
                    m = be.THINK_RE.match(msgs[-1]["content"])
                    assert m and be.has_natural_leet(m.group(2), min_words=3), f"Bad <think> format in {rid}"
                else:
                    min_w = 2 if p.name == "terminal_oneliners_train.jsonl" else 3
                    assert be.has_natural_leet(msgs[-1]["content"], min_words=min_w), f"Missing leet in {rid}"

        split_label = "dpo" if p.name == "dpo_pairs.jsonl" else ("val" if p.name == "val.jsonl" else "train")
        file_counts.append((p.name, len(lines), split_label))

    leak_train_val = len(train_users & val_users)
    leak_dpo_val = len(dpo_users & val_users)
    assert leak_train_val == 0, f"Train/Val leakage detected: {leak_train_val}"
    assert leak_dpo_val == 0, f"DPO/Val leakage detected: {leak_dpo_val}"

    sibling_paths = [
        p for pat in ("*/*/*.jsonl", "*/*.jsonl")
        for p in Path("/Users/test/Desktop/1337").glob(pat)
        if DATA_DIR.parent not in p.parents
    ]
    sibling_users = be._load_seen_users(sibling_paths)
    sibling_overlap = len((train_users | val_users | dpo_users) & sibling_users)

    total = sum(c for _, c, _ in file_counts)
    sft_train_total = sum(c for _, c, s in file_counts if s == "train")
    print(f"ALL 28 DATASETS VERIFIED CLEAN: {total:,} total rows")
    print(f"  - SFT train rows : {sft_train_total:,} (across 26 files)")
    print(f"  - Held-out val   : {len(val_users):,} (0 train/val leakage)")
    print(f"  - DPO pairs      : {len(dpo_users):,} (0 val leakage)")
    print(f"  - Sibling overlap: {sibling_overlap} collisions against agent 1 / agents 2")
    for fname, cnt, sl in file_counts:
        print(f"    [{sl:5s}] {fname:38s} -> {cnt:5,d} rows")


if __name__ == "__main__":
    main()
