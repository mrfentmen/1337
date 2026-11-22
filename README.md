# 1337

Our own model. Not a paper, not part of Nemesis — a build.

**The idea:** take an open code model (Qwen Coder), fine-tune it on synthetic
red team / blue team data, and give it a persona called **1337** that speaks
leetspeak. Red hat data teaches the offensive side (CTF and lab framed),
blue hat data teaches the defensive side (logs, detection, response).
The trained adapter ships under the name **1337**.

## Plan

1. **Data** — synthetic SFT rows generated with Gemini 4 Carbon.
   Red and blue sets, small batches, every row banked to disk the moment
   it lands. Spec for the generator: [PROMPT.md](PROMPT.md).
2. **Training** — LoRA adapter on Qwen Coder via the Modal pipeline
   (the same route as the Llama adapters: 906-step runs, zipped release).
3. **Release** — adapter + this data published here.

## Data format

One JSON object per line:

```json
{"id": "leet-red-000001",
 "messages": [
   {"role": "system", "content": "<the 1337 persona, verbatim from PROMPT.md>"},
   {"role": "user", "content": "<a security task or question>"},
   {"role": "assistant", "content": "<the answer, in leet, technically correct>"}],
 "hat": "red",
 "family": "ctf-web",
 "generator": "gemini-4-carbon",
 "split": "train"}
```

## Doctrine

Red data is CTF, lab, and sandbox only: concepts and practice on systems
built to be attacked. No instructions for hitting real targets, no working
malware, no real-world intrusion recipes. Blue data is unrestricted
defensive work. Same house rules as every dataset we generate.

## Status

2026-11-21 — repo created, generation prompt written. Data generation
runs through Hermes with the Gemini 4 hackathon key (the key dies
2026-11-22, so data comes first, training after).
