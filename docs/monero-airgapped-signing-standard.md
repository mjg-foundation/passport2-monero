<!--
SPDX-FileCopyrightText: 2026 MAWXHUB

SPDX-License-Identifier: GPL-3.0-or-later
-->

# MASS-1: Monero Airgapped Signing Standard

Status: Draft for review

Scope: Passport Monero firmware, companion desktop/mobile wallets, and tooling that
needs to exchange Monero cold-signing payloads without a network connection.

## Goals

MASS-1 defines a minimal interoperable flow for Monero airgapped signing:

1. An online wallet with the address and private view key prepares an unsigned
   transaction set.
2. Passport or another offline signer validates the request and signs it with
   the spend key.
3. The online wallet imports the signed transaction set and submits it.
4. The online wallet and offline signer keep output and key-image state in sync.

The first version intentionally reuses the existing Monero wallet payloads rather
than inventing a new transaction format. This keeps the standard compatible with
`monero-wallet-cli` and `monero-wallet-rpc` while giving QR and microSD
transports a common envelope.

## Non-Goals

- Defining a replacement for Monero consensus transaction serialization.
- Reimplementing wallet output selection on Passport.
- Supporting multisig payloads in this draft.
- Treating a view-only wallet as trusted. The signer must display enough details
  for user approval.

## Actors

- Online wallet: A view-only wallet that can scan the chain, build unsigned
  transaction sets, import key images, and submit signed transaction sets.
- Offline signer: Passport or another device that holds the spend key and can
  parse, display, sign, and export payloads without network access.
- Transport: microSD file transfer, single QR, or animated QR using UR 2.0.

## Existing Monero Payloads

MASS-1 treats these Monero payloads as authoritative:

| Payload | Producer | Consumer | Purpose |
| --- | --- | --- | --- |
| `unsigned_txset` / `unsigned_monero_tx` | Online wallet | Offline signer | Transaction request for signing |
| `signed_txset` / `signed_monero_tx` | Offline signer | Online wallet | Signed transaction set for submission |
| `outputs` | Online wallet | Offline signer | Output data needed for key-image generation |
| `key_images` | Offline signer | Online wallet | Key images so the view-only wallet can track spends |

The CLI flow is documented by Monero Docs: a transfer from a view-only wallet
creates `unsigned_monero_tx`, `sign_transfer` creates `signed_monero_tx`, and
`submit_transfer` broadcasts it. The same guide documents the output/key-image
round trip using `export_outputs`, `import_outputs`, `export_key_images`, and
`import_key_images`.

The wallet RPC flow exposes equivalent strings. `transfer` and related calls can
return an `unsigned_txset`; `sign_transfer` accepts that string and returns a
`signed_txset`; `submit_transfer` accepts the signed data as `tx_data_hex`.

In the current Monero wallet implementation, unsigned sets are serialized
`wallet2::unsigned_tx_set` objects and signed sets are serialized
`wallet2::signed_tx_set` objects. Both have magic prefixes in wallet2:

- `Monero unsigned tx set\005`
- `Monero signed tx set\005`

The current unsigned payload contains transaction construction data plus exported
wallet outputs. The signed payload contains pending transactions, key images, and
transaction-output key-image mapping data. Payload internals are versioned by the
Monero implementation and should be parsed through Monero wallet-compatible code,
not by ad-hoc byte offsets.

## MASS-1 Envelope

Every QR or file transport should wrap exactly one Monero payload in a small
metadata envelope:

```json
{
  "standard": "MASS-1",
  "network": "mainnet",
  "payload_type": "monero.unsigned_txset",
  "payload_encoding": "hex",
  "payload": "<hex string>",
  "source": "wallet-name/version",
  "created_at": "2026-06-10T00:00:00Z"
}
```

### Required Fields

- `standard`: Literal `MASS-1`.
- `network`: One of `mainnet`, `stagenet`, or `testnet`.
- `payload_type`: One of the values in the table below.
- `payload_encoding`: `hex` for wallet RPC strings or `binary` for raw files.
- `payload`: Payload bytes encoded according to `payload_encoding`.

### Optional Fields

- `source`: Human-readable source wallet and version.
- `created_at`: UTC timestamp for user display and troubleshooting.
- `account`: Wallet account index if known.
- `note`: Human-readable text. Must never be required for parsing.

### Payload Types

| Type | Contents |
| --- | --- |
| `monero.unsigned_txset` | Hex or binary data matching Monero unsigned tx set |
| `monero.signed_txset` | Hex or binary data matching Monero signed tx set |
| `monero.outputs` | Output export payload |
| `monero.key_images` | Key-image export payload |

## Transport Rules

### microSD

For microSD, write the envelope as UTF-8 JSON with one of these filenames:

- `monero-unsigned-txset.mass1.json`
- `monero-signed-txset.mass1.json`
- `monero-outputs.mass1.json`
- `monero-key-images.mass1.json`

The receiver may also accept legacy Monero filenames (`unsigned_monero_tx`,
`signed_monero_tx`, `outputs`, `key_images`) and wrap them internally as MASS-1.

### QR / Animated QR

For QR transport, encode the same JSON bytes with UR 2.0. The UR type should be:

- `crypto-monero-unsigned-tx`
- `crypto-monero-signed-tx`
- `crypto-monero-outputs`
- `crypto-monero-key-images`

Animated QR senders should preserve the JSON bytes exactly before UR encoding.
Receivers should reject payloads that decode to invalid JSON, unsupported
`standard`, unsupported `network`, unsupported `payload_type`, or malformed hex.

## Signing Flow

### Online Wallet

1. Sync the view-only wallet.
2. Build the transfer with `do_not_relay=true` and request an unsigned set, or
   use the CLI workflow that writes `unsigned_monero_tx`.
3. Wrap the unsigned payload as `monero.unsigned_txset`.
4. Transfer the envelope to Passport.

### Passport / Offline Signer

1. Decode the MASS-1 envelope.
2. Verify that `network` matches the wallet.
3. Parse the Monero unsigned set with wallet-compatible code.
4. Display at minimum:
   - network
   - destination address or addresses
   - amount per destination
   - fee
   - change address when present
   - number of inputs and ring size when available
5. Require explicit user approval.
6. Sign with the spend key.
7. Export a `monero.signed_txset` envelope.

### Online Wallet Submission

1. Decode the signed envelope.
2. Submit the signed set through `submit_transfer` or CLI `submit_transfer`.
3. Export outputs to the offline signer.
4. Import key images returned by the offline signer.

## Output and Key-Image Sync

An offline signer cannot safely sign future spends without output context. After
submitting a transaction, the online wallet should export new outputs and send
them to the signer. The signer should import those outputs, generate key images,
and export key images back to the online wallet.

For recovery or when state is uncertain, the online wallet should export all
outputs and the offline signer should export all key images. This mirrors the
Monero CLI restoration guidance.

## Validation Requirements

Implementations must reject:

- Unknown `standard` values.
- Unknown `network` values.
- Payloads whose network does not match the active wallet.
- Unknown `payload_type` values.
- Invalid hex when `payload_encoding` is `hex`.
- Binary payloads whose Monero magic prefix is not appropriate for the declared
  `payload_type`.
- Unsigned transactions that cannot be displayed to the user with destination,
  amount, and fee.

Implementations should warn when:

- The fee is unexpectedly high.
- There are multiple destination outputs.
- The transfer uses a payment ID or integrated address.
- The payload was produced by an unknown wallet version.

## Security Notes

- The online wallet can be compromised, so Passport must not blindly sign any
  payload.
- The signer display is the trust boundary. Destination, amount, fee, and network
  must be shown before approval.
- The signer should never export spend secrets, view secrets, seeds, or raw wallet
  cache data.
- The signed transaction set is safe to move to the online wallet, but submitting
  it reveals transaction data to the node used for broadcast.
- Key images reveal spend status. They are necessary for view-only wallet balance
  correctness, but should still be transferred only to the intended wallet.

## Compatibility Plan

1. Accept legacy Monero CLI files for import.
2. Add MASS-1 JSON wrappers for QR and microSD interoperability.
3. Use Monero wallet-compatible parsing for tx set internals.
4. Keep payload parsing version-aware so Monero upstream format changes can be
   handled by updating the parser rather than changing the envelope.

## Open Questions for Review

- Should the QR UR type use `crypto-monero-*` names or a single
  `crypto-monero` type with `payload_type` inside the JSON?
- Should `created_at` be mandatory for replay/troubleshooting, or optional for
  deterministic fixtures?
- Should the first Passport implementation support raw legacy binary files only,
  RPC hex strings only, or both?
- Which Monero core or wallet developers should be asked to sign off on this
  draft before MASS-1 is treated as stable?

## References

- Monero Docs: Offline Transaction Signing,
  https://docs.getmonero.org/cold-storage/offline-transaction-signing/
- Monero wallet RPC guide: `transfer`, `sign_transfer`, and `submit_transfer`,
  https://www.getmonero.org/resources/developer-guides/wallet-rpc.html
- Monero source: `wallet2::unsigned_tx_set`, `wallet2::signed_tx_set`, and
  tx-set load/sign/parse methods,
  https://github.com/monero-project/monero/blob/master/src/wallet/wallet2.h and
  https://github.com/monero-project/monero/blob/master/src/wallet/wallet2.cpp
- Blockchain Commons UR,
  https://github.com/BlockchainCommons/Research/blob/master/papers/bcr-2020-005-ur.md
