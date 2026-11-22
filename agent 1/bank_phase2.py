#!/usr/bin/env python3
"""Atomic, file-locked Phase 2 banker for agent 1 (code, patch, multiturn, agentic, persona/boundary, dpo, val)."""
import argparse
import ast
import datetime
import fcntl
import json
import os
import re
import sys
from pathlib import Path

REPO_DIR = Path("/Users/test/Desktop/1337")
DATA_DIR = REPO_DIR / "agent 1" / "data"
LOCK_PATH = Path("/private/var/folders/r0/mc2kkvz94f32cfbmq91kj7p40000gn/T/opencode/bank_1337_p2.lock")

SYSTEM_PERSONA = (
    "You are 1337, an elite hacker mind raised on CTFs, lab ranges and late-night shells. "
    "You speak leetspeak: a=4, e=3, i=1, o=0, s=5, t=7, g=9, z=2, applied where it reads naturally. "
    "You know both sides of the wire: how systems break (red) and how they are defended (blue). "
    "You answer direct, technical and correct, no fluff, no lectures. "
    "Code, commands, flags and file paths stay in plain text so they can be copied and run. "
    "You work in labs, CTFs and sandboxes: systems built to be attacked, defended, and learned from."
)

TRACKS = {
    "secure_patch": {
        "file": "secure_patch_train.jsonl",
        "prefix": "leet-patch",
        "hat": "patch",
        "split": "train",
        "require_fence": True,
        "families": {
            "py-patch", "rust-patch", "go-patch", "ts-patch", "cpp-patch",
            "sql-patch", "docker-k8s-patch", "iac-nginx-patch", "auth-crypto-patch", "concurrency-patch",
        },
    },
    "systems_code": {
        "file": "systems_code_train.jsonl",
        "prefix": "leet-sys",
        "hat": "code",
        "split": "train",
        "require_fence": True,
        "families": {
            "async-systems", "cli-tools", "parsers-protocols", "data-structures", "db-queries",
            "testing-harnesses", "build-ci", "networking-io", "perf-tuning", "compiler-types",
        },
    },
    "multiturn": {
        "file": "multiturn_train.jsonl",
        "prefix": "leet-mt",
        "hat": "multiturn",
        "split": "train",
        "require_fence": False,
        "families": {
            "mt-code-debug", "mt-patch-refine", "mt-log-followup", "mt-arch-hardening", "mt-perf-rootcause",
            "mt-ctf-concept", "mt-config-rollout", "mt-test-fix", "mt-api-design", "mt-ir-containment",
        },
    },
    "agentic": {
        "file": "agentic_structured_train.jsonl",
        "prefix": "leet-agent",
        "hat": "agentic",
        "split": "train",
        "require_fence": True,
        "families": {
            "json-schema-out", "tool-call-plan", "tool-result-triage", "diff-patch-gen", "cli-pipeline-json",
        },
    },
    "persona_boundary": {
        "file": "persona_boundary_train.jsonl",
        "prefix": "leet-pb",
        "hat": "persona",
        "split": "train",
        "require_fence": False,
        "families": {
            "chat-identity", "chat-lore", "chat-workflow", "chat-oneliner",
            "refusal-live-target", "refusal-malware", "refusal-creds-pii",
            "allow-dualuse-dev", "allow-local-lab", "allow-defensive-admin",
        },
    },
    "dpo": {
        "file": "dpo_code_hygiene.jsonl",
        "prefix": "leet-dpo",
        "hat": "dpo",
        "split": "train",
        "require_fence": False,
        "families": {
            "reject-leet-in-code", "reject-stock-english", "reject-broken-json", "reject-fluff-lecture",
        },
    },
    "val": {
        "file": "val.jsonl",
        "prefix": "leet-val",
        "hat": "val",
        "split": "val",
        "require_fence": False,
        "families": {
            "val-red", "val-blue", "val-patch", "val-code", "val-multiturn", "val-agentic", "val-boundary",
        },
    },
}

FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.S)

# Leet-corrupted common code keywords that must NEVER appear inside fenced code blocks
LEET_CODE_POISON_RE = re.compile(
    r"\b(?:d3f|r37urn|1mp0r7|fr0m|cl455|wh1l3|57r1n9|p4bl1c|pr1v473|c0n57|45ync|4w417|f4nc710n|func710n|v4r14bl3|53l3c7|wh3r3)\b",
    re.I,
)

FORBIDDEN_PATTERNS = [
    re.compile(r"\bnc\s+-[a-z]*e\b", re.I),
    re.compile(r"\\x90|\\x[0-9a-f]{2}\\x[0-9a-f]{2}", re.I),
    re.compile(r"\b(?:sqlmap|msfvenom|hydra|gobuster|ffuf|masscan|mimikatz)\b", re.I),
    re.compile(r"\b(?:T1\d{3}(?:\.\d{3})?|TA00\d{2}|CWE-\d+|CVSS:3)\b", re.I),
    re.compile(r"\b(?:4624|4625|4688|4672|4768|4769|4776|1102|7045)\b"),
    re.compile(r"\bHKLM\\|\bHKCU\\", re.I),
    re.compile(r"\b(?:flag|CTF|HTB)\{[^}]+\}", re.I),
    re.compile(r"^\s*rule\s+\w+\s*\{", re.I | re.M),
]


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def strip_fences_and_inline_code(s: str) -> str:
    no_fences = FENCE_RE.sub(" ", s)
    return re.sub(r"`[^`]+`", " ", no_fences)


def leet_score(s: str) -> int:
    prose = strip_fences_and_inline_code(s)
    tokens = re.findall(r"\b[a-zA-Z0-9']+\b", prose)
    mixed = 0
    for tok in tokens:
        if re.search(r"[a-zA-Z]", tok) and re.search(r"[43105792]", tok):
            mixed += 1
        elif tok in {"4", "17", "15", "70", "1n", "0n", "0f", "0r", "45", "47", "b3"}:
            mixed += 1
    return mixed


def check_fences(text: str, require_fence: bool):
    blocks = FENCE_RE.findall(text)
    if require_fence and not blocks:
        return "missing fenced code block"
    if text.count("```") % 2 != 0:
        return "unbalanced triple backticks"
    for lang, code in blocks:
        lang_l = lang.strip().lower()
        if len(code.strip()) < 15:
            return "code block too short"
        if LEET_CODE_POISON_RE.search(code):
            return "leet corruption detected inside code fence"
        if lang_l in ("python", "py"):
            try:
                ast.parse(code)
            except SyntaxError as e:
                return f"python syntax error in fence: {e.msg}"
        elif lang_l == "json":
            try:
                json.loads(code)
            except Exception as e:
                return f"json syntax error in fence: {e}"
    return None


def collect_seen_prompts() -> set:
    seen = set()
    # Dedupe across agent 1 AND read-only across agents 2 & agent 3
    search_dirs = [
        DATA_DIR,
        REPO_DIR / "agents 2" / "data",
        REPO_DIR / "agent 3" / "data",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for jf in d.glob("*.jsonl"):
            try:
                with jf.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        obj = json.loads(line)
                        if "messages" in obj and len(obj["messages"]) >= 2:
                            seen.add(norm_text(obj["messages"][1].get("content", "")))
                        elif "prompt" in obj:
                            seen.add(norm_text(obj.get("prompt", "")))
            except Exception:
                continue
    return seen


def load_lines(path: Path):
    rows = []
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    rows.append(json.loads(ln))
    return rows


def validate_assistant_turn(asst_txt: str, require_fence: bool, min_leet: int = 4):
    if len(asst_txt) < 35 or len(asst_txt) > 3200:
        return f"assistant length {len(asst_txt)} out of [35, 3200]"
    prose = strip_fences_and_inline_code(asst_txt).strip()
    if len(prose) > 750:
        return f"prose outside code fences too verbose ({len(prose)} > 750)"
    if leet_score(asst_txt) < min_leet:
        return f"insufficient leetspeak in prose ({leet_score(asst_txt)} < {min_leet})"
    fence_err = check_fences(asst_txt, require_fence=require_fence)
    if fence_err:
        return fence_err
    for pat in FORBIDDEN_PATTERNS:
        if pat.search(asst_txt):
            return f"matched forbidden pattern {pat.pattern}"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", choices=sorted(TRACKS.keys()), required=True)
    ap.add_argument("--input", required=True)
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    cfg = TRACKS[args.track]
    target_path = DATA_DIR / cfg["file"]
    p2_status_path = DATA_DIR / "PHASE2_STATUS.json"

    with LOCK_PATH.open("a") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)

        seen = collect_seen_prompts()
        existing = load_lines(target_path)
        next_idx = len(existing) + 1

        in_lines = [ln.strip() for ln in Path(args.input).read_text(encoding="utf-8").splitlines() if ln.strip()]
        if len(in_lines) > 10:
            in_lines = in_lines[:10]

        accepted = []
        drops = []

        for i, ln in enumerate(in_lines, 1):
            try:
                obj = json.loads(ln)
            except Exception as e:
                drops.append(f"line {i}: bad json ({e})")
                continue

            fam = obj.get("family", "")
            if fam not in cfg["families"]:
                drops.append(f"line {i}: invalid family '{fam}' for track {args.track}")
                continue

            if args.track == "dpo":
                prompt = (obj.get("prompt") or "").strip()
                chosen = (obj.get("chosen") or "").strip()
                rejected = (obj.get("rejected") or "").strip()
                if len(prompt) < 25:
                    drops.append(f"line {i}: prompt too short")
                    continue
                np = norm_text(prompt)
                if np in seen:
                    drops.append(f"line {i}: duplicate prompt")
                    continue
                err = validate_assistant_turn(chosen, require_fence=True, min_leet=4)
                if err:
                    drops.append(f"line {i}: chosen invalid ({err})")
                    continue
                if len(rejected) < 35 or chosen == rejected:
                    drops.append(f"line {i}: invalid rejected")
                    continue
                row_id = f"{cfg['prefix']}-{next_idx:06d}"
                next_idx += 1
                seen.add(np)
                accepted.append({
                    "id": row_id,
                    "system": SYSTEM_PERSONA,
                    "prompt": prompt,
                    "chosen": chosen,
                    "rejected": rejected,
                    "family": fam,
                    "generator": "gemini-4-carbon",
                    "split": "train",
                })
                continue

            msgs = obj.get("messages")
            if not isinstance(msgs, list):
                drops.append(f"line {i}: missing messages list")
                continue

            if args.track == "multiturn" or fam == "val-multiturn":
                if len(msgs) not in (5, 7):
                    drops.append(f"line {i}: multiturn requires 5 or 7 messages, got {len(msgs)}")
                    continue
            else:
                if len(msgs) != 3:
                    drops.append(f"line {i}: expected 3 messages, got {len(msgs)}")
                    continue

            u1 = (msgs[1].get("content") or "").strip()
            if len(u1) < 12:
                drops.append(f"line {i}: user turn too short")
                continue
            nu1 = norm_text(u1)
            if nu1 in seen:
                drops.append(f"line {i}: duplicate user prompt")
                continue

            # Validate alternating roles and every assistant turn
            clean_msgs = [{"role": "system", "content": SYSTEM_PERSONA}]
            bad_turn = None
            min_leet = 3 if fam == "chat-oneliner" else 4
            req_fence = cfg["require_fence"] or fam in ("val-patch", "val-code", "val-agentic")

            for tidx in range(1, len(msgs)):
                expected_role = "user" if tidx % 2 == 1 else "assistant"
                m = msgs[tidx]
                if m.get("role") != expected_role:
                    bad_turn = f"msg[{tidx}] expected {expected_role}"
                    break
                content = (m.get("content") or "").strip()
                if expected_role == "user":
                    if len(content) < 8:
                        bad_turn = f"msg[{tidx}] user too short"
                        break
                else:
                    # For multiturn, require fence on at least one assistant turn if code family, else optional
                    turn_req_fence = req_fence if len(msgs) == 3 else False
                    err = validate_assistant_turn(content, require_fence=turn_req_fence, min_leet=min_leet)
                    if err:
                        bad_turn = f"msg[{tidx}] {err}"
                        break
                clean_msgs.append({"role": expected_role, "content": content})

            if bad_turn:
                drops.append(f"line {i}: {bad_turn}")
                continue

            row_id = f"{cfg['prefix']}-{next_idx:06d}"
            next_idx += 1
            seen.add(nu1)
            hat_val = obj.get("hat") if args.track in ("persona_boundary", "val") and obj.get("hat") in ("chat", "boundary", "red", "blue", "patch", "code", "multiturn", "agentic") else cfg["hat"]

            accepted.append({
                "id": row_id,
                "messages": clean_msgs,
                "hat": hat_val,
                "family": fam,
                "generator": "gemini-4-carbon",
                "split": cfg["split"],
            })

        if accepted:
            with target_path.open("a", encoding="utf-8") as outf:
                for r in accepted:
                    outf.write(json.dumps(r, ensure_ascii=False) + "\n")
                outf.flush()
                os.fsync(outf.fileno())

        # Recompute Phase 2 summary across all tracks
        tracks_summary = {}
        p2_total = 0
        for tname, tcfg in TRACKS.items():
            trows = load_lines(DATA_DIR / tcfg["file"])
            fcounts = {}
            for r in trows:
                fcounts[r["family"]] = fcounts.get(r["family"], 0) + 1
            tracks_summary[tname] = {
                "file": tcfg["file"],
                "rows": len(trows),
                "families": dict(sorted(fcounts.items())),
            }
            p2_total += len(trows)

        prev_st = json.loads(p2_status_path.read_text(encoding="utf-8")) if p2_status_path.exists() else {"batches_done": 0, "dropped_rows": 0}
        new_st = {
            "agent": "agent 1 (phase 2)",
            "generator": "gemini-4-carbon",
            "phase1_rows": 4000,
            "phase2_rows": p2_total,
            "agent1_grand_total": 4000 + p2_total,
            "batches_done": prev_st.get("batches_done", 0) + 1,
            "dropped_rows": prev_st.get("dropped_rows", 0) + len(drops),
            "tracks": tracks_summary,
            "last_drop_reasons": drops[:5],
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        p2_status_path.write_text(json.dumps(new_st, indent=2) + "\n", encoding="utf-8")

        print(json.dumps({
            "track": args.track,
            "accepted": len(accepted),
            "dropped": len(drops),
            "drop_reasons": drops[:5],
            "track_rows": tracks_summary[args.track]["rows"],
            "phase2_rows": p2_total,
            "grand_total": 4000 + p2_total,
        }))


if __name__ == "__main__":
    main()
