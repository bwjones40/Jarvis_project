"""Helpers for reading and searching vault files."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def read_note(vault_path: str, vault_root: str | Path = ".") -> str:
    return _resolve_path(vault_path, vault_root).read_text(encoding="utf-8")


def note_exists(vault_path: str, vault_root: str | Path = ".") -> bool:
    return _resolve_path(vault_path, vault_root).exists()


def search_notes(query: str, vault_root: str | Path = ".", max_results: int = 3) -> list[dict[str, Any]]:
    root = Path(vault_root)
    terms = [term.lower() for term in query.split() if term.strip()]
    if not terms or not root.exists():
        return []

    matches: list[dict[str, Any]] = []
    for path in root.rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        title = _extract_h1(content)
        haystacks = [path.stem.lower(), title.lower(), content.lower()]
        score = sum(sum(term in haystack for haystack in haystacks) for term in terms)
        if score == 0:
            continue
        matches.append(
            {
                "path": path.as_posix(),
                "title": title,
                "content": content,
                "score": float(score) / float(len(terms) * len(haystacks)),
            }
        )

    matches.sort(key=lambda item: (-item["score"], item["path"]))
    return matches[:max_results]


def _resolve_path(vault_path: str, vault_root: str | Path) -> Path:
    path = Path(vault_path)
    if path.is_absolute():
        return path
    return Path(vault_root) / path


def _extract_h1(content: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""
