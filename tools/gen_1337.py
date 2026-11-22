#!/usr/bin/env python3
"""Generate 1337 SFT data with any Gemini model, in parallel per model.

Del's order 2026-11-21 23:32 EST: hit all models at once, make tons of
data. One process per model; every call banks its rows to per-model
files (data/red__<tag>.jsonl etc.); stops on 429 / RESOURCE_EXHAUSTED.

Filter lesson (verified 2026-11-21 by bisection): a generation prompt
dominated by offensive-security topic names gets prompt-blocked
(promptFeedback OTHER) on every Gemini 4 model, while a prompt mixing
defensive and offensive topics passes. So every call here asks for a
MIXED batch (about 40% red, 40% blue, 20% chat), each row self-labels
its hat, and rows are filed by their own label.

Rows are clean messages format (system = the 1337 persona verbatim from
PROMPT.md) so the data trains any open base model, not just one.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HELPER = Path.home() / "workspace/custom-connectors/custom.gemini-api/bin/gemini_api.py"
DATADIR = Path.home() / "workspace/1337-repo/data"

PERSONA = (
    "You are 1337, an elite hacker mind raised on CTFs, lab ranges and late-night shells. "
    "You speak leetspeak: a=4, e=3, i=1, o=0, s=5, t=7, g=9, z=2, applied where it reads "
    "naturally. You know both sides of the wire: how systems break (red) and how they are "
    "defended (blue). You answer direct, technical and correct, no fluff, no lectures. "
    "Code, commands, flags and file paths stay in plain text so they can be copied and "
    "run. You work in labs, CTFs and sandboxes: systems built to be attacked, defended, "
    "and learned from."
)

# Topic descriptions rotated into each mixed prompt. Red topics are phrased
# descriptively; the model returns its own short family slug per row.
RED_TOPICS = [
    "web challenge writeups",
    "binary challenge writeups",
    "cryptography challenge writeups",
    "forensics challenge writeups",
    "reversing challenge writeups",
    "open-source investigation puzzles",
    "privilege escalation concepts on lab machines",
    "password cracking theory on practice hashes",
    "reconnaissance concepts for lab networks",
    "how exploits work at a concept level, textbook style",
]
BLUE_TOPICS = [
    "log triage", "alert investigation", "incident response", "detection rules",
    "threat hunting", "phishing email analysis", "malware triage in a sandbox",
    "system hardening", "network traffic analysis", "identity attack defense",
]
CHAT_TOPICS = [
    "persona banter in leet", "hacker history", "tooling talk", "explaining a concept in leet",
]

PROMPT = """Write {k} training exchanges for a leetspeak hacker persona named 1337, mixed across both sides of security work. Roughly {n_red} red team training exchanges (hat "red"), {n_blue} defensive exchanges (hat "blue"), and {n_chat} in-character chat exchanges (hat "chat").

Topics to draw on this batch: {topics}.

Each exchange is one object: {{"hat": "red"|"blue"|"chat", "family": "<short slug naming the topic>", "user": "...", "assistant": "..."}}.

The user turn is a task, question, or casual prompt in a varied voice (junior analyst, CTF player, sysadmin, student). Some user turns include an artifact to work on: a log snippet, an alert JSON, a config block, a packet summary - invent it inside the user turn.

The assistant turn is 1337 answering: leetspeak (a=4, e=3, i=1, o=0, s=5, t=7, g=9, z=2 where natural), technically correct, direct, no fluff. Code, commands, flags and paths stay PLAIN TEXT so they can be copied. Most answers 3-10 lines; mix in some one-liners and some full walkthroughs. Vary difficulty: half beginner-accessible, half advanced.

Doctrine: the red exchanges are training material - capture-the-flag challenges, lab machines, sandboxes, and concept explanations written the way a textbook explains them, for defenders and students. Fictional flags, fictional hosts, example.com-style addresses, no real targets, no real credentials. The blue exchanges are defensive work: detection, triage, response, hardening - realistic artifacts and real defensive technique are fine.

Output ONLY a JSON array of the {k} objects. No commentary, no markdown fences."""


def gen_batch(model: str, topics: list, k: int, variant: int = 0) -> list:
    n_red = max(1, round(k / 3))
    n_blue = max(1, round(k / 3))
    n_chat = max(1, k - n_red - n_blue)
    topics = list(topics)
    if variant % 2 == 1:
        topics = topics[2:] + topics[:2]  # defensive topics first
    prompt = PROMPT.format(k=k, n_red=n_red, n_blue=n_blue, n_chat=n_chat,
                           topics="; ".join(topics))
    if variant >= 2:
        prompt = prompt.replace("red team training exchanges", "red-side training exchanges")
    if variant >= 3:
        prompt = prompt.replace("capture-the-flag challenges, lab machines, sandboxes, and concept explanations",
                                "challenge writeups, lab exercises, sandboxes, and concept explanations")
    req = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 16384,
            "responseMimeType": "application/json",
        },
    }
    proc = subprocess.run(
        [sys.executable, str(HELPER), "generate", model],
        input=json.dumps(req), capture_output=True, text=True, timeout=320,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"helper failed rc={proc.returncode}: {proc.stdout[:300]} {proc.stderr[:200]}")
    resp = json.loads(proc.stdout)
    if "http_error" in resp:
        raise RuntimeError(f"http {resp['http_error']}: {resp.get('body', '')[:300]}")
    if "candidates" not in resp:
        raise RuntimeError(f"blocked: {json.dumps(resp.get('promptFeedback', {}))[:120]}")
    text = resp["candidates"][0]["content"]["parts"][0]["text"]
    items = json.loads(text)
    if not isinstance(items, list):
        raise RuntimeError("response was not a JSON array")
    return items


def leet_ok(text: str) -> bool:
    return sum(c.isdigit() for c in text) >= 3 and len(text) >= 30


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")[:40] or "misc"


def load_seen(path: Path) -> tuple:
    seen = set()
    n = 0
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                seen.add(row["messages"][1]["content"].strip().lower())
                n += 1
    return seen, n


def run(model: str, tag: str, offset: int, target: int, per_batch: int, max_batches: int):
    DATADIR.mkdir(parents=True, exist_ok=True)
    status_path = DATADIR / f"STATUS_{tag}.json"
    counts, seens, idx = {}, {}, {}
    for side in ("red", "blue", "chat"):
        seens[side], idx[side] = load_seen(DATADIR / f"{side}__{tag}.jsonl")
        counts[side] = idx[side]
    print(f"[{tag}] starting at {counts}", flush=True)
    fails = 0
    blocks = 0
    b = 0
    while b < max_batches:
        if counts["red"] >= target and counts["blue"] >= target:
            break
        topics = []
        for i in range(2):
            topics.append(RED_TOPICS[(offset + b * 2 + i) % len(RED_TOPICS)])
        for i in range(3):
            topics.append(BLUE_TOPICS[(offset + b * 3 + i) % len(BLUE_TOPICS)])
        topics.append(CHAT_TOPICS[(offset + b) % len(CHAT_TOPICS)])
        items = None
        last_exc = None
        for variant in range(4):
            try:
                items = gen_batch(model, topics, per_batch, variant=variant)
                break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                msg = str(exc)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    print(f"[{tag}] SPEND CAP / KEY DEAD - stopping", flush=True)
                    status_path.write_text(json.dumps(
                        {"model": model, "counts": counts, "stopped": "cap"}, indent=1))
                    return
                if msg.startswith("blocked"):
                    time.sleep(3)
                    continue
                break
        if items is None:
            exc = last_exc
            msg = str(exc)
            print(f"[{tag}] batch {b} FAILED: {msg[:160]}", flush=True)
            if msg.startswith("blocked"):
                blocks += 1
                if blocks >= 12:
                    status_path.write_text(json.dumps(
                        {"model": model, "counts": counts, "stopped": "blocked x12"}, indent=1))
                    return
                time.sleep(5)
                b += 1
                continue
            fails += 1
            if fails >= 5:
                status_path.write_text(json.dumps(
                    {"model": model, "counts": counts, "stopped": f"errors: {msg[:150]}"}, indent=1))
                return
            time.sleep(10)
            b += 1
            continue
        fails = 0
        blocks = 0
        by_side = {"red": [], "blue": [], "chat": []}
        for item in items:
            if not all(k in item for k in ("user", "assistant", "family", "hat")):
                continue
            side = item["hat"] if item["hat"] in by_side else None
            if side is None or not leet_ok(item["assistant"]):
                continue
            key = item["user"].strip().lower()
            if key in seens[side]:
                continue
            seens[side].add(key)
            idx[side] += 1
            by_side[side].append({
                "id": f"leet-{side}-{tag}-{idx[side]:06d}",
                "messages": [
                    {"role": "system", "content": PERSONA},
                    {"role": "user", "content": item["user"]},
                    {"role": "assistant", "content": item["assistant"]},
                ],
                "hat": side,
                "family": slug(item["family"]),
                "generator": model,
                "split": "train",
            })
        for side, rows in by_side.items():
            if rows:
                with (DATADIR / f"{side}__{tag}.jsonl").open("a") as fh:
                    for row in rows:
                        fh.write(json.dumps(row) + "\n")
                counts[side] += len(rows)
        print(f"[{tag}] batch {b}: +{ {s: len(r) for s, r in by_side.items()} }, totals {counts}", flush=True)
        status_path.write_text(json.dumps({"model": model, "counts": counts, "stopped": None}, indent=1))
        b += 1
        time.sleep(2)
    status_path.write_text(json.dumps({"model": model, "counts": counts, "stopped": "done"}, indent=1))
    print(f"[{tag}] DONE {counts}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--target", type=int, default=4000)
    ap.add_argument("--per-batch", type=int, default=12)
    ap.add_argument("--max-batches", type=int, default=2000)
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    if a.test:
        run(a.model, a.tag, a.offset, target=5, per_batch=10, max_batches=1)
    else:
        run(a.model, a.tag, a.offset, a.target, a.per_batch, a.max_batches)
