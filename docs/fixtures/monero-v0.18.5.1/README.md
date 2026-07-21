<!--
SPDX-FileCopyrightText: Copyright (c) 2026 Guoqiang Liu

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Monero v0.18.5.1 non-empty cold-signing fixture

This directory freezes the first non-empty unsigned/signed pair produced by
Monero's upstream `cold_signing` functional test. The two `.hex` files contain
ASCII hexadecimal split across lines; concatenate whitespace and hex-decode to
recover the exact files passed through wallet RPC.

## Provenance

- Source: Monero `v0.18.5.1`, commit
  `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`.
- Generator: the unmodified test flow in
  `tests/functional_tests/cold_signing.py`, with print-only instrumentation for
  the private test view key and the two RPC hex fields.
- Runtime: the
  [official Windows CLI archive](https://www.getmonero.org/downloads/)
  `monero-win-x64-v0.18.5.1.zip`.
- Archive SHA-256:
  `cf2ae8273977697d9ef2031c7337b781e6e5936578f602444b2990a173a2437d`,
  matching the value published in Monero's
  [signed hash list](https://www.getmonero.org/downloads/hashes.txt).
- Network: isolated `regtest`, fixed difficulty `10`, KDF rounds `1`.
- Public test seed: `velvet lymph giddy number token physics poetry unquoted
  nibs useful sabotage limits benches lifestyle eden nitrogen anvil fewest
  avoid batch vials washing fences goat unquoted`.
- Private test view key:
  `49774391fa5e8d249fc2c5b45dadef13534bf2483dede880dac88f061e809100`.
- Account address:
  `42ey1afDFnn4886T7196doS9GPMzexD9gXpsZJDwVjeRVdFCSoHnv7KPbBeGpzJBzHRCAs9UxqeoyFQMYbqSWYTfJJQAWDm`.

The seed and view key are public test material. They MUST NOT be used for
production funds.

## Exact files

| File | Bytes | SHA-256 | IV |
| --- | ---: | --- | --- |
| `unsigned_monero_tx.hex` | 3,204 | `0a68ca780e5833d2808b07b4cd58a6519bc128b8e7197126bd4292602f315ead` | `92614faa5817eb3b` |
| `signed_monero_tx.hex` | 8,522 | `e09504167ea03340172079ca58a711186860b7d41fe38c82e008fbd36c14ebb6` | `d674b7c738e258a2` |

The unsigned file begins with `Monero unsigned tx set || 05`; the signed file
begins with `Monero signed tx set || 05`. The IV is the next eight bytes in
each file. The final 64 bytes are the authentication signature.

## Verified lifecycle

The upstream harness completed all assertions and reported
`[TEST PASSED] cold_signing` and `Done, 1/1 tests passed`. For this first pair it
verified:

- the cold wallet accepted and described one unsigned transaction;
- the recipient amount was `1,000,000,000,000` atomic units, ring size was
  `16`, and unlock time was `0`;
- the cold wallet returned one signed transaction and transaction hash;
- the watch-only wallet accepted that exact signed set into its mempool; and
- the transaction confirmed after the regtest daemon mined one block.

The command was:

```shell
python3 tests/functional_tests/functional_tests_rpc.py \
  python3 "$PWD/tests/functional_tests" "$PWD/build/release" cold_signing
```

To verify a fixture digest on a Unix-like host:

```shell
tr -d '[:space:]' < unsigned_monero_tx.hex | xxd -r -p | sha256sum
tr -d '[:space:]' < signed_monero_tx.hex | xxd -r -p | sha256sum
```

Exact encrypted bytes are reference vectors, not canonical writer output.
Fresh runs may use different IVs, signatures, transaction randomness, and
unordered-map iteration order. Compare decoded semantics when generating a new
pair.
