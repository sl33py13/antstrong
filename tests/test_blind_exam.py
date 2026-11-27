import json

import pytest

from tools import blind_exam as be

GOOD = '''```python
import argparse, csv, json, os
p = argparse.ArgumentParser()
p.add_argument("--out"); p.add_argument("--key"); p.add_argument("--size"); p.add_argument("--seed", type=int)
a = p.parse_args()
os.makedirs(a.out, exist_ok=True)
for i in range(8):
    with open(os.path.join(a.out, f"t{i}.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["id", "v"]); w.writerows([[j, j * i] for j in range(10)])
with open(os.path.join(a.out, "README.txt"), "w") as f:
    f.write("planted: firmware 4.2 fails")   # a leak the runner must quarantine
json.dump({"patterns": ["secret"]}, open(a.key, "w"))
```'''

CRASHES = '```python\nimport sys\nraise SystemExit("boom: column missing")\n```'


class FakeProvider(be.Provider):
    def __init__(self, replies):
        super().__init__("openai", "k", "fake")
        self.replies = list(replies)
        self.seen = []

    def chat(self, messages):
        self.seen.append([m["content"] for m in messages])
        return self.replies.pop(0)


@pytest.mark.parametrize("src", [
    "import subprocess",
    "import socket",
    "from urllib import request",
    "import os\nos.remove('x')",
    "import shutil",
    "eval('1')",
    "import os\nos.system('dir')",
    "().__class__.__bases__",
])
def test_unsafe_scripts_rejected(src):
    with pytest.raises(be.UnsafeScript):
        be.check_script_safety(src)


def test_safe_script_allowed():
    be.check_script_safety(be.extract_python(GOOD))


def test_extract_picks_largest_block():
    assert "argparse" in be.extract_python("intro\n```python\nx=1\n```\n" + GOOD)


def _dirs(tmp_path):
    priv, data = tmp_path / "private", tmp_path / "data"
    priv.mkdir(); data.mkdir()
    return priv, data


def test_good_run_keeps_key_private_and_quarantines_leaks(tmp_path):
    priv, data = _dirs(tmp_path)
    r = be.run_job(FakeProvider([GOOD]), "ops", "r1", "small", 1, priv, data)
    assert r["ok"] and r["tables"] == 8 and r["quarantined_files"] == 1
    out = data / "openai_ops"
    assert not (out / "README.txt").exists()
    assert all(f.suffix == ".csv" for f in out.rglob("*") if f.is_file())
    assert json.loads((priv / "openai_ops_answer_key.json").read_text())["patterns"] == ["secret"]
    assert not any("answer_key" in f.name for f in data.rglob("*"))


def test_crash_is_sent_back_and_fixed(tmp_path):
    priv, data = _dirs(tmp_path)
    fake = FakeProvider([CRASHES, GOOD])
    r = be.run_job(fake, "traps", "r1", "small", 1, priv, data)
    assert r["ok"] and r["attempts"] == 2
    assert "boom: column missing" in fake.seen[1][-1]


def test_unsafe_reply_is_rejected_then_fixed(tmp_path):
    priv, data = _dirs(tmp_path)
    fake = FakeProvider(["```python\nimport subprocess\n```", GOOD])
    r = be.run_job(fake, "schema", "r1", "small", 1, priv, data)
    assert r["ok"]
    assert "not allowed" in fake.seen[1][-1]


def test_gives_up_after_repairs(tmp_path):
    priv, data = _dirs(tmp_path)
    r = be.run_job(FakeProvider([CRASHES] * 3), "ops", "r1", "small", 1, priv, data)
    assert not r["ok"] and not (data / "openai_ops").exists()


def test_first_run_creates_keys_template(tmp_path, monkeypatch):
    monkeypatch.setattr(be.os, "name", "posix")
    with pytest.raises(SystemExit):
        be.load_settings(tmp_path / "p")
    text = (tmp_path / "p" / "keys.env").read_text()
    assert "OPENAI_API_KEY=" in text and "GEMINI_API_KEY=" in text


def test_fallback_model_choice():
    assert be.pick_fallback_model("openai", ["gpt-5.5", "gpt-6.2-sol", "gpt-6-cyber", "gpt-6.2-mini", "gpt-image-2.6", "gpt-5.6-sol-2026-08-05"]) == "gpt-6.2-sol"
    assert be.pick_fallback_model("gemini", ["gemini-flash-latest", "gemini-pro-latest", "gemini-3.1-pro-preview"]) == "gemini-pro-latest"
    assert be.pick_fallback_model("gemini", ["gemini-flash-latest", "gemini-3.1-pro-preview", "gemini-2.5-pro"]) == "gemini-3.1-pro-preview"
    assert be.pick_fallback_model("gemini", ["gemini-flash-latest"]) == "gemini-flash-latest"


def test_missing_model_switches_automatically(tmp_path):
    priv, data = _dirs(tmp_path)

    class Flaky(FakeProvider):
        def chat(self, messages):
            if self.model == "gone":
                raise RuntimeError("HTTP 404: model_not_found")
            return super().chat(messages)

        def available_models(self):
            return ["gpt-6.2-sol", "gpt-6.2-mini"]

    fake = Flaky([GOOD]); fake.model = "gone"
    r = be.run_job(fake, "ops", "r1", "small", 1, priv, data)
    assert r["ok"] and r["model"] == "gpt-6.2-sol"
