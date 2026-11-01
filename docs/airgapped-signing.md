# Airgapped Monero Transaction Signing — Format Specification

| Field | Value |
| --- | --- |
| Title | Airgapped Monero Transaction Signing |
| Status | Draft / Request for Comments |
| Version | 0.1 |
| Scope | `passport2-monero`, mobile wallets, `monero-wallet-cli` interop |

## 1. Abstract

This document specifies, in a BIP-style manner, how an offline ("airgapped")
device signs a Monero transaction that was constructed on a network-connected
machine.

It does two things:

1. It documents the **existing** `monero-wallet-cli` on-disk formats
   (`unsigned_monero_tx`, `signed_monero_tx`) precisely enough to implement a
   reader/writer for them (§5).
2. It specifies a **minimal, portable, transport-agnostic envelope** (§6) for the
   same information, suitable for QR-code / SD-card / audio transport between a
   hot wallet and a constrained hardware signer such as Passport2.

Implementations MAY support either format. A wallet that implements §6 MUST also
be able to export/import the §5 format, so that it interoperates with
`monero-wallet-cli` and with wallets that only speak the legacy format.

## 2. Motivation

Cold signing is supported by `monero-wallet-cli` today, but the format is
undocumented outside of a handful of StackExchange answers, and the reference
file format is a serialization of `wallet2` internals — a "kitchen sink" that
carries wallet state, an address book, and a transfer cache in addition to the
data actually required to produce a signature.

For a hardware signer this is undesirable:

* the file can be large (well beyond a single QR code),
* the payload layout tracks `wallet2` internals and therefore changes with it,
* much of the payload is not needed to sign and is not authenticated by the
  user's confirmation screen.

The goal of this document is interoperability: mobile wallets, hardware wallets
and `monero-wallet-cli` should not each invent a slightly different dialect of
the same exchange.

## 3. Terminology

* **Hot wallet** — a view-only wallet running on a network-connected machine with
  a fully synced node. It builds transactions but holds no spend key.
* **Cold wallet** — a wallet holding the spend key on an airgapped machine. It
  does not need a blockchain, and does not need key images for its own outputs
  (they are computed during signing).
* **Signer** — the cold wallet.
* **Coordinator** — the hot wallet.
* **Request** — the message sent from coordinator to signer.
* **Response** — the message sent from signer back to coordinator.

`MUST`, `MUST NOT`, `SHOULD`, `MAY` are used as in RFC 2119.

## 4. High-level flow (informative)

This is the flow assumed by this specification; it matches the behaviour of
`monero-wallet-cli`.

1. The coordinator, using a synced view-only wallet, constructs a transaction and
   writes a **sign request** (default file name `unsigned_monero_tx`).
2. The request is moved to the airgapped machine (SD card, QR frames, …).
3. The signer runs `sign_transfer` (or the equivalent UI): it parses the request,
   displays the transaction details to the user, and on confirmation writes a
   **sign response** (default file name `signed_monero_tx`).
4. The response is moved back to the online machine, which runs
   `submit_transfer` and broadcasts the transaction.

The account model is unchanged: the signer requires the private view key (to
recognise its own outputs and derive commitment masks) and the private spend key
(to produce key images and CLSAG signatures).

## 5. Existing `wallet2` on-disk format (informative, normative for interop)

### 5.1 File layout

Both `unsigned_monero_tx` and `signed_monero_tx` are written by
`wallet2::save_unsigned_tx()` / `wallet2::save_signed_tx()` (see
`src/wallet/wallet2.cpp`, `src/wallet/wallet2.h`).

```text
+-----------------------------+ 0
| magic (ASCII, NUL-free)     |   identifies "Monero Unsigned Tx" / "Monero Signed Tx"
+-----------------------------+
| version (uint32, LE)        |   currently 1
+-----------------------------+
| encrypted payload           |   epee (portable storage) serialization,
|                             |   ChaCha20-encrypted with the private view key
+-----------------------------+
```

Notes:

* The serialization is **epee portable storage** (the same binary format used for
  wallet files and for the daemon RPC in binary mode). A description of the
  format is available at
  <https://github.com/jeffro256/serde_epee/blob/master/PORTABLE_STORAGE.md>.
* The payload is encrypted with `crypto::chacha20` keyed by the wallet's private
  view key, with a zero IV (the `encrypt_with_view_secret_key` helper). It is
  therefore *confidential* only with respect to an attacker who does not have the
  wallet file or the view key — it is **not** a substitute for authenticated
  encryption. Implementations MUST NOT rely on this encryption for integrity.
* Readers MUST reject a file whose magic or version does not match, and MUST NOT
  attempt to parse a truncated payload.

### 5.2 Unsigned payload

The decrypted payload is the epee serialization of
`tools::wallet2::unsigned_tx_set`, which contains (non-exhaustively):

* `txes` — one `tx_construction_data` per transaction being built:
  * `sources` — `tx_source_entry` for every input: amount, the full ring of
    decoy outputs (`{global_index, public_key, commitment}`), the real output's
    index within the ring, the real output's tx key and additional tx keys, and
    the real output's index within its transaction;
  * `splits`, `extra`, `unlock_time`, `use_rct` / RCT type;
  * `destinations` — `{amount, address}` for each payment;
  * change destination, change amount, subaddress account/indices.
* `transfers` — a cache of the wallet's own transfers, plus the index of the
  first transfer not yet known to the signer. **This is a wallet state update,
  not signing data.**
* `address_book` — the coordinator's address book. Not signing data.
* `hw_device_type`, and (in newer versions) per-transaction device aux data.

Because of the transfer cache and address book, the file size is dominated by
wallet state rather than by the transaction. There is no fixed upper bound; a
wallet with a large transfer cache produces a correspondingly large file. A
minimal 2-input/2-output `tx_construction_data` with ring size 16 is on the
order of 2.5 KB, and that is the useful lower bound for the payload.

### 5.3 Signed payload

The decrypted payload is the epee serialization of
`tools::wallet2::signed_tx_set`:

* `ptx` — one `pending_tx` per transaction: the serialized `transaction` plus the
  per-input `tx_key`/derivation data needed to broadcast it;
* `key_images` — the key images produced during signing;
* `tx_device_aux` — opaque per-transaction data from the signer (used for
  hardware-wallet state such as transaction confirmation bookkeeping);
* multisig bookkeeping fields.

### 5.4 Limitations

Implementations SHOULD read §5 for compatibility but SHOULD NOT treat it as the
canonical airgapped format:

* it is a serialization of internals and tracks `wallet2` version changes;
* it carries unrelated wallet state across the airgap (a privacy and attack
  surface concern);
* it does not fit comfortably in a QR code once the transfer cache is non-empty;
* it has no authenticity guarantee — the signer cannot distinguish a request
  produced by its own coordinator from one produced by anyone holding the file.

## 6. Minimal airgapped envelope (normative)

### 6.1 Framing

Every message is a single envelope:

```text
+--------+---------+--------+------------------+-----------------+
| magic  | version | type   | payload_length   | payload         |
| 4 B    | 1 B     | 1 B    | varint           | payload_length  |
+--------+---------+--------+------------------+-----------------+
```

* `magic` = ASCII `P2AS` (bytes `50 32 41 53`).
* `version` = `0x01` for this document.
* `type` = `0x01` (SIGN_REQUEST) or `0x02` (SIGN_RESPONSE). Other values MUST be
  rejected.
* `payload_length` is a varint (§6.2) and MUST equal the number of remaining
  bytes exactly; trailing bytes MUST be rejected.

Example: an empty 2-byte payload of type SIGN_REQUEST begins
`50 32 41 53 01 01 02`.

### 6.2 Encoding primitives

* **Integers** are unsigned little-endian. `varint` is the LEB128 used by Monero
  (7 bits per byte, high bit = continuation).
* **Fixed-width fields** are written without a length prefix: public keys,
  scalars and hashes are 32 bytes.
* **Variable-length fields** are `varint length` followed by `length` bytes.
* **Addresses** are the full 69-byte Monero address (network byte, 32-byte spend
  public key, 32-byte view public key, 4-byte checksum). The signer MUST verify
  the checksum and MUST reject an address whose network byte does not match the
  requested network.
* All amounts are in atomic units (1 XMR = 10^12).

### 6.3 SIGN_REQUEST payload

```text
network                 u8     0 = mainnet, 1 = testnet, 2 = stagenet
rct_type                u8     ringct type of the transaction being built
unlock_time             varint
request_id              32 B   see below
tx_private_key          32 B   the transaction secret key `r`
extra                   varint length + bytes (contains the tx public key `rG`)
num_inputs              varint
  for each input:
    amount              8 B    decrypted amount of the real input
    real_output_index   varint index of the real output within the ring
    real_out_tx_key     32 B   transaction public key of the real output's tx
    num_addl_tx_keys    varint
      additional_tx_key 32 B   (one per entry)
    real_out_in_tx      varint index of the real output within its transaction
    ring_size           varint MUST be >= 2
      for each ring member:
        global_index    varint
        public_key      32 B
        commitment      32 B
num_destinations        varint
  for each payment:
    amount              8 B
    address             69 B
has_change              u8     0 or 1
  if 1:
    change_amount       8 B
    change_address      69 B
num_additional_data     varint (reserved; MUST be 0 in version 1)
```

`request_id` is `Keccak-256` of the payload bytes from `network` up to and
including `extra`, i.e. of the canonical encoding of everything the user is asked
to approve. It binds the response to the request and lets the coordinator detect
that the signer was shown a different transaction than the one it built.

The signer MUST:

* reject a request whose `num_inputs` or `ring_size` exceeds its resource budget
  before allocating,
* reject a ring in which `real_output_index >= ring_size`,
* display every destination amount and address, plus the total fee, before
  signing.

### 6.4 SIGN_RESPONSE payload

```text
request_id              32 B   echoed from the request
network                 u8     echoed
num_inputs              varint MUST equal the request's num_inputs
  for each input:
    key_image           32 B
    pseudo_out          32 B   commitment produced by the signer
    c1                  32 B   CLSAG initial challenge
    ring_size           varint MUST equal the request's ring_size
      s                 32 B   (ring_size entries)
```

The signer derives the commitment mask for each input with the standard scheme
(`Hs("commitment_mask" || Hs(rA) || output_index)`, where `rA` is the shared
secret between the input's tx key and the wallet's view key) and computes
`pseudo_out = mask*G + amount*H`. The coordinator MUST verify that each
`pseudo_out` is consistent with the sum of the destination amounts plus the fee
before assembling the transaction.

The coordinator MUST verify that `request_id` matches the request it sent, and
MUST reject a response with a different `network` or a mismatched input/ring
count.

Every input must be signed with a distinct key image; a response containing a
repeated key image MUST be rejected.

### 6.5 Wire size

With ring size 16:

* SIGN_REQUEST, 2 inputs / 2 outputs:
  `2 * (8 + 32 + 1 + 1 + 16 * 72) + 2 * 77 + extra ≈ 2.6 KB`
* SIGN_RESPONSE, 2 inputs:
  `2 * (32 + 32 + 32 + 16 * 32) = 1.28 KB`

Both fit in the largest QR symbols, but only just. See §7.

## 7. Transport profiles

Any byte-oriented transport may carry an envelope. Two profiles are defined.

### 7.1 File

The envelope is written verbatim to a file. Recommended file names
`unsigned_monero_tx` / `signed_monero_tx` keep CLI muscle memory, but a `.p2as`
extension SHOULD be used so that the two formats are never confused.

### 7.2 Chunked (QR, audio, manual entry)

A payload larger than the transport's single-frame capacity is split into
frames:

```text
frame_magic      2 B    ASCII "AF"
frame_version    1 B    0x01
total_length     varint total envelope length
payload_hash     32 B   Keccak-256 of the complete envelope
frame_index      varint 0-based
frame_count      varint
frame_length     varint
frame_data       frame_length bytes
```

* The receiver MUST verify `payload_hash` after reassembly and MUST reject the
  payload if it does not match.
* Frames MAY arrive out of order.
* A sender SHOULD prefer many small frames over a single maximal QR code, since
  dense symbols are hard to scan on inexpensive cameras.

## 8. Security considerations

* **Airgap hygiene.** The signer MUST NOT have network, Bluetooth or other
  untrusted I/O enabled while signing. `passport2-monero` treats the absence of
  the network stack as a precondition, not a runtime check.
* **What the user approves.** The `request_id` MUST cover exactly the data shown
  on the confirmation screen. Any field not covered by `request_id` is a
  candidate for a substitution attack.
* **Address and amount display.** The signer MUST independently decode and
  display destination addresses; it MUST NOT display an address supplied in
  rendered form by the coordinator.
* **Encryption is not authentication.** The `wallet2` payload encryption (§5.1)
  uses the view key with a zero IV. Implementations MUST NOT treat successful
  decryption as evidence of authenticity. The envelope in §6 carries no
  encryption at all; confidentiality across the airgap is the user's
  responsibility, and integrity comes from `request_id` plus, optionally, a
  signature by the signer's spend key over the response.
* **Replay.** A coordinator MUST NOT submit the same `SIGN_RESPONSE` twice; the
  network will reject the second broadcast, but the failure mode should be
  detected locally.
* **Resource limits.** A malicious request can specify a very large ring size or
  input count. Limits MUST be enforced before allocation; the signer SHOULD
  enforce a maximum payload size at the transport layer as well.
* **Key images.** A key image produced by the signer is public information once
  the transaction is broadcast; the signer SHOULD track them to avoid
  double-spend attempts being presented as fresh requests.

## 9. Compatibility

An implementation that supports §6 MUST also provide:

* import of `unsigned_monero_tx` (§5.1/§5.2) and export of
  `signed_monero_tx` (§5.1/§5.3), so that `monero-wallet-cli` remains usable as
  the coordinator; and
* export of `unsigned_monero_tx` from a §6 request where possible, for the same
  reason.

Where the two formats disagree, §5 is authoritative for interop and §6 is
informative for new implementations.

### 9.1 Mapping §5 → §6

| §6 field | `wallet2` source |
| --- | --- |
| `network` | `wallet2::nettype()` |
| `rct_type` | `tx_construction_data::use_rct` + `rct::RctType` |
| `unlock_time` | `tx_construction_data::unlock_time` |
| `tx_private_key` | `tx_construction_data::tx_device_aux` / constructed `r` |
| `extra` | `tx_construction_data::extra` |
| input `amount` | `tx_source_entry::amount` |
| input ring | `tx_source_entry::outputs` |
| `real_output_index` | `tx_source_entry::real_output` |
| `real_out_tx_key` | `tx_source_entry::real_out_tx_key` |
| `real_out_in_tx` | `tx_source_entry::real_output_in_tx_index` |
| destinations | `tx_construction_data::destinations` |
| change | `tx_construction_data::change_dts`, `change_amount` |

Fields present in §5 but absent from §6 (`transfers`, `address_book`) are wallet
state and MUST NOT be forwarded to the signer.

## 10. Test vectors

A conforming implementation MUST ship, and this document MUST eventually contain,
vectors for at least:

1. envelope framing: magic/version/type/length for an empty payload and for a
   payload of length 128 (multi-byte varint);
2. a 1-input / 1-output SIGN_REQUEST with ring size 2, and its `request_id`;
3. the corresponding SIGN_RESPONSE, including `key_image` and `pseudo_out`;
4. a rejection vector: trailing byte after the payload;
5. a rejection vector: `request_id` mismatch between request and response;
6. a rejection vector: `real_output_index >= ring_size`.

These are pending a first implementation; the absence of frozen vectors is the
reason this document is `Draft`.

## 11. References

* `monero-project/monero` — `src/wallet/wallet2.cpp`,
  `wallet2::save_unsigned_tx`, `load_unsigned_tx`, `sign_tx`, `submit_transfer`
* `monero-project/monero` — `src/wallet/wallet2.h`,
  `unsigned_tx_set`, `signed_tx_set`, `tx_construction_data`, `tx_source_entry`
* `monero-project/monero` — `src/serialization/` (portable storage / epee)
* <https://github.com/jeffro256/serde_epee/blob/master/PORTABLE_STORAGE.md>
* <https://docs.featherwallet.org/guides/offline-tx-signing>
* <https://monero.stackexchange.com/a/2916>
* BIP-0370 (format reference for how this document is structured)

## 12. Open questions

* Should the signer, rather than the coordinator, generate `tx_private_key`? That
  would remove a value from the airgap and is compatible with §6, but breaks
  byte-compatibility with `wallet2`.
* Should §6 add an optional signature by the signer's spend key over
  `request_id || response payload`, so that the coordinator can prove the
  response came from its own device?
* Multisig signing is explicitly out of scope for version 1.
