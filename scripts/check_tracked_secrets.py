#!/usr/bin/env python3
"""Reject local-secret paths and likely credentials tracked by Git.

The scanner intentionally reports only paths, line numbers, and rule names. It
never prints the matching value.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


HIGH_CONFIDENCE_PATTERNS = {
    "OpenAI/OpenRouter-style API key": re.compile(
        rb"\bsk-(?:or-v1-)?[A-Za-z0-9_-]{16,}\b"
    ),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{20,}\b"),
    "Groq API key": re.compile(rb"\bgsk_[A-Za-z0-9_-]{16,}\b"),
    "Hugging Face token": re.compile(rb"\bhf_[A-Za-z0-9]{20,}\b"),
    "GitHub token": re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "private key block": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
}

NAMED_SECRET_ASSIGNMENT = re.compile(
    rb'''(?ix)
    ["']?
    (?:
        api[_-]?keys?|access[_-]?tokens?|refresh[_-]?tokens?|
        client[_-]?secrets?|passwords?|passwds?|authorization|
        hf_token|pixiv_refresh_token
    )
    ["']?
    \s*[:=]\s*
    ["'](?P<value>[^"'\r\n]{6,})["']
    ''',
)

SERVICE_SECRET_ASSIGNMENT = re.compile(
    rb'''(?ix)
    ["']?
    (?:deepseek|openrouter|gemini|groq|openai|prodia)
    ["']?
    \s*[:=]\s*
    ["'](?P<value>[^"'\r\n]{6,})["']
    ''',
)

CONFIG_LIKE_SUFFIXES = (
    ".cfg",
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
)

PLACEHOLDER_MARKERS = (
    "your_",
    "example",
    "sample",
    "placeholder",
    "changeme",
    "replace_me",
    "在此",
    "你的",
    "...",
    "***",
)

DATABASE_SUFFIXES = (
    ".db",
    ".db-shm",
    ".db-wal",
    ".sqlite",
    ".sqlite-shm",
    ".sqlite-wal",
    ".sqlite3",
    ".sqlite3-shm",
    ".sqlite3-wal",
)

PRIVATE_KEY_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int | None
    rule: str


def run_git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, stderr=subprocess.DEVNULL
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"git command failed: git {' '.join(args)}") from exc


def repository_root() -> Path:
    try:
        raw = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("run this command inside a Git repository") from exc
    return Path(raw.decode().strip())


def forbidden_path_reason(path_text: str) -> str | None:
    path = PurePosixPath(path_text)
    lower_name = path.name.lower()
    lower_parts = tuple(part.lower() for part in path.parts)

    if lower_name == "config.json":
        return "real config.json must remain local"
    if lower_name in {"config.local.json"} or (
        lower_name.startswith("config.") and lower_name.endswith(".local.json")
    ):
        return "local config variant must remain local"
    if lower_name == ".env" or (
        lower_name.startswith(".env.")
        and not lower_name.endswith((".example", ".sample", ".template"))
    ):
        return "environment file must remain local"
    if lower_name.endswith(PRIVATE_KEY_SUFFIXES) or lower_name in {
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "keystore.json",
    }:
        return "private key or keystore must remain local"
    if lower_name.endswith(DATABASE_SUFFIXES):
        return "runtime database must remain local"
    if len(lower_parts) >= 2 and lower_parts[:2] == ("bot", "data"):
        return "Bot runtime state must remain local"
    if lower_parts and lower_parts[0].startswith("napcat.shell"):
        return "NapCat account/runtime files must remain local"
    return None


def is_placeholder(value: bytes) -> bool:
    text = value.decode("utf-8", errors="ignore").strip().lower()
    if not text:
        return True
    if any(marker in text for marker in PLACEHOLDER_MARKERS):
        return True
    return set(text) <= {"x", "*", "-", "_", ".", "<", ">", " "}


def line_number(data: bytes, offset: int) -> int:
    return data.count(b"\n", 0, offset) + 1


def scan_content(path: str, data: bytes) -> list[Finding]:
    if b"\0" in data:
        return []

    findings: list[Finding] = []
    for rule, pattern in HIGH_CONFIDENCE_PATTERNS.items():
        for match in pattern.finditer(data):
            findings.append(Finding(path, line_number(data, match.start()), rule))

    for match in NAMED_SECRET_ASSIGNMENT.finditer(data):
        if not is_placeholder(match.group("value")):
            findings.append(
                Finding(
                    path,
                    line_number(data, match.start()),
                    "non-placeholder value assigned to a secret field",
                )
            )

    lower_path = path.lower()
    if lower_path.endswith(CONFIG_LIKE_SUFFIXES) or "/.env" in lower_path:
        for match in SERVICE_SECRET_ASSIGNMENT.finditer(data):
            if not is_placeholder(match.group("value")):
                findings.append(
                    Finding(
                        path,
                        line_number(data, match.start()),
                        "non-placeholder value assigned to a service credential",
                    )
                )
    return findings


def scan_tracked_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    candidates = run_git(
        root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
    ).split(b"\0")
    for raw_path in candidates:
        if not raw_path:
            continue
        path_text = raw_path.decode("utf-8", errors="surrogateescape")
        reason = forbidden_path_reason(path_text)
        if reason:
            findings.append(Finding(path_text, None, reason))
            continue
        try:
            data = (root / path_text).read_bytes()
        except OSError as exc:
            findings.append(Finding(path_text, None, f"cannot read tracked file: {exc}"))
            continue
        findings.extend(scan_content(path_text, data))
    return findings


def scan_history(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    names = run_git(
        root, "log", "--all", "--name-only", "--pretty=format:"
    ).decode("utf-8", errors="surrogateescape")
    for path_text in sorted(set(names.splitlines())):
        path_text = path_text.strip()
        if not path_text:
            continue
        reason = forbidden_path_reason(path_text)
        if reason:
            findings.append(Finding(f"history:{path_text}", None, reason))

    patch = run_git(
        root,
        "log",
        "--all",
        "-p",
        "--full-history",
        "--no-ext-diff",
        "--no-color",
    )
    for rule, pattern in HIGH_CONFIDENCE_PATTERNS.items():
        if pattern.search(patch):
            findings.append(Finding("<all reachable Git history>", None, rule))
    return findings


def deduplicate(findings: list[Finding]) -> list[Finding]:
    return sorted(
        set(findings),
        key=lambda item: (item.path, item.line or 0, item.rule),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history",
        action="store_true",
        help="also scan all commits reachable from local branches and tags",
    )
    args = parser.parse_args()

    try:
        root = repository_root()
        findings = scan_tracked_tree(root)
        if args.history:
            findings.extend(scan_history(root))
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    findings = deduplicate(findings)
    if not findings:
        scope = (
            "tracked/unignored files and reachable history"
            if args.history
            else "tracked and unignored files"
        )
        print(f"OK: no likely secrets found in {scope}.")
        return 0

    print("Potential secret exposure detected (matching values are intentionally hidden):")
    for finding in findings:
        location = finding.path
        if finding.line is not None:
            location = f"{location}:{finding.line}"
        print(f"- {location}: {finding.rule}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
