"""Blind exam runner: has other AIs (Gemini, ChatGPT) write synthetic MSP datasets
with planted patterns, so the antSTRONG engine can be tested on data its builders
have not seen.

Ben runs this on his PC (double-click run_blind_exam.bat). It:
  1. sends each exam prompt to the other AI through its official API,
  2. safety-checks the Python script that comes back,
  3. runs it, writing DATA into   <project>/blind/<run_id>/<job>/   (Claude can read this)
     and the ANSWER KEY, scripts and replies into the PRIVATE folder (Claude cannot),
  4. if a script crashes, sends the error back to the same AI to fix (up to 2 times).

Private folder (outside the project, so Claude never sees it):
  %USERPROFILE%\\antSTRONG_blind_private\\
    keys.env           API keys, typed in by Ben only
    <run_id>\\...       scripts, AI replies, answer keys, logs

Only the standard library is used, so it runs in the project's .venv as is.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT / "blind"
PRIVATE_ROOT = Path(os.environ.get("ANTSTRONG_BLIND_PRIVATE", Path.home() / "antSTRONG_blind_private"))

DEFAULT_MODELS = {"openai": "gpt-6.2-sol", "gemini": "gemini-pro-latest"}

KEYS_TEMPLATE = """# antSTRONG blind exam settings. Paste your keys after the = signs, save, close.
# This file stays on your PC only. Never paste these keys into a chat.
OPENAI_API_KEY=
GEMINI_API_KEY=

# Optional: change the model names if the runner says a model was not found.
OPENAI_MODEL={openai}
GEMINI_MODEL={gemini}
""".format(**DEFAULT_MODELS)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CORE_PROMPT = """I'm building software that analyses a managed IT service provider's (MSP's) operational data and automatically finds non-obvious, decision-relevant patterns for executives. I need a realistic SYNTHETIC dataset to blind-test it. The software's developers must not see how the patterns were planted.

Write ONE self-contained Python 3 script that:
- Uses only the Python standard library (no pip installs). Deterministic: a --seed argument (default 42).
- Takes --out <folder> for the data and --key <file> for the answer key. Never write any part of the answer key, hints, comments or a data dictionary into the --out folder. Only CSV files go in --out.
- Takes --size small|large (small: about 20k rows total; large: about 500k+ rows total). Large must finish in under 5 minutes on a normal PC.
- Writes UTF-8 CSV files that look like real exports from MSP tools (PSA/ticketing, RMM/device monitoring, time sheets, contracts and billing, sites and locations, staff). At least 8 tables that link by IDs, realistic for an Australian MSP with 40 to 200 client businesses over 18 months.
- Uses ONLY fictional business and person names. No real companies or people. Real Australian suburbs and cities are fine.
- Includes realistic mess: missing values, inconsistent spellings of the same client, duplicated rows, mixed date formats, free-text ticket notes written like real technicians write, and seasonal and weekly rhythms.
- Must not use the network, run other programs, or delete files. Allowed modules: argparse, csv, json, random, math, datetime, os.path, pathlib, collections, itertools, string, statistics, uuid, hashlib, re, sys, time, dataclasses, typing, functools, decimal, bisect, heapq, calendar, textwrap, enum, copy, operator.
- Prints nothing about the planted patterns to the screen.

Plant at least 6 TRUE patterns, each a combination of 2 to 3 attributes that drives a measurable business outcome (ticket volume, repeat faults, SLA breaches, technician hours, margin, churn). Vary their strength from obvious to subtle. Also plant at least 4 DECOYS: things that look meaningful at first glance but are not real effects.

The answer key (--key, JSON) must list, for every planted pattern and decoy: a plain-English description, the exact conditions in terms of table and column names, the affected outcome, the effect size, the number of affected records, and for decoys, why it is spurious. Also list every column that contains personal or identifying information (names, emails, phone numbers, addresses, IPs, serial numbers).

Reply with the complete script in a single ```python code block and nothing else. Do not describe the planted patterns outside the script.
"""

ADDENDA = {
    "ops": """Focus: device and infrastructure patterns. Include network devices with firmware versions, models, install dates, site locations with distance from the client's head office, and ISP or link type. Patterns should resemble "devices of model X on firmware Y at sites more than Z km away fail far more often", plus technician- and client-level effects.""",
    "schema": """Focus: schema messiness. Use 40+ tables in total (many irrelevant), cryptic or inconsistent column names (e.g. "cust_nm", "CLIENT", "acct_ref2"), wide tables with 60+ columns, and personal information hidden in unexpected places (an email address inside a notes field, a phone number in a "ref" column, staff names inside ticket summaries). Plant fewer patterns (minimum 4), but make them span 3 or more joined tables.""",
    "traps": """Focus: traps that fool naive analysis. Include a Simpson's paradox (an effect that reverses when split by a third variable), a confounder (two things correlated only because both depend on a hidden third), an effect that begins at a specific date (e.g. after a firmware rollout or a staff change), a seasonal effect that mimics a real problem, and small groups with extreme rates purely by chance. Every trap must be explained in the answer key.""",
}

# Which AI writes which exam. Two different companies, three different jobs.
JOBS = [("gemini", "ops"), ("openai", "schema"), ("gemini", "traps")]

# ---------------------------------------------------------------------------
# Safety check for AI-written scripts
# ---------------------------------------------------------------------------

ALLOWED_MODULES = {
    "argparse", "csv", "json", "random", "math", "datetime", "os", "pathlib", "collections",
    "itertools", "string", "statistics", "uuid", "hashlib", "re", "sys", "time", "dataclasses",
    "typing", "functools", "decimal", "bisect", "heapq", "calendar", "textwrap", "enum", "copy",
    "operator", "__future__",
}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__", "breakpoint", "input"}
FORBIDDEN_ATTRS = {
    # os / pathlib: deleting, renaming, running programs, changing permissions
    "system", "popen", "remove", "unlink", "rmdir", "removedirs", "rename", "replace", "chmod",
    "chown", "kill", "fork", "startfile", "execv", "execve", "execl", "execlp", "execvp",
    "spawnl", "spawnv", "spawnve", "putenv", "rmtree",
}


class UnsafeScript(Exception):
    pass


def check_script_safety(source: str) -> None:
    """Static check. Reduces risk from AI-written code; it is not a full sandbox."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise UnsafeScript(f"Script does not parse: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_MODULES:
                    raise UnsafeScript(f"Imports a module that is not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root not in ALLOWED_MODULES:
                raise UnsafeScript(f"Imports a module that is not allowed: {node.module}")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in FORBIDDEN_CALLS:
                raise UnsafeScript(f"Calls a function that is not allowed: {fn.id}()")
            if isinstance(fn, ast.Attribute) and fn.attr in FORBIDDEN_ATTRS:
                raise UnsafeScript(f"Calls something that is not allowed: .{fn.attr}()")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr not in {"__name__", "__init__", "__file__", "__dict__"}:
            raise UnsafeScript(f"Uses a hidden attribute that is not allowed: {node.attr}")


def extract_python(reply: str) -> str:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", reply, flags=re.S | re.I)
    if not blocks:
        raise ValueError("The reply did not contain a ```python code block.")
    return max(blocks, key=len)

# ---------------------------------------------------------------------------
# API clients (standard library only)
# ---------------------------------------------------------------------------


def _post_json(url: str, body: dict, headers: dict, timeout: int = 900) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"HTTP {exc.code} from {url.split('?')[0]}: {detail}") from exc


def _get_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


@dataclass
class Provider:
    name: str
    key: str
    model: str

    def chat(self, messages: list[dict]) -> str:
        if self.name == "openai":
            data = _post_json(
                "https://api.openai.com/v1/chat/completions",
                {"model": self.model, "messages": messages},
                {"Authorization": f"Bearer {self.key}"},
            )
            return data["choices"][0]["message"]["content"]
        if self.name == "gemini":
            contents = [
                {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages
            ]
            data = _post_json(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                {"contents": contents},
                {"x-goog-api-key": self.key},
            )
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        raise ValueError(f"Unknown provider {self.name}")

    def available_models(self) -> list[str]:
        try:
            if self.name == "openai":
                data = _get_json("https://api.openai.com/v1/models", {"Authorization": f"Bearer {self.key}"})
                return sorted(m["id"] for m in data.get("data", []))
            data = _get_json("https://generativelanguage.googleapis.com/v1beta/models", {"x-goog-api-key": self.key})
            return sorted(m["name"].split("/")[-1] for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", []))
        except Exception as exc:  # noqa: BLE001
            return [f"(could not list models: {exc})"]

_VERSION_RE = re.compile(r"(\d+(?:\.\d+)?)")
_OPENAI_SKIP = ("mini", "nano", "cyber", "audio", "realtime", "image", "search", "codex", "chat-latest",
                "transcribe", "tts", "embedding", "moderation", "whisper", "oss", "instruct", "preview", "daybreak")


def pick_fallback_model(provider: str, available: list[str]) -> str | None:
    """Choose the strongest general-purpose text model from what the key can use."""
    if provider == "gemini":
        if "gemini-pro-latest" in available:
            return "gemini-pro-latest"
        pros = [m for m in available if m.startswith("gemini-") and "-pro" in m and "image" not in m and "tts" not in m]
        flashes = [m for m in available if m == "gemini-flash-latest"]
        pool = pros or flashes
    else:
        pool = [m for m in available if m.startswith("gpt-") and not any(x in m for x in _OPENAI_SKIP)
                and not re.search(r"\d{4}-\d{2}-\d{2}", m)]
    if not pool:
        return None

    def version(m: str) -> float:
        found = _VERSION_RE.search(m.split("-", 1)[1] if "-" in m else m)
        return float(found.group(1)) if found else 0.0

    return sorted(pool, key=lambda m: (version(m), "latest" in m, -len(m)))[-1]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def load_settings(private_root: Path) -> dict[str, str]:
    keys_file = private_root / "keys.env"
    if not keys_file.exists():
        private_root.mkdir(parents=True, exist_ok=True)
        keys_file.write_text(KEYS_TEMPLATE, encoding="utf-8")
        print(f"\nFirst run: created {keys_file}")
        print("Paste your OpenAI and Gemini API keys into it, save, close it, then run this again.")
        if os.name == "nt":
            subprocess.Popen(["notepad.exe", str(keys_file)])  # noqa: S603,S607
        sys.exit(0)
    settings = {}
    for line in keys_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            settings[k.strip()] = v.strip().strip('"').strip("'")
    return settings

# ---------------------------------------------------------------------------
# Running one exam
# ---------------------------------------------------------------------------


def run_generator(script: Path, out_dir: Path, key_file: Path, size: str, seed: int, log: Path) -> tuple[bool, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-I", str(script), "--out", str(out_dir), "--key", str(key_file), "--size", size, "--seed", str(seed)]
    try:
        proc = subprocess.run(cmd, cwd=str(script.parent), capture_output=True, text=True, timeout=1200)  # noqa: S603
    except subprocess.TimeoutExpired:
        return False, "The script took more than 20 minutes and was stopped."
    log.write_text(f"$ {' '.join(cmd)}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}", encoding="utf-8")
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout)[-3000:]
    if not key_file.exists():
        return False, f"The script finished but did not write the answer key to --key ({key_file})."
    try:
        json.loads(key_file.read_text(encoding="utf-8"))
    except ValueError as exc:
        return False, f"The answer key is not valid JSON: {exc}"
    csvs = list(out_dir.rglob("*.csv"))
    if len(csvs) < 8:
        return False, f"Only {len(csvs)} CSV files were written to --out; at least 8 are required."
    return True, ""


def quarantine_non_csv(out_dir: Path, private_dir: Path) -> list[str]:
    """Anything in the data folder that is not a CSV could leak hints: move it to private."""
    moved = []
    for f in list(out_dir.rglob("*")):
        if f.is_file() and f.suffix.lower() != ".csv":
            dest = private_dir / "quarantined" / f.relative_to(out_dir)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dest))
            moved.append(str(f.relative_to(out_dir)))
    return moved


def run_job(provider: Provider, job: str, run_id: str, size: str, seed: int, private_run: Path, data_run: Path, max_repairs: int = 2) -> dict:
    tag = f"{provider.name}_{job}"
    out_dir = data_run / tag
    key_file = private_run / f"{tag}_answer_key.json"
    messages = [{"role": "user", "content": CORE_PROMPT + "\n" + ADDENDA[job]}]
    print(f"\n[{tag}] asking {provider.name} ({provider.model}) to write the generator. This can take a few minutes...")

    for attempt in range(max_repairs + 1):
        try:
            reply = provider.chat(messages)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            model_missing = any(t in msg.lower() for t in ("404", "not found", "does not exist", "model_not_found", "invalid model"))
            fallback = pick_fallback_model(provider.name, provider.available_models()) if model_missing else None
            if fallback and fallback != provider.model:
                print(f"[{tag}] model {provider.model} is not available on your key; using {fallback} instead.")
                provider.model = fallback
                try:
                    reply = provider.chat(messages)
                except Exception as exc2:  # noqa: BLE001
                    return {"job": tag, "ok": False, "error": f"API call failed: {exc2}"}
            else:
                if model_missing:
                    msg += "\nModels your key can use: " + ", ".join(provider.available_models()[:60])
                return {"job": tag, "ok": False, "error": f"API call failed: {msg}"}

        (private_run / f"{tag}_reply_{attempt}.md").write_text(reply, encoding="utf-8")
        messages.append({"role": "assistant", "content": reply})

        try:
            source = extract_python(reply)
            check_script_safety(source)
        except (ValueError, UnsafeScript) as exc:
            problem = str(exc)
        else:
            script = private_run / f"{tag}_generator.py"
            script.write_text(source, encoding="utf-8")
            if out_dir.exists():
                shutil.rmtree(out_dir)
            print(f"[{tag}] running the generator (attempt {attempt + 1})...")
            ok, problem = run_generator(script, out_dir, key_file, size, seed, private_run / f"{tag}_run_{attempt}.log")
            if ok:
                moved = quarantine_non_csv(out_dir, private_run)
                csvs = sorted(out_dir.rglob("*.csv"))
                rows = 0
                for c in csvs:
                    with open(c, "rb") as fh:
                        rows += max(0, sum(1 for _ in fh) - 1)
                print(f"[{tag}] done: {len(csvs)} tables, about {rows:,} rows.")
                return {"job": tag, "ok": True, "provider": provider.name, "model": provider.model,
                        "tables": len(csvs), "rows": rows, "quarantined_files": len(moved), "attempts": attempt + 1}

        print(f"[{tag}] problem: {problem.splitlines()[-1] if problem else 'unknown'}")
        if attempt < max_repairs:
            print(f"[{tag}] asking {provider.name} to fix it...")
            messages.append({"role": "user", "content": (
                "The script failed or was rejected. Fix it and reply with the complete corrected script in a single "
                "```python code block and nothing else. All original requirements still apply.\n\nProblem:\n" + problem[-3000:]
            )})

    if out_dir.exists():
        shutil.rmtree(out_dir)
    return {"job": tag, "ok": False, "error": f"Still failing after {max_repairs} fixes. Last problem: {problem[-800:]}"}

# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a blind exam: other AIs generate test data with hidden answer keys.")
    ap.add_argument("--size", choices=["small", "large"], default="large")
    ap.add_argument("--seed", type=int, default=None, help="Defaults to a new random seed each run.")
    ap.add_argument("--only", choices=[f"{p}_{j}" for p, j in JOBS], help="Run one exam only.")
    args = ap.parse_args(argv)

    settings = load_settings(PRIVATE_ROOT)
    providers = {}
    for name, key_name in (("openai", "OPENAI_API_KEY"), ("gemini", "GEMINI_API_KEY")):
        key = settings.get(key_name) or os.environ.get(key_name, "")
        if key:
            providers[name] = Provider(name, key, settings.get(f"{name.upper()}_MODEL") or DEFAULT_MODELS[name])

    seed = args.seed if args.seed is not None else int(time.time()) % 1_000_000
    run_id = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    private_run = PRIVATE_ROOT / run_id
    data_run = DATA_ROOT / run_id
    private_run.mkdir(parents=True, exist_ok=True)
    data_run.mkdir(parents=True, exist_ok=True)
    print(f"Blind exam {run_id}, size {args.size}, seed {seed}")
    print(f"Data for Claude:          {data_run}")
    print(f"Private (answer keys):    {private_run}")

    results = []
    for prov_name, job in JOBS:
        if args.only and args.only != f"{prov_name}_{job}":
            continue
        if prov_name not in providers:
            results.append({"job": f"{prov_name}_{job}", "ok": False, "error": f"No {prov_name.upper()} key in keys.env"})
            continue
        results.append(run_job(providers[prov_name], job, run_id, args.size, seed, private_run, data_run))

    # What Claude may see: which exams exist and how big they are. Nothing about their contents.
    manifest = {"run_id": run_id, "size": args.size, "seed": seed,
                "exams": [{k: v for k, v in r.items() if k != "error"} for r in results]}
    (data_run / "manifest.csv").write_text(
        "exam,ok,provider,model,tables,rows\n" + "".join(
            f"{r['job']},{r['ok']},{r.get('provider', '')},{r.get('model', '')},{r.get('tables', '')},{r.get('rows', '')}\n" for r in results
        ),
        encoding="utf-8",
    )
    (private_run / "results.json").write_text(json.dumps({**manifest, "results": results}, indent=2), encoding="utf-8")

    print("\n================ SUMMARY ================")
    for r in results:
        print(("OK    " if r["ok"] else "FAILED") + f"  {r['job']}" + ("" if r["ok"] else f"\n        {r['error'][:600]}"))
    print("\nTell Claude the exam is ready (or paste only the FAILED lines above). Do not open or share the answer keys yet.")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
