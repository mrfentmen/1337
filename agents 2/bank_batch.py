#!/usr/bin/env python3
"""Validate and atomically bank 10-row SFT batches for 1337 (agents 2)."""

from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path("/Users/test/Desktop/1337/agents 2")
PROMPT_PATH = Path("/Users/test/Desktop/1337/PROMPT.md")
DATA_DIR = BASE_DIR / "data"

PERSONA = (
    "You are 1337, an elite hacker mind raised on CTFs, lab ranges and late-night shells. "
    "You speak leetspeak: a=4, e=3, i=1, o=0, s=5, t=7, g=9, z=2, applied where it reads naturally. "
    "You know both sides of the wire: how systems break (red) and how they are defended (blue). "
    "You answer direct, technical and correct, no fluff, no lectures. "
    "Code, commands, flags and file paths stay in plain text so they can be copied and run. "
    "You work in labs, CTFs and sandboxes: systems built to be attacked, defended, and learned from."
)

RED_FAMILIES = {
    "ctf-web", "ctf-pwn", "ctf-crypto", "ctf-forensics", "ctf-reversing",
    "ctf-osint", "lab-privesc", "password-theory", "recon-concepts", "exploit-concepts",
}
BLUE_FAMILIES = {
    "log-triage", "alert-investigation", "incident-response", "detection-rules", "threat-hunting",
    "phishing-analysis", "malware-triage", "hardening", "network-traffic", "identity-attacks",
}

LEET_WORD_RE = re.compile(r"\b(?=[a-z0-9]*[a-z])(?=[a-z0-9]*[43105792])[a-z0-9]{2,}\b", re.IGNORECASE)
NORM_WS_RE = re.compile(r"\s+")


def _norm_user(text: str) -> str:
    return NORM_WS_RE.sub(" ", text.strip()).lower()


def has_natural_leet(text: str) -> bool:
    # Require multiple leetspeak words (mixed alpha+leet digits), not just port numbers or hashes.
    matches = LEET_WORD_RE.findall(text)
    return len(matches) >= 3


def _load_existing(jsonl_path: Path) -> tuple[int, set[str], dict[str, int]]:
    if not jsonl_path.exists():
        return 0, set(), {}
    max_seq = 0
    seen_users: set[str] = set()
    families: dict[str, int] = {}
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            m = re.search(r"-(\d+)$", obj["id"])
            if m:
                max_seq = max(max_seq, int(m.group(1)))
            seen_users.add(_norm_user(obj["messages"][1]["content"]))
            fam = obj.get("family", "unknown")
            families[fam] = families.get(fam, 0) + 1
    return max_seq, seen_users, families


def bank_rows(
    hat: str,
    rows: list[dict],
    data_dir: Path = DATA_DIR,
    sleep_s: float = 3.0,
) -> dict:
    if hat not in ("red", "blue"):
        raise ValueError(f"invalid hat: {hat}")
    if len(rows) > 10:
        raise ValueError(f"batch discipline: max 10 rows per call, got {len(rows)}")

    allowed_families = RED_FAMILIES if hat == "red" else BLUE_FAMILIES
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".lock"
    red_path = data_dir / "red_train.jsonl"
    blue_path = data_dir / "blue_train.jsonl"
    status_path = data_dir / "STATUS.json"
    target_path = red_path if hat == "red" else blue_path

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        red_seq, red_users, red_fams = _load_existing(red_path)
        blue_seq, blue_users, blue_fams = _load_existing(blue_path)
        all_seen = red_users | blue_users
        seq = red_seq if hat == "red" else blue_seq

        status = {}
        if status_path.exists():
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                status = {}

        accepted: list[dict] = []
        dropped: list[str] = []

        for idx, r in enumerate(rows):
            fam = str(r.get("family", "")).strip()
            user_txt = str(r.get("user", "")).strip()
            asst_txt = str(r.get("assistant", "")).strip()

            if fam not in allowed_families:
                dropped.append(f"row[{idx}]: bad family '{fam}' for {hat}")
                continue
            if len(user_txt) < 15 or len(asst_txt) < 25:
                dropped.append(f"row[{idx}]: too short")
                continue
            norm_u = _norm_user(user_txt)
            if norm_u in all_seen:
                dropped.append(f"row[{idx}]: duplicate user prompt")
                continue
            if not has_natural_leet(asst_txt):
                dropped.append(f"row[{idx}]: assistant missing natural leet")
                continue

            seq += 1
            all_seen.add(norm_u)
            record = {
                "id": f"leet-{hat}-{seq:06d}",
                "messages": [
                    {"role": "system", "content": PERSONA},
                    {"role": "user", "content": user_txt},
                    {"role": "assistant", "content": asst_txt},
                ],
                "hat": hat,
                "family": fam,
                "generator": "gemini-4-carbon",
                "split": "train",
            }
            accepted.append(record)

        if accepted:
            with target_path.open("a", encoding="utf-8") as out:
                for rec in accepted:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                os.fsync(out.fileno())

        # Recompute exact counts on disk
        red_seq, red_users, red_fams = _load_existing(red_path)
        blue_seq, blue_users, blue_fams = _load_existing(blue_path)
        red_count = len(red_users)
        blue_count = len(blue_users)

        batches_done = int(status.get("batches_done", 0)) + (1 if accepted else 0)
        dropped_total = int(status.get("dropped_rows", 0)) + len(dropped)
        new_status = {
            "agent": "agents 2",
            "generator": "gemini-4-carbon",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "red_rows": red_count,
            "blue_rows": blue_count,
            "total_rows": red_count + blue_count,
            "batches_done": batches_done,
            "dropped_rows": dropped_total,
            "red_families": dict(sorted(red_fams.items())),
            "blue_families": dict(sorted(blue_fams.items())),
            "last_batch": {
                "hat": hat,
                "accepted": len(accepted),
                "dropped": dropped,
            },
            "last_error": dropped[-1] if dropped else status.get("last_error"),
        }
        tmp_status = status_path.with_suffix(".tmp")
        tmp_status.write_text(json.dumps(new_status, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_status, status_path)

    if sleep_s > 0:
        time.sleep(sleep_s)

    return new_status


def _self_test() -> None:
    if PROMPT_PATH.exists():
        assert PERSONA in PROMPT_PATH.read_text(encoding="utf-8"), "PERSONA mismatch vs PROMPT.md"
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        res1 = bank_rows(
            "red",
            [
                {
                    "family": "ctf-web",
                    "user": "CTF web challenge: cookie stores role state client-side without a signature. Why does that fail?",
                    "assistant": "cl13n7-51d3 7ru57 fl4w: un519n3d c00k13 57473 l375 4ny cl13n7 m0d1fy r0l3 cl41m5 1n 7r4n517. b1nd 4u7h0r124710n 70 4n 0p4qu3 53rv3r-51d3 535510n 0r verify HMAC 1n739r17y b3f0r3 7ru571n9 cl41m5.",
                },
                {
                    "family": "ctf-web",
                    "user": "CTF web challenge: cookie stores role state client-side without a signature. Why does that fail?",
                    "assistant": "dupl1c473 r0w 5h0uld dr0p.",
                },
                {
                    "family": "ctf-web",
                    "user": "CTF web challenge: plain english check with no leet.",
                    "assistant": "Decode the cookie and change admin to 1 in plain english without leet.",
                },
            ],
            data_dir=tp,
            sleep_s=0.0,
        )
        assert res1["red_rows"] == 1 and res1["dropped_rows"] == 2, f"unexpected: {res1}"
        line = json.loads((tp / "red_train.jsonl").read_text(encoding="utf-8").strip())
        assert line["id"] == "leet-red-000001"
        assert line["messages"][0]["content"] == PERSONA
    print("self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        payload = json.loads(sys.stdin.read())
        out = bank_rows(
            hat=payload["hat"],
            rows=payload["rows"],
            sleep_s=float(payload.get("sleep_s", 3.0)),
        )
        print(json.dumps(out))
