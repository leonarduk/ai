"""Smoke test: the avatar package and its submodules import cleanly."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_avatar_package_imports():
    importlib.import_module("avatar")


def test_avatar_submodules_import():
    for module_name in ["context", "llm", "tools", "guardrails", "styles"]:
        importlib.import_module(f"avatar.{module_name}")
