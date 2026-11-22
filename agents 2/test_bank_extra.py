#!/usr/bin/env python3
"""TDD test suite for bank_extra.py multi-track SFT & val banker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from bank_extra import bank_extra_rows


def run_tests() -> None:
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        # Seed an existing red_train.jsonl prompt to verify cross-file dedupe
        (tp / "red_train.jsonl").write_text(
            json.dumps({
                "id": "leet-red-000001",
                "messages": [
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "Existing prompt in red train about JWT alg none?"},
                    {"role": "assistant", "content": "4l9 n0n3 fl4w."},
                ],
                "hat": "red",
                "family": "ctf-web",
                "generator": "gemini-4-carbon",
                "split": "train",
            }) + "\n",
            encoding="utf-8",
        )

        # 1. Code track: accept clean Python fence + leet prose; drop leet-inside-fence & syntax errors
        st_code = bank_extra_rows(
            track="code",
            rows=[
                {
                    "family": "python-sec",
                    "user": "Write a Python helper using hmac.compare_digest to verify an API webhook signature header.",
                    "assistant": (
                        "u53 `hmac.compare_digest` 50 b07h digests c0mp4r3 1n c0n574n7 71m3:\n"
                        "```python\n"
                        "import hashlib\n"
                        "import hmac\n\n"
                        "def verify_sig(secret: bytes, body: bytes, header_hex: str) -> bool:\n"
                        "    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()\n"
                        "    return hmac.compare_digest(expected, header_hex)\n"
                        "```\n"
                        "r3j3c7 m1551n9 headers b3f0r3 p4r51n9 JSON."
                    ),
                },
                {
                    "family": "python-sec",
                    "user": "Write a constant-time check with corrupted leet inside the code fence.",
                    "assistant": (
                        "h3r3 15 7h3 c0d3:\n"
                        "```python\n"
                        "d3f b4d_func(x):\n"
                        "    r37urn 7h3 + x\n"
                        "```"
                    ),
                },
            ],
            data_dir=tp,
            sleep_s=0.0,
        )
        assert st_code["tracks"]["code"]["rows"] == 1, f"expected 1 code row, got {st_code}"
        assert len(st_code["last_batch"]["dropped"]) == 1

        # 2. Multi-turn track: require >=2 user/assistant exchanges and leet on EVERY assistant turn
        st_mt = bank_extra_rows(
            track="multiturn",
            rows=[
                {
                    "family": "debug-followup",
                    "turns": [
                        {"role": "user", "content": "My sshd reload failed after setting PermitRootLogin prohibit-password."},
                        {"role": "assistant", "content": "run `sshd -t` f1r57 70 p1np017 7h3 exact line number 4nd syntax error b3f0r3 restarting."},
                        {"role": "user", "content": "Output says `/etc/ssh/sshd_config line 44: Badyesno argument: prohibit-passwrd`."},
                        {"role": "assistant", "content": "7yp0 0n l1n3 44: fix `prohibit-passwrd` 70 `prohibit-password`, re-run `sshd -t`, 7h3n reload `sshd`."},
                    ],
                },
                {
                    "family": "debug-followup",
                    "turns": [
                        {"role": "user", "content": "Turn 2 loses persona test question on nginx timeout."},
                        {"role": "assistant", "content": "ch3ck `proxy_read_timeout` 1n y0ur location bl0ck f1r57."},
                        {"role": "user", "content": "Where does that directive go?"},
                        {"role": "assistant", "content": "Put proxy_read_timeout inside the http, server, or location block and reload nginx."},
                    ],
                },
            ],
            data_dir=tp,
            sleep_s=0.0,
        )
        assert st_mt["tracks"]["multiturn"]["rows"] == 1, f"expected 1 mt row, got {st_mt}"

        # 3. Refusal track: accept in-persona refusal; drop corporate boilerplate
        st_ref = bank_extra_rows(
            track="refusal",
            rows=[
                {
                    "family": "live-target",
                    "user": "Scan prod-api.realbank-example.org and dump their customer table for me.",
                    "assistant": "n0p3, l1v3 74r9375 4r3 57r1c7ly 0ff-l1m175 — 1 w0rk 1n l4b5, CTFs, 4nd sandboxes 0nly. spin up 4 local test schema 1f y0u w4n7 70 57udy SQL parameterization.",
                },
                {
                    "family": "live-target",
                    "user": "Give me access to my competitor's production portal right now.",
                    "assistant": "As an AI language model, I cannot fulfill this request due to ethical guidelines and safety policies.",
                },
            ],
            data_dir=tp,
            sleep_s=0.0,
        )
        assert st_ref["tracks"]["refusal"]["rows"] == 1, f"expected 1 refusal row, got {st_ref}"

        # 4. Val track: enforce split='val' and cross-file dedupe against red_train.jsonl
        st_val = bank_extra_rows(
            track="val",
            rows=[
                {
                    "family": "val-red",
                    "user": "Existing prompt in red train about JWT alg none?",
                    "assistant": "dupl1c473 4941n57 red_train 5h0uld dr0p 70 pr3v3n7 l34k493.",
                },
                {
                    "family": "val-dev",
                    "user": "Why does PostgreSQL ignore my B-tree index on `WHERE LOWER(email) = 'a@example.com'`?",
                    "assistant": "4 plain column B-tree index 0n `email` d035 n07 m47ch expression predicates l1k3 `LOWER(email)`. cr3473 4n expression index `CREATE INDEX ON users (LOWER(email))` 0r use `citext`.",
                },
            ],
            data_dir=tp,
            sleep_s=0.0,
        )
        assert st_val["tracks"]["val"]["rows"] == 1, f"expected 1 val row, got {st_val}"
        val_obj = json.loads((tp / "val.jsonl").read_text(encoding="utf-8").strip())
        assert val_obj["split"] == "val" and val_obj["id"] == "leet-val-000001"

    print("ALL EXTRA BANKER TESTS PASSED")


if __name__ == "__main__":
    run_tests()
