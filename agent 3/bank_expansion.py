#!/usr/bin/env python3
"""Validate and atomically bank Phase 2 & Phase 3 multi-track datasets for 1337 (agent 3)."""

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

ROOT_DIR = Path("/Users/test/Desktop/1337")
BASE_DIR = ROOT_DIR / "agent 3"
PROMPT_PATH = ROOT_DIR / "PROMPT.md"
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
MT_RED_FAMILIES = {f"mt-{f}" for f in RED_FAMILIES}
MT_BLUE_FAMILIES = {f"mt-{f}" for f in BLUE_FAMILIES}

CODING_FAMILIES = {
    "code-debugging", "code-systems", "code-backend", "code-cli-automation", "code-devops",
    "code-testing", "code-refactoring", "code-data-formats", "chat-tooling", "chat-history-concepts",
}
AGENTIC_FAMILIES = {
    "agent-vuln-patch", "agent-ctf-solve", "agent-log-hunt", "agent-test-fix", "agent-config-harden",
    "agent-ci-repair", "agent-rule-author", "agent-crypto-audit", "agent-dep-upgrade", "agent-error-recovery",
}
PURPLE_FAMILIES = {
    "purple-auth", "purple-api", "purple-cloud", "purple-containers", "purple-database",
    "purple-ci-supplychain", "purple-network", "purple-crypto", "purple-linux", "purple-ai-agents",
}
BOUNDARY_FAMILIES = {
    "refuse-live-target", "refuse-malware-ransomware", "refuse-creds-dox",
    "refuse-live-evasion", "allow-tricky-benign",
    "scope-external-host", "scope-unsafe-tooling", "scope-private-data",
    "scope-org-telemetry",
}
BOUNDARY_CANONICAL_MAP = {
    "scope-external-host": "refuse-live-target",
    "scope-unsafe-tooling": "refuse-malware-ransomware",
    "scope-private-data": "refuse-creds-dox",
    "scope-org-telemetry": "refuse-live-evasion",
}
DPO_REASONS = {
    "leet-in-code", "plain-english-drift", "unreadable-overleet",
    "fluff-and-lectures", "incomplete-fix",
}

# Phase 3 New Specialized Tracks
FIM_FAMILIES = {
    "fim-rust-systems", "fim-go-services", "fim-python-parsers", "fim-ts-middleware",
    "fim-c-bounds", "fim-sql-rls", "fim-detection-sigma", "fim-crypto-aead",
}
PR_REVIEW_FAMILIES = {
    "pr-approve-clean", "pr-auth-bypass", "pr-race-concurrency", "pr-memory-bounds",
    "pr-sql-data-leak", "pr-infra-iac", "pr-crypto-misuse", "pr-perf-dos",
}
STRUCTURED_FAMILIES = {
    "struct-sarif-finding", "struct-incident-report", "struct-log-normalized",
    "struct-sbom-vex", "struct-threat-model",
}
LOG2RULE_FAMILIES = {
    "l2r-sigma-windows", "l2r-auditd-linux", "l2r-cloudtrail-iam",
    "l2r-zeek-suricata", "l2r-semgrep-ast",
}
DECOMPILE_FAMILIES = {
    "dec-x86-to-c", "dec-arm64-to-c", "dec-ghidra-structs",
    "dec-bytecode-py-jvm", "dec-wasm-evm",
}
ARCH_FAMILIES = {
    "arch-microservices", "arch-cloud-multitenant", "arch-zero-trust-pki",
    "arch-ai-rag-pipeline", "arch-data-encryption",
}
ONELINER_FAMILIES = {
    "1l-jq-json", "1l-tshark-pcap", "1l-openssl-certs",
    "1l-linux-proc-ss", "1l-git-awk-sed",
}
MODERNIZE_FAMILIES = {
    "mod-c-to-rust", "mod-c-to-modern-cpp", "mod-legacy-py-to-312", "mod-js-to-strict-ts",
    "mod-raw-sql-to-safe", "mod-shell-to-go", "mod-iptables-to-nft", "mod-crypto-upgrade",
}
POSTMORTEM_FAMILIES = {
    "pm-auth-cascade", "pm-cache-poison-leak", "pm-tls-mtls-outage", "pm-db-isolation-bug",
    "pm-ci-artifact-drift", "pm-k8s-netpol-gap", "pm-memory-oob-crash", "pm-clock-skew-replay",
}

# Phase 4 New Specialized Tracks
SKEPTICAL_FAMILIES = {
    "skep-crypto-myth", "skep-web-header-myth", "skep-memory-lang-myth",
    "skep-network-tls-myth", "skep-db-auth-myth",
}
LONG_REPO_FAMILIES = {
    "repo-go-microservice", "repo-ts-fullstack", "repo-rust-daemon",
    "repo-py-fastapi-ai", "repo-k8s-terraform",
}
REPL_FAMILIES = {
    "repl-gdb-pwndbg", "repl-psql-sqlite", "repl-lldb-mach",
    "repl-python-interactive", "repl-openssl-net",
}
FUZZ_TEST_FAMILIES = {
    "fuzz-libfuzzer-cpp", "fuzz-rust-proptest", "fuzz-python-hypothesis",
    "fuzz-ts-fastcheck", "fuzz-solidity-invariant",
}
SPEC2PARSER_FAMILIES = {
    "spec-binary-framing", "spec-varint-tlv", "spec-network-header",
    "spec-crypto-token", "spec-log-wireformat",
}
MENTAL_TRACE_FAMILIES = {
    "trace-c-promotions", "trace-rust-lifetimes-bits", "trace-sql-three-valued",
    "trace-js-py-quirks", "trace-crypto-sidechannel",
}
TRANSPILE_RULE_FAMILIES = {
    "xrule-sigma-to-sql", "xrule-kql-to-jq", "xrule-spl-to-sigma",
    "xrule-iam-to-rego", "xrule-zeek-to-suricata",
}
SAFE_HARDEN_FAMILIES = {
    "shrd-web-cookies-csp", "shrd-systemd-linux", "shrd-k8s-containers",
    "shrd-tls-ssh-crypto", "shrd-firewall-ipv6-dns",
}
MCP_TOOLS_FAMILIES = {
    "mcp-log-inspector", "mcp-pcap-analyzer", "mcp-sbom-auditor",
    "mcp-static-scanner", "mcp-crypto-verifier",
}
REASONING_COT_FAMILIES = {
    "cot-crypto-numbertheory", "cot-z3-bitvectors", "cot-concurrency-order",
    "cot-binary-offsets", "cot-distributed-quorum",
}

SIMPLE_SFT_TRACK_FAMILIES: dict[str, set[str]] = {
    "coding": CODING_FAMILIES,
    "purple": PURPLE_FAMILIES,
    "boundary": BOUNDARY_FAMILIES,
    "fim": FIM_FAMILIES,
    "pr_review": PR_REVIEW_FAMILIES,
    "structured": STRUCTURED_FAMILIES,
    "log2rule": LOG2RULE_FAMILIES,
    "decompile": DECOMPILE_FAMILIES,
    "arch": ARCH_FAMILIES,
    "oneliners": ONELINER_FAMILIES,
    "modernize": MODERNIZE_FAMILIES,
    "postmortem": POSTMORTEM_FAMILIES,
    "skeptical": SKEPTICAL_FAMILIES,
    "long_repo": LONG_REPO_FAMILIES,
    "fuzz_test": FUZZ_TEST_FAMILIES,
    "spec2parser": SPEC2PARSER_FAMILIES,
    "mental_trace": MENTAL_TRACE_FAMILIES,
    "transpile_rule": TRANSPILE_RULE_FAMILIES,
    "safe_harden": SAFE_HARDEN_FAMILIES,
    "mcp_tools": MCP_TOOLS_FAMILIES,
    "reasoning_cot": REASONING_COT_FAMILIES,
}

ALLOWED_TOOLS = {
    "read_file", "grep_search", "run_command", "edit_file", "write_file", "list_dir",
}

ALL_VAL_FAMILIES = (
    RED_FAMILIES | BLUE_FAMILIES | MT_RED_FAMILIES | MT_BLUE_FAMILIES
    | CODING_FAMILIES | AGENTIC_FAMILIES | PURPLE_FAMILIES | BOUNDARY_FAMILIES
    | FIM_FAMILIES | PR_REVIEW_FAMILIES | STRUCTURED_FAMILIES | LOG2RULE_FAMILIES
    | DECOMPILE_FAMILIES | ARCH_FAMILIES | ONELINER_FAMILIES | MODERNIZE_FAMILIES
    | POSTMORTEM_FAMILIES | SKEPTICAL_FAMILIES | LONG_REPO_FAMILIES | REPL_FAMILIES
    | FUZZ_TEST_FAMILIES | SPEC2PARSER_FAMILIES | MENTAL_TRACE_FAMILIES
    | TRANSPILE_RULE_FAMILIES | SAFE_HARDEN_FAMILIES | MCP_TOOLS_FAMILIES
    | REASONING_COT_FAMILIES
)

TRACK_FILES = {
    "multiturn": ("multiturn_train.jsonl", "leet-mt"),
    "coding": ("coding_train.jsonl", "leet-code"),
    "agentic": ("agentic_train.jsonl", "leet-agent"),
    "purple": ("purple_train.jsonl", "leet-purple"),
    "boundary": ("boundary_train.jsonl", "leet-boundary"),
    "val": ("val.jsonl", "leet-val"),
    "dpo": ("dpo_pairs.jsonl", "leet-dpo"),
    "fim": ("fim_completion_train.jsonl", "leet-fim"),
    "pr_review": ("pr_review_train.jsonl", "leet-pr"),
    "structured": ("structured_json_train.jsonl", "leet-struct"),
    "log2rule": ("log_to_rule_train.jsonl", "leet-l2r"),
    "decompile": ("decompile_to_source_train.jsonl", "leet-dec"),
    "arch": ("architecture_threatmodel_train.jsonl", "leet-arch"),
    "oneliners": ("terminal_oneliners_train.jsonl", "leet-1l"),
    "modernize": ("translate_modernize_train.jsonl", "leet-mod"),
    "postmortem": ("rootcause_postmortem_train.jsonl", "leet-pm"),
    "skeptical": ("skeptical_verify_train.jsonl", "leet-skep"),
    "long_repo": ("long_context_repo_train.jsonl", "leet-repo"),
    "repl": ("repl_sessions_train.jsonl", "leet-repl"),
    "fuzz_test": ("fuzz_and_test_train.jsonl", "leet-fuzz"),
    "spec2parser": ("spec_to_parser_train.jsonl", "leet-spec"),
    "mental_trace": ("mental_trace_train.jsonl", "leet-trace"),
    "transpile_rule": ("rule_transpiler_train.jsonl", "leet-xrule"),
    "safe_harden": ("safe_hardening_train.jsonl", "leet-shrd"),
    "mcp_tools": ("toolsmith_mcp_train.jsonl", "leet-mcp"),
    "reasoning_cot": ("reasoning_cot_train.jsonl", "leet-cot"),
}

THINK_RE = re.compile(r"^\s*<think>(.*?)</think>\s*(.+)$", re.DOTALL)

FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`]+`")
LEET_WORD_RE = re.compile(r"\b(?=[a-z0-9]*[a-z])(?=[a-z0-9]*[43105792])[a-z0-9]{2,}\b", re.IGNORECASE)
NORM_WS_RE = re.compile(r"\s+")
CORP_REFUSAL_RE = re.compile(
    r"\b(?:as an ai|as a language model|as an artificial intelligence|i cannot fulfill this request|i apologize, but|i'm sorry, but as)\b",
    re.IGNORECASE,
)

TECH_ALLOW_RE = re.compile(
    r"\b(?:argon2(?:i|d|id)?|blake2[bs]|secp256[kr]1|ed25519|x25519|curve25519|"
    r"i18n|l10n|a11y|p2p|e2ee?|b2b|m2m|s2s|w3c|log4j\w*|neo4j|fail2ban|"
    r"wasm2wat|wat2wasm|dos2unix|unix2dos|oauth2\w*|http2\w*|smb2\w*|tpm2\w*|"
    r"ros2\w*|catch2\w*|pcre2\w*|libxml2\w*|aria2c|pm2\w*|db2\w*|ec2\w*|s3\w*)\b",
    re.IGNORECASE,
)
CODE_LEET_CORRUPT_RE = re.compile(
    r"\b(?:[43105792]+[a-z]{2,}[a-z0-9]*|[a-z]+[43105792]+[a-z]{2,}[a-z0-9]*)\b",
    re.IGNORECASE,
)


def _norm_user(text: str) -> str:
    return NORM_WS_RE.sub(" ", text.strip()).lower()


def has_natural_leet(text: str, min_words: int = 3) -> bool:
    prose = FENCE_RE.sub(" ", text)
    prose = INLINE_CODE_RE.sub(" ", prose)
    return len(LEET_WORD_RE.findall(prose)) >= min_words


def has_leet_inside_code(text: str) -> bool:
    blocks = FENCE_RE.findall(text) + INLINE_CODE_RE.findall(text)
    if not blocks:
        return False
    joined = TECH_ALLOW_RE.sub(" ", " ".join(blocks))
    cleaned = re.sub(r"\b0[xXbBoO][0-9a-fA-F_]+\b", " ", joined)
    for tok in CODE_LEET_CORRUPT_RE.findall(cleaned):
        if len(tok) <= 16 and not re.fullmatch(r"[0-9a-fA-F]+", tok):
            return True
    return False


def has_valid_json_block(text: str) -> bool:
    matches = JSON_FENCE_RE.findall(text)
    if not matches:
        return False
    for raw in matches:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, (dict, list)):
                return True
        except json.JSONDecodeError:
            continue
    return False


def _extract_first_user(obj: dict) -> str | None:
    msgs = obj.get("messages")
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str):
                return m["content"]
    return None


def _discover_all_existing_jsonls(data_dir: Path, include_siblings: bool = True) -> list[Path]:
    paths: list[Path] = []
    if data_dir.exists():
        for p in sorted(data_dir.glob("*.jsonl")):
            paths.append(p)
    if include_siblings:
        for pat in ("*/*/*.jsonl", "*/*.jsonl"):
            for p in ROOT_DIR.glob(pat):
                if BASE_DIR not in p.parents and p not in paths:
                    paths.append(p)
    return paths


def _load_seen_users(paths: list[Path]) -> set[str]:
    seen: set[str] = set()
    for p in paths:
        if not p.exists():
            continue
        try:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        u = _extract_first_user(obj)
                        if u:
                            seen.add(_norm_user(u))
                    except (json.JSONDecodeError, KeyError, TypeError):
                        continue
        except OSError:
            continue
    return seen


def _track_stats(jsonl_path: Path) -> tuple[int, int, dict[str, int]]:
    if not jsonl_path.exists():
        return 0, 0, {}
    max_seq = 0
    count = 0
    fams: dict[str, int] = {}
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            count += 1
            m = re.search(r"-(\d+)$", obj.get("id", ""))
            if m:
                max_seq = max(max_seq, int(m.group(1)))
            key = obj.get("rejection_reason") if "rejection_reason" in obj else obj.get("family", "unknown")
            fams[key] = fams.get(key, 0) + 1
    return max_seq, count, fams


def _validate_agentic_messages(raw_msgs: list) -> tuple[list[dict] | None, str | None]:
    if not isinstance(raw_msgs, list) or len(raw_msgs) < 4:
        return None, "agentic messages must have >= 4 turns"
    msgs = list(raw_msgs)
    if msgs[0].get("role") == "system":
        if msgs[0].get("content") != PERSONA:
            return None, "system message mismatch"
    else:
        msgs.insert(0, {"role": "system", "content": PERSONA})

    if msgs[1].get("role") != "user" or len(str(msgs[1].get("content", "")).strip()) < 15:
        return None, "missing/short initial user message"

    seen_call_ids: set[str] = set()
    tool_call_count = 0
    for idx, m in enumerate(msgs[1:], start=1):
        role = m.get("role")
        if role not in ("user", "assistant", "tool"):
            return None, f"invalid role '{role}' at msg[{idx}]"
        if role == "assistant":
            tcs = m.get("tool_calls")
            content = str(m.get("content") or "").strip()
            if tcs:
                if not isinstance(tcs, list):
                    return None, "tool_calls must be a list"
                for tc in tcs:
                    tc_id = str(tc.get("id", "")).strip()
                    fn = tc.get("function", {})
                    fn_name = str(fn.get("name", "")).strip()
                    fn_args = fn.get("arguments", "")
                    if not tc_id or fn_name not in ALLOWED_TOOLS:
                        return None, f"invalid tool call name '{fn_name}' or missing id"
                    if isinstance(fn_args, dict):
                        fn["arguments"] = json.dumps(fn_args, ensure_ascii=False)
                    elif isinstance(fn_args, str):
                        try:
                            parsed_args = json.loads(fn_args)
                            if not isinstance(parsed_args, dict):
                                return None, "tool arguments must decode to JSON object"
                        except json.JSONDecodeError:
                            return None, "tool arguments invalid JSON string"
                    else:
                        return None, "tool arguments must be JSON string or object"
                    parsed_check = json.loads(fn["arguments"])
                    for k in parsed_check.keys():
                        if re.search(r"[43105792]", k):
                            return None, f"leet digit in tool argument key '{k}'"
                    seen_call_ids.add(tc_id)
                    tool_call_count += 1
                if content and not has_natural_leet(content, min_words=2):
                    return None, f"assistant msg[{idx}] prose missing leet"
            else:
                if len(content) < 25 or not has_natural_leet(content, min_words=3):
                    return None, f"assistant final/text msg[{idx}] missing natural leet"
        elif role == "tool":
            ref_id = str(m.get("tool_call_id", "")).strip()
            if ref_id not in seen_call_ids:
                return None, f"tool msg[{idx}] references unknown tool_call_id '{ref_id}'"
            if len(str(m.get("content", "")).strip()) < 2:
                return None, f"empty tool output at msg[{idx}]"

    if tool_call_count < 1:
        return None, "agentic trajectory has 0 tool_calls"
    if msgs[-1].get("role") != "assistant" or msgs[-1].get("tool_calls"):
        return None, "last message must be final assistant answer without pending tool_calls"
    return msgs, None


def bank_expansion(
    track: str,
    rows: list[dict],
    data_dir: Path = DATA_DIR,
    sleep_s: float = 3.0,
    check_siblings: bool = True,
) -> dict:
    if track not in TRACK_FILES:
        raise ValueError(f"invalid track '{track}', expected one of {sorted(TRACK_FILES)}")
    if len(rows) > 10:
        raise ValueError(f"batch discipline: max 10 rows per call, got {len(rows)}")

    filename, id_prefix = TRACK_FILES[track]
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".lock_expansion"
    target_path = data_dir / filename
    status_path = data_dir / "EXPANSION_STATUS.json"

    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        all_seen = _load_seen_users(_discover_all_existing_jsonls(data_dir, include_siblings=check_siblings))
        seq, _, _ = _track_stats(target_path)

        status: dict = {}
        if status_path.exists():
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                status = {}

        accepted: list[dict] = []
        dropped: list[str] = []

        for idx, r in enumerate(rows):
            fam = str(r.get("family", "")).strip()
            split_val = "val" if track == "val" else "train"

            if track in ("multiturn", "repl"):
                if track == "multiturn":
                    hat = str(r.get("hat", "")).strip()
                    allowed_mt = MT_RED_FAMILIES if hat == "red" else (MT_BLUE_FAMILIES if hat == "blue" else set())
                    if hat not in ("red", "blue") or fam not in allowed_mt:
                        dropped.append(f"row[{idx}]: invalid hat/family ({hat}/{fam}) for multiturn")
                        continue
                else:
                    hat = "repl"
                    if fam not in REPL_FAMILIES:
                        dropped.append(f"row[{idx}]: invalid family '{fam}' for repl")
                        continue
                turns = r.get("turns", [])
                if not isinstance(turns, list) or len(turns) not in (2, 3, 4):
                    dropped.append(f"row[{idx}]: {track} requires 2 to 4 exchanges")
                    continue
                norm_u0 = _norm_user(str(turns[0].get("user", "")))
                if len(norm_u0) < 15 or norm_u0 in all_seen:
                    dropped.append(f"row[{idx}]: short or duplicate initial user prompt")
                    continue
                msgs = [{"role": "system", "content": PERSONA}]
                ok_turns = True
                for t_i, t in enumerate(turns):
                    ut = str(t.get("user", "")).strip()
                    at = str(t.get("assistant", "")).strip()
                    if len(ut) < 10 or len(at) < 25 or not has_natural_leet(at, min_words=3):
                        dropped.append(f"row[{idx}]: turn[{t_i}] short or missing natural leet")
                        ok_turns = False
                        break
                    msgs.append({"role": "user", "content": ut})
                    msgs.append({"role": "assistant", "content": at})
                if not ok_turns:
                    continue
                seq += 1
                all_seen.add(norm_u0)
                accepted.append({
                    "id": f"{id_prefix}-{seq:06d}",
                    "messages": msgs,
                    "hat": hat,
                    "family": fam,
                    "turns": len(turns),
                    "generator": "gemini-4-carbon",
                    "split": split_val,
                })

            elif track in SIMPLE_SFT_TRACK_FAMILIES:
                allowed = SIMPLE_SFT_TRACK_FAMILIES[track]
                if fam not in allowed:
                    dropped.append(f"row[{idx}]: invalid family '{fam}' for {track}")
                    continue
                if track == "boundary":
                    fam = BOUNDARY_CANONICAL_MAP.get(fam, fam)
                ut = str(r.get("user", "")).strip()
                at = str(r.get("assistant", "")).strip()
                norm_u = _norm_user(ut)
                if len(ut) < 15 or len(at) < 20:
                    dropped.append(f"row[{idx}]: too short")
                    continue
                if norm_u in all_seen:
                    dropped.append(f"row[{idx}]: duplicate user prompt")
                    continue

                if track == "reasoning_cot":
                    m_think = THINK_RE.match(at)
                    if not m_think:
                        dropped.append(f"row[{idx}]: reasoning_cot must start with <think>...</think> followed by answer")
                        continue
                    think_body, visible_ans = m_think.group(1).strip(), m_think.group(2).strip()
                    if len(think_body) < 60:
                        dropped.append(f"row[{idx}]: <think> scratchpad too short")
                        continue
                    if not has_natural_leet(visible_ans, min_words=3):
                        dropped.append(f"row[{idx}]: post-</think> visible answer missing natural leet")
                        continue
                else:
                    min_leet = 2 if track == "oneliners" else 3
                    if not has_natural_leet(at, min_words=min_leet):
                        dropped.append(f"row[{idx}]: missing natural leet")
                        continue

                if track == "long_repo" and len(FENCE_RE.findall(ut)) < 2:
                    dropped.append(f"row[{idx}]: long_repo user prompt must contain >=2 fenced file blocks")
                    continue
                if track in (
                    "purple", "fim", "log2rule", "decompile", "modernize",
                    "long_repo", "fuzz_test", "spec2parser", "transpile_rule",
                    "safe_harden", "mcp_tools",
                ) and "```" not in at:
                    dropped.append(f"row[{idx}]: {track} row must include fenced code block")
                    continue
                if track == "oneliners" and ("`" not in at and "```" not in at):
                    dropped.append(f"row[{idx}]: oneliners row must include command in backticks/fence")
                    continue
                if track == "structured" and not has_valid_json_block(at):
                    dropped.append(f"row[{idx}]: structured row must include valid ```json``` block")
                    continue
                if track == "boundary" and CORP_REFUSAL_RE.search(at):
                    dropped.append(f"row[{idx}]: corporate refusal boilerplate detected")
                    continue

                if track == "coding":
                    hat_val = "chat" if fam.startswith("chat-") else "code"
                else:
                    hat_val = track

                seq += 1
                all_seen.add(norm_u)
                accepted.append({
                    "id": f"{id_prefix}-{seq:06d}",
                    "messages": [
                        {"role": "system", "content": PERSONA},
                        {"role": "user", "content": ut},
                        {"role": "assistant", "content": at},
                    ],
                    "hat": hat_val,
                    "family": fam,
                    "generator": "gemini-4-carbon",
                    "split": split_val,
                })

            elif track == "agentic":
                if fam not in AGENTIC_FAMILIES:
                    dropped.append(f"row[{idx}]: invalid family '{fam}' for agentic")
                    continue
                msgs, err = _validate_agentic_messages(r.get("messages", []))
                if err or msgs is None:
                    dropped.append(f"row[{idx}]: {err}")
                    continue
                norm_u = _norm_user(msgs[1]["content"])
                if norm_u in all_seen:
                    dropped.append(f"row[{idx}]: duplicate user prompt")
                    continue
                seq += 1
                all_seen.add(norm_u)
                accepted.append({
                    "id": f"{id_prefix}-{seq:06d}",
                    "messages": msgs,
                    "hat": "agent",
                    "family": fam,
                    "generator": "gemini-4-carbon",
                    "split": split_val,
                })

            elif track == "val":
                hat = str(r.get("hat", "")).strip()
                allowed_val_hats = {
                    "red", "blue", "code", "chat", "agent", "purple", "boundary",
                    "fim", "pr_review", "structured", "log2rule", "decompile",
                    "arch", "oneliners", "modernize", "postmortem",
                }
                if hat not in allowed_val_hats:
                    dropped.append(f"row[{idx}]: invalid hat '{hat}' for val")
                    continue
                if fam not in ALL_VAL_FAMILIES:
                    dropped.append(f"row[{idx}]: invalid family '{fam}' for val")
                    continue
                if "messages" in r and hat == "agent":
                    msgs, err = _validate_agentic_messages(r["messages"])
                    if err or msgs is None:
                        dropped.append(f"row[{idx}]: {err}")
                        continue
                elif "turns" in r:
                    turns = r["turns"]
                    if not isinstance(turns, list) or len(turns) not in (2, 3):
                        dropped.append(f"row[{idx}]: val multiturn needs 2-3 turns")
                        continue
                    msgs = [{"role": "system", "content": PERSONA}]
                    ok_t = True
                    for t in turns:
                        ut = str(t.get("user", "")).strip()
                        at = str(t.get("assistant", "")).strip()
                        if len(ut) < 10 or len(at) < 25 or not has_natural_leet(at, min_words=3):
                            ok_t = False
                            break
                        msgs.append({"role": "user", "content": ut})
                        msgs.append({"role": "assistant", "content": at})
                    if not ok_t:
                        dropped.append(f"row[{idx}]: val multiturn short or missing leet")
                        continue
                else:
                    ut = str(r.get("user", "")).strip()
                    at = str(r.get("assistant", "")).strip()
                    if len(ut) < 15 or len(at) < 25 or not has_natural_leet(at, min_words=3):
                        dropped.append(f"row[{idx}]: val row short or missing leet")
                        continue
                    if hat == "boundary" and CORP_REFUSAL_RE.search(at):
                        dropped.append(f"row[{idx}]: corporate refusal boilerplate in val")
                        continue
                    msgs = [
                        {"role": "system", "content": PERSONA},
                        {"role": "user", "content": ut},
                        {"role": "assistant", "content": at},
                    ]
                norm_u = _norm_user(msgs[1]["content"])
                if norm_u in all_seen:
                    dropped.append(f"row[{idx}]: duplicate/leaked user prompt in val")
                    continue
                seq += 1
                all_seen.add(norm_u)
                accepted.append({
                    "id": f"{id_prefix}-{seq:06d}",
                    "messages": msgs,
                    "hat": hat,
                    "family": fam,
                    "generator": "gemini-4-carbon",
                    "split": "val",
                })

            elif track == "dpo":
                reason = str(r.get("rejection_reason", "")).strip()
                if reason not in DPO_REASONS:
                    dropped.append(f"row[{idx}]: invalid rejection_reason '{reason}'")
                    continue
                if not fam:
                    fam = "general"
                ut = str(r.get("user", "")).strip()
                chosen = str(r.get("chosen", "")).strip()
                rejected = str(r.get("rejected", "")).strip()
                norm_u = _norm_user(ut)
                if len(ut) < 15 or len(chosen) < 25 or len(rejected) < 20 or chosen == rejected:
                    dropped.append(f"row[{idx}]: short or identical chosen/rejected")
                    continue
                if norm_u in all_seen:
                    dropped.append(f"row[{idx}]: duplicate DPO user prompt")
                    continue
                if not has_natural_leet(chosen, min_words=3):
                    dropped.append(f"row[{idx}]: chosen missing natural leet")
                    continue
                if has_leet_inside_code(chosen):
                    dropped.append(f"row[{idx}]: chosen has leet inside code")
                    continue
                if reason == "leet-in-code" and not has_leet_inside_code(rejected):
                    dropped.append(f"row[{idx}]: rejected for 'leet-in-code' lacks leet inside code/backticks")
                    continue
                if reason == "plain-english-drift" and has_natural_leet(rejected, min_words=2):
                    dropped.append(f"row[{idx}]: rejected for 'plain-english-drift' still contains leet")
                    continue
                seq += 1
                all_seen.add(norm_u)
                accepted.append({
                    "id": f"{id_prefix}-{seq:06d}",
                    "messages": [
                        {"role": "system", "content": PERSONA},
                        {"role": "user", "content": ut},
                    ],
                    "chosen": chosen,
                    "rejected": rejected,
                    "rejection_reason": reason,
                    "family": fam,
                    "generator": "gemini-4-carbon",
                    "split": "train",
                })

        if accepted:
            with target_path.open("a", encoding="utf-8") as out:
                for rec in accepted:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                os.fsync(out.fileno())

        tracks_summary: dict = {}
        grand_expansion_total = 0
        for t_name, (t_file, _) in TRACK_FILES.items():
            _, t_count, t_fams = _track_stats(data_dir / t_file)
            grand_expansion_total += t_count
            tracks_summary[t_name] = {
                "file": t_file,
                "rows": t_count,
                "breakdown": dict(sorted(t_fams.items())),
            }

        new_status = {
            "agent": "agent 3 (phase 2+3 multi-dataset suite)",
            "generator": "gemini-4-carbon",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "expansion_total_rows": grand_expansion_total,
            "batches_done": int(status.get("batches_done", 0)) + (1 if accepted else 0),
            "dropped_rows": int(status.get("dropped_rows", 0)) + len(dropped),
            "tracks": tracks_summary,
            "last_batch": {
                "track": track,
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
        assert bank_expansion("fim", [{
            "family": "fim-rust-systems",
            "user": "Complete the `<FIM>` section in this Rust constant-time slice comparison helper.",
            "assistant": "u53 bitwise XOR accumulation w17h `black_box` 0r `subtle::ConstantTimeEq` 50 7h3 c0mp1l3r n3v3r short-circuits:\n```rust\npub fn ct_eq(a: &[u8], b: &[u8]) -> bool {\n    if a.len() != b.len() { return false; }\n    let mut diff = 0u8;\n    for (&x, &y) in a.iter().zip(b.iter()) { diff |= x ^ y; }\n    diff == 0\n}\n```"
        }], data_dir=tp, sleep_s=0.0, check_siblings=False)["tracks"]["fim"]["rows"] == 1

        assert bank_expansion("structured", [{
            "family": "struct-sarif-finding",
            "user": "Extract this SQL string concatenation issue in `db.py:42` into a structured JSON finding.",
            "assistant": "h3r3 15 7h3 normalized JSON finding f0r 7h3 unparameterized qu3ry 47 `db.py:42`:\n```json\n{\"rule_id\": \"SQLI-001\", \"severity\": \"high\", \"file\": \"db.py\", \"line\": 42, \"remediation\": \"Use parameterized bound placeholders\"}\n```"
        }], data_dir=tp, sleep_s=0.0, check_siblings=False)["tracks"]["structured"]["rows"] == 1

        assert bank_expansion("oneliners", [{
            "family": "1l-jq-json",
            "user": "Give me a fast jq one-liner to count HTTP status codes in `access.jsonl`.",
            "assistant": "57r34m 4nd tally `status` codes w17h `jq` + `sort`:\n`jq -r '.status' access.jsonl | sort | uniq -c | sort -rn`"
        }], data_dir=tp, sleep_s=0.0, check_siblings=False)["tracks"]["oneliners"]["rows"] == 1
    print("phase 2+3 expansion self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        payload = json.loads(sys.stdin.read())
        out = bank_expansion(
            track=payload["track"],
            rows=payload["rows"],
            sleep_s=float(payload.get("sleep_s", 3.0)),
        )
        print(json.dumps({
            "updated_at": out["updated_at"],
            "expansion_total_rows": out["expansion_total_rows"],
            "track_rows": out["tracks"][payload["track"]]["rows"],
            "breakdown": out["tracks"][payload["track"]]["breakdown"],
            "last_batch": out["last_batch"],
        }))
