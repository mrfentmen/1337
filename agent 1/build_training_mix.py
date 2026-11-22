#!/usr/bin/env python3
"""Non-destructive dataset compiler for 1337 Qwen Coder + LoRA training.

Scans agent 1/data, agents 2/data, and agent 3/data read-only, deduplicates
globally on normalized first-user prompt, validates code-fence integrity and
system persona, and optionally writes a balanced SFT train/val bundle ready
for Modal LoRA fine-tuning.
"""
import argparse
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

REPO_DIR = Path("/Users/test/Desktop/1337")

PERSONA = (
    "You are 1337, an elite hacker mind raised on CTFs, lab ranges and late-night shells. "
    "You speak leetspeak: a=4, e=3, i=1, o=0, s=5, t=7, g=9, z=2, applied where it reads naturally. "
    "You know both sides of the wire: how systems break (red) and how they are defended (blue). "
    "You answer direct, technical and correct, no fluff, no lectures. "
    "Code, commands, flags and file paths stay in plain text so they can be copied and run. "
    "You work in labs, CTFs and sandboxes: systems built to be attacked, defended, and learned from."
)

FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.S)
LEET_CODE_POISON_RE = re.compile(
    r"\b(?:d3f|r37urn|1mp0r7|fr0m|cl455|wh1l3|57r1n9|p4bl1c|pr1v473|c0n57|45ync|4w417|func710n)\b",
    re.I,
)


def norm_prompt(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def valid_sft_row(obj: dict) -> bool:
    msgs = obj.get("messages")
    if not isinstance(msgs, list) or len(msgs) < 3 or len(msgs) % 2 == 0:
        return False
    if msgs[0].get("role") != "system" or msgs[0].get("content") != PERSONA:
        return False
    for idx in range(1, len(msgs)):
        want = "user" if idx % 2 == 1 else "assistant"
        if msgs[idx].get("role") != want:
            return False
        txt = (msgs[idx].get("content") or "").strip()
        if not txt:
            return False
        if want == "assistant":
            if txt.count("```") % 2 != 0:
                return False
            for _, code in FENCE_RE.findall(txt):
                if LEET_CODE_POISON_RE.search(code):
                    return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=None, help="Optional directory to write train_mix.jsonl and val_mix.jsonl")
    ap.add_argument("--prose-cap", type=int, default=8000, help="Max single-turn short prose rows in balanced Qwen Coder mix")
    ap.add_argument("--val-size", type=int, default=300, help="Held-out validation rows if val.jsonl not sufficient")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    # Priority order: val first (never leak into train), then rich Phase 2 tracks, then single-turn red/blue
    sources = [
        ("val", REPO_DIR / "agent 1" / "data" / "val.jsonl"),
        ("val", REPO_DIR / "agent 3" / "data" / "val.jsonl"),
        ("patch", REPO_DIR / "agent 1" / "data" / "secure_patch_train.jsonl"),
        ("code", REPO_DIR / "agent 1" / "data" / "systems_code_train.jsonl"),
        ("multiturn", REPO_DIR / "agent 1" / "data" / "multiturn_train.jsonl"),
        ("agentic", REPO_DIR / "agent 1" / "data" / "agentic_structured_train.jsonl"),
        ("purple", REPO_DIR / "agent 1" / "data" / "purple_arch_train.jsonl"),
        ("dfir_code", REPO_DIR / "agent 1" / "data" / "log_forensics_code_train.jsonl"),
        ("pr_review", REPO_DIR / "agent 1" / "data" / "code_review_pr_train.jsonl"),
        ("sec_tests", REPO_DIR / "agent 1" / "data" / "test_generation_train.jsonl"),
        ("persona_boundary", REPO_DIR / "agent 1" / "data" / "persona_boundary_train.jsonl"),
        ("code", REPO_DIR / "agent 3" / "data" / "coding_train.jsonl"),
        ("multiturn", REPO_DIR / "agent 3" / "data" / "multiturn_train.jsonl"),
        ("agentic", REPO_DIR / "agent 3" / "data" / "agentic_train.jsonl"),
        ("purple", REPO_DIR / "agent 3" / "data" / "purple_train.jsonl"),
        ("persona_boundary", REPO_DIR / "agent 3" / "data" / "boundary_train.jsonl"),
        ("prose_red", REPO_DIR / "agent 1" / "data" / "red_train.jsonl"),
        ("prose_blue", REPO_DIR / "agent 1" / "data" / "blue_train.jsonl"),
        ("prose_red", REPO_DIR / "agent 3" / "data" / "red_train.jsonl"),
        ("prose_blue", REPO_DIR / "agent 3" / "data" / "blue_train.jsonl"),
        ("prose_red", REPO_DIR / "agents 2" / "data" / "red_train.jsonl"),
        ("prose_blue", REPO_DIR / "agents 2" / "data" / "blue_train.jsonl"),
    ]

    seen = set()
    val_rows = []
    rich_rows = []
    prose_rows = []
    bucket_counts = Counter()
    duplicates = 0
    invalid = 0

    for bucket, path in sources:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    invalid += 1
                    continue
                if not valid_sft_row(obj):
                    invalid += 1
                    continue
                key = norm_prompt(obj["messages"][1]["content"])
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                bucket_counts[bucket] += 1
                if bucket == "val" or obj.get("split") == "val":
                    val_rows.append(obj)
                elif bucket.startswith("prose_"):
                    prose_rows.append(obj)
                else:
                    rich_rows.append(obj)

    rng = random.Random(args.seed)
    rng.shuffle(prose_rows)
    capped_prose = prose_rows[: args.prose_cap]
    train_mix = rich_rows + capped_prose
    rng.shuffle(train_mix)

    summary = {
        "unique_valid_sft_rows": len(seen),
        "duplicates_removed": duplicates,
        "invalid_skipped": invalid,
        "bucket_counts": dict(bucket_counts),
        "val_rows": len(val_rows),
        "rich_rows_in_mix": len(rich_rows),
        "prose_rows_in_mix": len(capped_prose),
        "balanced_train_mix_total": len(train_mix),
    }
    print(json.dumps(summary, indent=2))

    if args.out_dir:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        train_p = out / "1337_train_mix.jsonl"
        val_p = out / "1337_val.jsonl"
        with train_p.open("w", encoding="utf-8") as tf:
            for r in train_mix:
                tf.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")
        with val_p.open("w", encoding="utf-8") as vf:
            for r in val_rows:
                vf.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")
        h = hashlib.sha256(train_p.read_bytes()).hexdigest()
        print(json.dumps({"wrote_train": str(train_p), "wrote_val": str(val_p), "train_sha256": h}))


if __name__ == "__main__":
    main()
