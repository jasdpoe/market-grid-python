"""Bounded, offline pre-publication scan; never prints suspected secret values."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "__pycache__", ".venv", "venv", "build", "dist", ".pytest_cache"}
PRIVATE_NAMES = {".openai", ".sites-runtime", ".wrangler", ".ssh", ".npmrc", ".netrc"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "service token": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b"),
    "assigned credential": re.compile(r'''(?im)(?:api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*["']?[A-Za-z0-9_/-]{16,}'''),
    "personal Windows path": re.compile(r"[A-Z]:[\\/]+Users[\\/]+[^\s/\\]+", re.I),
    "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "deployment URL": re.compile(r"https?://[^\s]+\.chatgpt\.site", re.I),
}
TEXT_SUFFIXES = {".py", ".js", ".mjs", ".html", ".css", ".svg", ".md", ".toml", ".json", ".yml", ".yaml", ".txt"}


def scan():
    findings = []
    count = 0
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if any(part in SKIP or part.endswith(".egg-info") for part in relative.parts):
            continue
        if any(part in PRIVATE_NAMES for part in relative.parts):
            findings.append((relative, "internal hosting/configuration file"))
            continue
        if not path.is_file():
            continue
        count += 1
        if path.name.startswith((".env", ".dev.vars")) or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".log", ".sqlite", ".db", ".zip"}:
            findings.append((relative, "private or generated file"))
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".gitignore":
            findings.append((relative, "unreviewed file type"))
            continue
        content = path.read_text(encoding="utf-8")
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append((relative, label))
    for path, reason in findings:
        print(f"REVIEW: {path.as_posix()} ({reason})")
    print(f"Scanned {count} files; {len(findings)} finding(s). Git history and generated directories excluded.")
    return bool(findings)


if __name__ == "__main__":
    sys.exit(scan())
