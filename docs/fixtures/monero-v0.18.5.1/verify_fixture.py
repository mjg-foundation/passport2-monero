#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2026 Guoqiang Liu
# SPDX-License-Identifier: GPL-3.0-or-later

"""Verify the frozen Monero cold-signing file vectors with the stdlib."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
VECTORS = {
    "unsigned_monero_tx.hex": {
        "bytes": 3_204,
        "sha256": "0a68ca780e5833d2808b07b4cd58a6519bc128b8e7197126bd4292602f315ead",
        "magic": b"Monero unsigned tx set",
        "version": 5,
        "iv": bytes.fromhex("92614faa5817eb3b"),
    },
    "signed_monero_tx.hex": {
        "bytes": 8_522,
        "sha256": "e09504167ea03340172079ca58a711186860b7d41fe38c82e008fbd36c14ebb6",
        "magic": b"Monero signed tx set",
        "version": 5,
        "iv": bytes.fromhex("d674b7c738e258a2"),
    },
}


def read_hex(path: Path) -> bytes:
    text = path.read_text(encoding="ascii")
    compact = "".join(text.split())
    if len(compact) % 2 or re.fullmatch(r"[0-9a-fA-F]*", compact) is None:
        raise ValueError(f"{path.name}: invalid hexadecimal text")
    return bytes.fromhex(compact)


def verify(name: str, expected: dict[str, object]) -> None:
    data = read_hex(HERE / name)
    magic = expected["magic"]
    assert isinstance(magic, bytes)
    version = expected["version"]
    assert isinstance(version, int)
    iv = expected["iv"]
    assert isinstance(iv, bytes)

    prefix = magic + bytes([version])
    digest = hashlib.sha256(data).hexdigest()
    ciphertext_size = len(data) - len(prefix) - len(iv) - 64

    assert len(data) == expected["bytes"], f"{name}: wrong byte length"
    assert digest == expected["sha256"], f"{name}: wrong SHA-256"
    assert data.startswith(prefix), f"{name}: wrong magic or outer version"
    assert data[len(prefix) : len(prefix) + len(iv)] == iv, f"{name}: wrong IV"
    assert ciphertext_size > 0, f"{name}: empty or truncated ciphertext frame"

    print(
        f"OK {name}: {len(data)} bytes, sha256={digest}, "
        f"version={version}, ciphertext={ciphertext_size} bytes"
    )


def main() -> None:
    for name, expected in VECTORS.items():
        verify(name, expected)


if __name__ == "__main__":
    main()
