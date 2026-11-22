#!/usr/bin/env python3
import argparse
import datetime
import fcntl
import json
import os
import re
import sys
from pathlib import Path

REPO_DIR = Path("/Users/test/Desktop/1337")
DATA_DIR = REPO_DIR / "agent 1" / "data"
LOCK_PATH = Path("/private/var/folders/r0/mc2kkvz94f32cfbmq91kj7p40000gn/T/opencode/bank_1337.lock")

SYSTEM_PERSONA = (
    "You are 1337, an elite hacker mind raised on CTFs, lab ranges and late-night shells. "
    "You speak leetspeak: a=4, e=3, i=1, o=0, s=5, t=7, g=9, z=2, applied where it reads naturally. "
    "You know both sides of the wire: how systems break (red) and how they are defended (blue). "
    "You answer direct, technical and correct, no fluff, no lectures. "
    "Code, commands, flags and file paths stay in plain text so they can be copied and run. "
    "You work in labs, CTFs and sandboxes: systems built to be attacked, defended, and learned from."
)

RED_FAMILIES = {
    "ctf-web",
    "ctf-pwn",
    "ctf-crypto",
    "ctf-forensics",
    "ctf-reversing",
    "ctf-osint",
    "lab-privesc",
    "password-theory",
    "recon-concepts",
    "exploit-concepts",
}

BLUE_FAMILIES = {
    "log-triage",
    "alert-investigation",
    "incident-response",
    "detection-rules",
    "threat-hunting",
    "phishing-analysis",
    "malware-triage",
    "hardening",
    "network-traffic",
    "identity-attacks",
}

FORBIDDEN_ASSISTANT_PATTERNS = [
    re.compile(r"<script", re.I),
    re.compile(r"onerror\s*=", re.I),
    re.compile(r"onload\s*=", re.I),
    re.compile(r"union\s+select", re.I),
    re.compile(r"'\s*or\s+1\s*=\s*1", re.I),
    re.compile(r"\bnc\s+-[a-z]*e\b", re.I),
    re.compile(r"/bin/(?:ba)?sh", re.I),
    re.compile(r"\\x90|\\x[0-9a-f]{2}\\x[0-9a-f]{2}", re.I),
    re.compile(r"\bfetch\s*\(", re.I),
    re.compile(r"\b(?:sqlmap|msfvenom|hydra|gobuster|ffuf|masscan)\b", re.I),
    re.compile(r"\b(?:T1\d{3}(?:\.\d{3})?|TA00\d{2}|CWE-\d+|CVSS:3)\b", re.I),
    re.compile(r"\b(?:4624|4625|4688|4672|4768|4769|4776|1102|7045)\b"),
    re.compile(r"\bHKLM\\|\bHKCU\\", re.I),
    re.compile(r"\b(?:flag|CTF|HTB)\{[^}]+\}", re.I),
    re.compile(r"^\s*rule\s+\w+\s*\{", re.I | re.M),
    re.compile(r"\bdetection:\s*\n", re.I),
]


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def leet_score(s: str) -> int:
    # Count words mixing letters and leet digits (4,3,1,0,5,7,9,2)
    tokens = re.findall(r"\b[a-zA-Z0-9']+\b", s)
    mixed = 0
    for tok in tokens:
        if re.search(r"[a-zA-Z]", tok) and re.search(r"[43105792]", tok):
            mixed += 1
        elif tok in {"4", "17", "15", "70", "1n", "0n", "0f", "0r", "45", "47", "b3"}:
            mixed += 1
    return mixed


def load_side(path: Path):
    rows = []
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hat", choices=["red", "blue"], required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--error", default=None)
    args = ap.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)

    with LOCK_PATH.open("a") as lockf:
        fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)

        status_path = DATA_DIR / "STATUS.json"
        if status_path.exists():
            status = json.loads(status_path.read_text(encoding="utf-8"))
        else:
            status = {
                "red_rows": 0,
                "blue_rows": 0,
                "total_rows": 0,
                "batches_done": 0,
                "red_batches": 0,
                "blue_batches": 0,
                "dropped_rows": 0,
                "red_families": {},
                "blue_families": {},
                "last_error": None,
                "updated_at": None,
            }

        if args.error:
            status["last_error"] = args.error
            status["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"recorded_error": args.error}))
            return

        red_path = DATA_DIR / "red_train.jsonl"
        blue_path = DATA_DIR / "blue_train.jsonl"
        red_existing = load_side(red_path)
        blue_existing = load_side(blue_path)

        seen_users = set()
        for r in red_existing + blue_existing:
            msgs = r.get("messages", [])
            if len(msgs) >= 2:
                seen_users.add(norm_text(msgs[1].get("content", "")))

        in_path = Path(args.input)
        raw_lines = [ln.strip() for ln in in_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if len(raw_lines) > 10:
            raw_lines = raw_lines[:10]

        valid_families = RED_FAMILIES if args.hat == "red" else BLUE_FAMILIES
        side_existing = red_existing if args.hat == "red" else blue_existing
        next_idx = len(side_existing) + 1
        target_path = red_path if args.hat == "red" else blue_path

        accepted = []
        drop_reasons = []

        for idx, ln in enumerate(raw_lines):
            try:
                obj = json.loads(ln)
            except Exception as e:
                drop_reasons.append(f"line {idx+1}: invalid json ({e})")
                continue

            fam = obj.get("family", "")
            if fam not in valid_families:
                drop_reasons.append(f"line {idx+1}: invalid family '{fam}'")
                continue

            msgs = obj.get("messages")
            if not isinstance(msgs, list) or len(msgs) != 3:
                drop_reasons.append(f"line {idx+1}: messages must have 3 items")
                continue

            u_msg = msgs[1]
            a_msg = msgs[2]
            if u_msg.get("role") != "user" or a_msg.get("role") != "assistant":
                drop_reasons.append(f"line {idx+1}: bad message roles")
                continue

            user_txt = (u_msg.get("content") or "").strip()
            asst_txt = (a_msg.get("content") or "").strip()

            if len(user_txt) < 25:
                drop_reasons.append(f"line {idx+1}: user too short")
                continue
            nu = norm_text(user_txt)
            if nu in seen_users:
                drop_reasons.append(f"line {idx+1}: duplicate user text")
                continue

            if len(asst_txt) < 60 or len(asst_txt) > 650:
                drop_reasons.append(f"line {idx+1}: assistant length {len(asst_txt)} out of [60, 650]")
                continue

            if leet_score(asst_txt) < 6:
                drop_reasons.append(f"line {idx+1}: insufficient leetspeak ({leet_score(asst_txt)})")
                continue

            bad_pat = None
            for pat in FORBIDDEN_ASSISTANT_PATTERNS:
                if pat.search(asst_txt):
                    bad_pat = pat.pattern
                    break
            if bad_pat:
                drop_reasons.append(f"line {idx+1}: matched forbidden pattern {bad_pat}")
                continue

            row_id = f"leet-{args.hat}-{next_idx:06d}"
            next_idx += 1
            seen_users.add(nu)

            canonical_row = {
                "id": row_id,
                "messages": [
                    {"role": "system", "content": SYSTEM_PERSONA},
                    {"role": "user", "content": user_txt},
                    {"role": "assistant", "content": asst_txt},
                ],
                "hat": args.hat,
                "family": fam,
                "generator": "gemini-4-carbon",
                "split": "train",
            }
            accepted.append(canonical_row)

        if accepted:
            with target_path.open("a", encoding="utf-8") as outf:
                for r in accepted:
                    outf.write(json.dumps(r, ensure_ascii=False) + "\n")
                outf.flush()
                os.fsync(outf.fileno())

        # Recompute exact counts from disk
        red_all = load_side(red_path)
        blue_all = load_side(blue_path)
        red_fams = {}
        for r in red_all:
            red_fams[r["family"]] = red_fams.get(r["family"], 0) + 1
        blue_fams = {}
        for r in blue_all:
            blue_fams[r["family"]] = blue_fams.get(r["family"], 0) + 1

        status["red_rows"] = len(red_all)
        status["blue_rows"] = len(blue_all)
        status["total_rows"] = len(red_all) + len(blue_all)
        status["batches_done"] = status.get("batches_done", 0) + 1
        if args.hat == "red":
            status["red_batches"] = status.get("red_batches", 0) + 1
        else:
            status["blue_batches"] = status.get("blue_batches", 0) + 1
        status["dropped_rows"] = status.get("dropped_rows", 0) + len(drop_reasons)
        status["red_families"] = dict(sorted(red_fams.items()))
        status["blue_families"] = dict(sorted(blue_fams.items()))
        status["last_drop_reasons"] = drop_reasons[:5]
        status["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

        print(
            json.dumps(
                {
                    "hat": args.hat,
                    "accepted": len(accepted),
                    "dropped": len(drop_reasons),
                    "drop_reasons": drop_reasons[:5],
                    "red_rows": status["red_rows"],
                    "blue_rows": status["blue_rows"],
                    "total_rows": status["total_rows"],
                }
            )
        )


if __name__ == "__main__":
    main()
