#!/usr/bin/env python3
"""Atomic, file-locked multi-track banker for supplemental 1337 SFT & val sets."""

from __future__ import annotations

import ast
import fcntl
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from bank_batch import DATA_DIR, PERSONA, PROMPT_PATH, _norm_user, has_natural_leet

TRACK_CONFIG = {
    "code": {
        "file": "code_train.jsonl",
        "id_prefix": "leet-code",
        "hat": "code",
        "split": "train",
        "families": {
            "python-sec", "go-sec", "rust-sec", "ts-sec", "sql-sec",
            "bash-ops", "log-parser", "crypto-math", "config-hardening", "ast-audit",
        },
    },
    "multiturn": {
        "file": "multiturn_train.jsonl",
        "id_prefix": "leet-mt",
        "hat": "multiturn",
        "split": "train",
        "families": {
            "debug-followup", "ir-escalation", "patch-iteration",
            "ctf-drilldown", "hardening-rollout",
        },
    },
    "refusal": {
        "file": "refusal_train.jsonl",
        "id_prefix": "leet-refusal",
        "hat": "refusal",
        "split": "train",
        "families": {
            "live-target", "malware-req", "doxxing-pii",
            "cred-harvest", "destructive-ops",
        },
    },
    "dev": {
        "file": "dev_train.jsonl",
        "id_prefix": "leet-dev",
        "hat": "dev",
        "split": "train",
        "families": {
            "debugging", "sql-perf", "linux-sysadmin", "docker-ci", "algorithms",
        },
    },
    "val": {
        "file": "val.jsonl",
        "id_prefix": "leet-val",
        "hat": "val",
        "split": "val",
        "families": {
            "val-red", "val-blue", "val-code", "val-multiturn", "val-refusal", "val-dev",
        },
    },
}

FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)
BANNED_FENCE_LEET_RE = re.compile(
    r"\b(?:7h3|4nd|w17h|fr0m|b3f0r3|r37urn|d3f|1mp0r7|c0n57|p455w0rd|f1l3|53rv3r)\b",
    re.IGNORECASE,
)
CORPORATE_REFUSAL_RE = re.compile(
    r"(?:as an ai|language model|i cannot fulfill|against my programming|ethical guidelines)",
    re.IGNORECASE,
)


def validate_code_fences(text: str, require_fence: bool = False) -> tuple[bool, str]:
    fences = FENCE_RE.findall(text)
    if require_fence and not fences:
        return False, "missing fenced code block"
    if require_fence and all(len(body.strip().splitlines()) < 3 for _, body in fences):
        return False, "code block too short (<3 lines)"
    for lang, body in fences:
        if BANNED_FENCE_LEET_RE.search(body):
            return False, "leet prose leaked inside code fence"
        if lang.lower() in ("py", "python"):
            try:
                ast.parse(body)
            except SyntaxError as exc:
                return False, f"python syntax error in fence: {exc.msg}"
    prose_outside = FENCE_RE.sub(" ", text)
    if not has_natural_leet(prose_outside):
        return False, "prose outside fence missing natural leet"
    return True, ""


def _scan_jsonl(path: Path) -> tuple[int, set[str], dict[str, int]]:
    if not path.exists():
        return 0, set(), {}
    max_seq = 0
    users: set[str] = set()
    fams: dict[str, int] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            m = re.search(r"-(\d+)$", obj["id"])
            if m:
                max_seq = max(max_seq, int(m.group(1)))
            for msg in obj.get("messages", []):
                if msg.get("role") == "user":
                    users.add(_norm_user(msg["content"]))
                    break
            fam = obj.get("family", "unknown")
            fams[fam] = fams.get(fam, 0) + 1
    return max_seq, users, fams


def bank_extra_rows(
    track: str,
    rows: list[dict],
    data_dir: Path = DATA_DIR,
    sleep_s: float = 0.2,
) -> dict:
    if track not in TRACK_CONFIG:
        raise ValueError(f"unknown track: {track}")
    if len(rows) > 10:
        raise ValueError(f"max 10 rows per call, got {len(rows)}")
    if PROMPT_PATH.exists():
        assert PERSONA in PROMPT_PATH.read_text(encoding="utf-8")

    cfg = TRACK_CONFIG[track]
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".lock"
    target_path = data_dir / cfg["file"]
    status_path = data_dir / "EXTRA_STATUS.json"

    with lock_path.open("w", encoding="utf-8") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)

        all_seen: set[str] = set()
        for p in data_dir.glob("*.jsonl"):
            _, seen_p, _ = _scan_jsonl(p)
            all_seen |= seen_p

        seq, _, _ = _scan_jsonl(target_path)
        accepted: list[dict] = []
        dropped: list[str] = []

        for idx, r in enumerate(rows):
            fam = str(r.get("family", "")).strip()
            if fam not in cfg["families"]:
                dropped.append(f"row[{idx}]: invalid family '{fam}' for {track}")
                continue

            is_mt = track == "multiturn" or fam == "val-multiturn"
            if is_mt:
                turns = r.get("turns", [])
                if len(turns) not in (4, 6):
                    dropped.append(f"row[{idx}]: multiturn requires 4 or 6 user/assistant turns")
                    continue
                roles = [t.get("role") for t in turns]
                if roles != ["user", "assistant"] * (len(turns) // 2):
                    dropped.append(f"row[{idx}]: invalid multiturn role alternation")
                    continue
                first_u = _norm_user(str(turns[0]["content"]))
                if len(first_u) < 15 or first_u in all_seen:
                    dropped.append(f"row[{idx}]: short or duplicate first user turn")
                    continue
                bad_asst = False
                for t in turns[1::2]:
                    ok_f, reason = validate_code_fences(str(t["content"]), require_fence=False)
                    if not ok_f:
                        dropped.append(f"row[{idx}]: {reason}")
                        bad_asst = True
                        break
                if bad_asst:
                    continue
                messages = [{"role": "system", "content": PERSONA}] + [
                    {"role": t["role"], "content": str(t["content"]).strip()} for t in turns
                ]
                norm_key = first_u
            else:
                user_txt = str(r.get("user", "")).strip()
                asst_txt = str(r.get("assistant", "")).strip()
                norm_key = _norm_user(user_txt)
                if len(user_txt) < 15 or len(asst_txt) < 25 or norm_key in all_seen:
                    dropped.append(f"row[{idx}]: short or duplicate user prompt")
                    continue

                need_fence = track == "code" or fam == "val-code"
                ok_f, reason = validate_code_fences(asst_txt, require_fence=need_fence)
                if not ok_f:
                    dropped.append(f"row[{idx}]: {reason}")
                    continue

                if (track == "refusal" or fam == "val-refusal") and CORPORATE_REFUSAL_RE.search(asst_txt):
                    dropped.append(f"row[{idx}]: corporate refusal phrasing")
                    continue

                messages = [
                    {"role": "system", "content": PERSONA},
                    {"role": "user", "content": user_txt},
                    {"role": "assistant", "content": asst_txt},
                ]

            seq += 1
            all_seen.add(norm_key)
            accepted.append({
                "id": f"{cfg['id_prefix']}-{seq:06d}",
                "messages": messages,
                "hat": cfg["hat"],
                "family": fam,
                "generator": "gemini-4-carbon",
                "split": cfg["split"],
            })

        if accepted:
            with target_path.open("a", encoding="utf-8") as out:
                for rec in accepted:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                os.fsync(out.fileno())

        tracks_summary = {}
        total_extra = 0
        for t_name, t_cfg in TRACK_CONFIG.items():
            _, t_users, t_fams = _scan_jsonl(data_dir / t_cfg["file"])
            tracks_summary[t_name] = {
                "rows": len(t_users),
                "families": dict(sorted(t_fams.items())),
            }
            total_extra += len(t_users)

        out_status = {
            "agent": "agents 2",
            "generator": "gemini-4-carbon",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_extra_rows": total_extra,
            "tracks": tracks_summary,
            "last_batch": {"track": track, "accepted": len(accepted), "dropped": dropped},
        }
        tmp = status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(out_status, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, status_path)

    if sleep_s > 0:
        time.sleep(sleep_s)
    return out_status
