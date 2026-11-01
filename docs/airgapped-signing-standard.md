# Airgapped Signing Standard (Draft v0)

Status: **Draft** — for review by core wallet and hardware wallet developers.

This document formalizes the offline/airgapped Monero signing flow and the wire
formats used by it. It exists because the only prior references were a Stack
Exchange answer and monerodocs.org, which is not a sufficient basis for building
interoperable mobile and airgapped wallets.

The document has two parts:

1. **Part A — The de-facto wallet2 format.** A complete description of what
   `monero-wallet-cli` actually writes to `unsigned_monero_tx` and
   `signed_monero_tx` today. This is what existing wallets must remain
   compatible with.
2. **Part B — A proposed minimal portable format.** A much smaller,
   self-describing, QR-friendly payload intended for constrained airgapped
   devices (e.g. Passport). This is the part that needs ratification.

---

# Part A — The de-facto wallet2 format

## A.1 Terminology

| Term | Meaning |
| --- | --- |
| **Hot wallet** | Online, fully synced view-only (watch-only) wallet with a node. Holds the private *view* key. |
| **Cold wallet** | Offline, airgapped wallet holding the private *spend* key. No blockchain, no key image cache. |
| `unsigned_monero_tx` | Default file written by `transfer` on the hot wallet. |
| `signed_monero_tx` | Default file written by `sign_transfer` on the cold wallet. |

## A.2 The UX flow being standardized

This is the flow users are recommended to follow, and the flow every
implementation must interoperate with:

1. **Hot wallet:** `transfer <address> <amount>` (or `sweep_all`). The CLI writes
   `unsigned_monero_tx` to disk. Nothing is broadcast.
2. **Transfer** the file to the airgapped machine (SD card, QR, USB, …).
3. **Cold wallet:** `sign_transfer`. The wallet parses the file, prints the
   decoded transaction details, and asks the user to confirm. On confirmation it
   writes `signed_monero_tx`.
4. **Transfer** `signed_monero_tx` back to the online machine.
5. **Hot wallet:** `submit_transfer`. The wallet re-reads the signed file,
   imports the key images into its cache, and broadcasts the transaction.

Notes:

* The hot wallet must be able to *recognize* the outputs it created after
  `submit_transfer`, so it stores the per-transaction secret keys
  (`tx_key`, additional tx keys) in its cache on step 1.
* The cold wallet never needs a chain, and never needs a key image cache;
  key images are computed from the spend key and the real input's
  `Hp(P)`.
* Transaction details (destination, amount, fee) MUST be displayed on the cold
  device prior to signing. Any implementation that cannot render the full
  destination list is non-conforming.

## A.3 Container: `unsigned_monero_tx`

```
offset  size            field
0       N               magic prefix: ASCII "Monero unsigned tx set" + 0x03
N       ...             epee portable-storage serialization of
                        wallet2::unsigned_tx_set, ChaCha20-encrypted with a
                        key derived from the wallet's private view key
```

* For multisig wallets the magic is `"Monero multisig unsigned tx set"` + 0x01.
* The trailing byte after the magic is the **format version** (currently 3 for
  the single-signature unsigned set, 1 for the multisig set). A parser MUST
  reject versions it does not know.
* Everything after the magic/version is a single encrypted blob. There is no
  length prefix: the blob runs to EOF.
* The encryption key is the ChaCha20 key derived from the *private view key*
  (`generate_chacha_key(view_secret_key)`). Consequence: the cold wallet must
  hold the private view key to read the file. This is why watch-only wallets
  cannot sign and why the cold wallet must know the view key even though it is
  online-wallet material in most other contexts.

### A.3.1 Encoded structure

`wallet2::unsigned_tx_set` (source of truth: `src/wallet/wallet2.h`) contains, in
serialization order:

* `txes` — `vector<tx_construction_data>`, one entry per transaction in the
  batch (a `sweep_all` may produce several).
* `transfers` — `vector<transfer_details>`, the full wallet-side record of every
  selected output: amount, global output index, tx id, public key, commitment
  mask, `tx_pubkey`, `tx_pubkey_derivation`, subaddress index, spent flag, etc.
* `selected_transfers` — indices into `transfers` used by the batch.

Each `tx_construction_data` carries:

* `sources` — `vector<tx_source_entry>`; for each real input: the ring of
  `{public key, commitment}` pairs, `real_output` (index into the ring),
  `real_out_tx_key`, `real_out_additional_tx_keys`, `real_output_in_tx_index`,
  `amount`, `rct` flag, `mask`.
* `splits` — the `{amount, destination, is_subaddress, is_integrated}` outputs.
* `change_dts` — the change destination, or empty.
* `use_rct`, `use_bulletproofs` (or `rct_type`), `unlock_time`, `extra`.
* `subaddresses` — index map needed to recognize self-payments.

Because `transfers` and `txes[].sources` overlap heavily, the serialized blob
contains the same output data many times over.

## A.4 Container: `signed_monero_tx`

```
offset  size            field
0       N               magic prefix: ASCII "Monero signed tx set" + 0x03
N       ...             epee portable-storage serialization of
                        wallet2::signed_tx_set, ChaCha20-encrypted with the
                        view-key-derived key
```

`wallet2::signed_tx_set` contains:

* `ptx` — `vector<pending_tx>`: for every transaction of the batch, the
  constructed transaction blob plus the per-input key material needed to finish
  it (`tx_key`, `additional_tx_keys`, `dust`, `fee`, `change`, `construction_data`).
* `key_images` — the key images for the spent inputs, so `submit_transfer` can
  insert them into the hot wallet's cache without a rescan.
* `tx_key_images` — map used to associate key images with their outputs.

## A.5 Epee portable storage encoding (summary)

Both files are serialized with epee's *portable storage* (binary) format. Full
specification: <https://github.com/jeffro256/serde_epee/blob/master/PORTABLE_STORAGE.md>.
The rules that matter for a parser are:

* Integers are **varints** (LEB128), so a `uint64_t` field occupies 1–10 bytes.
* `std::string` / `std::vector<char>` prefixed by varint length.
* Optional/absent fields are signalled by a varint `0` length or a single
  presence byte, depending on the field kind.
* Structs serialize their members in declaration order with no delimiters and no
  field names; there is **no schema**, no self-description and no forward
  compatibility. Any change to `wallet2.h` silently changes the format.

## A.6 Why this is not a good airgap transport

1. **It is not a format, it is a memory dump.** `unsigned_tx_set` includes the
   wallet's own state (`transfers`) that is irrelevant to signing. It is
   explicitly *not* designed to be portable.
2. **It is wallet2-internal.** Any refactor of `wallet2.h` is a breaking change.
   A hardware implementation must pin and mirror exact struct versions.
3. **It is unbounded in size.** There is no bound on the number of transfers or
   ring members, so a hostile or merely large hot wallet can hand the cold
   device a file far larger than its RAM. Size MUST be bounded and validated
   before the body is parsed.
4. **The confidentiality story is weak for an airgap.** The whole payload is
   encrypted under a view-key-derived key with no authentication tag, so a
   malleability/corruption check must be done structurally after decryption.
5. **It uses the private view key on the signing device.** Necessary for this
   format, but avoidable in a purpose-built format (see Part B), where the
   device only needs output public keys and commitments.

## A.7 Size budget

The signing-relevant data is small. For a 2-input, 2-output RingCT
(bulletproofs, ring size 16) transaction, the information the cold device
actually needs is:

| Item | Size |
| --- | --- |
| Transaction header (version, unlock time, fee, RCT type, extra) | ~150 B |
| Per input: real output key + commitment + amount | ~72 B |
| Per input: 16 ring members × (pubkey 32 + commitment 32) | ~1 KiB |
| Per input: global output indices (16 × varint ≈ 8) | ~128 B |
| Per output: destination (68) + amount (8) | ~80 B |

Total: **under 3 KiB** for a typical 2-in/2-out transaction.

What must travel back is one CLSAG per input: a 32-byte `D`, a 32-byte `s0`,
and `ring_size` 32-byte scalars — 608 bytes per input at ring size 16. So a
2-input signature set is ~1.2 KiB.

Both directions therefore fit in a small number of QR codes; the existing
`unsigned_monero_tx` does not, which is the core motivation for Part B.

---

# Part B — Proposed portable airgapped signing payload (v0)

This section is the part requiring ratification. It is a *new* format, not a
re-encoding of wallet2 internals. It deliberately carries only the data needed
to produce and verify CLSAG signatures, plus enough context for the device to
show the user what they are signing.

## B.1 Goals

* Fits in ≤ 3 KiB for 2-in/2-out; chunkable over QR.
* Requires only the private spend key on the signing device (never the view key).
* Self-describing: versioned, length-delimited, checksummed.
* Deterministic and canonical: one encoding per transaction, so the signature
  is bound to a byte string that both sides can recompute.
* Forward compatible: unknown extension blocks are skipped, not rejected.

## B.2 Framing

All multi-byte integers are **big-endian**, fixed width (not varint), so that
parsing is constant time and offsets are computable. Scalars and points are the
32-byte compressed encodings used by `crypto::secret_key` / `crypto::public_key`.

```
frame header (9 bytes)
  0      u8    magic 0x4D  ('M')
  1      u8    magic 0x58  ('X')
  2      u8    format version (0x00)
  3      u8    message type: 0x01 = unsigned tx, 0x02 = signature set
  4      u8    chunk index (0-based)
  5      u8    chunk count (1..255)
  6-7    u16   payload length of this chunk
  8      u8    reserved, must be 0
payload (payload length bytes)
  9      4     chunk data … (see below)
last bytes of final chunk:
  n-4    u32   CRC-32 (IEEE) over the reassembled payload
```

Reassembly rules:

* Chunks may arrive in any order; duplicate indices with identical content are
  tolerated, conflicting duplicates are an error.
* The reassembled payload MUST be rejected if larger than 8192 bytes.
* CRC-32 is verified before any further parsing.

## B.3 Message type 0x01 — unsigned transaction

```
 0    u8    network (0 = mainnet, 1 = testnet, 2 = stagenet)
 1    u8    rct_type (0 = RingCT/bulletproofs, 1 = RingCT/bulletproofs+, 2 = CLSAG/bulletproofs+)
 2    u8    tx version
 3    u8    input count (1..255)
 4    u8    output count (1..255)
 5    u64   fee (atomic units)
13    u64   unlock_time
21    u8    extra length
22    ..    extra bytes (tx pubkey, additional tx pubkeys, nonce)
```

Then, for each input:

```
  u8    ring size (must be >= 2 and <= 32)
  u64   amount of the real input (0 if unknown to the hot wallet)
  32    real output one-time public key  P
  32    real output commitment mask
  32    real out tx key
  32    real out additional tx key (or all-zero if absent)
  8     real output index within that tx
  8     global output index of the real output
  ring size × {
    32  ring member one-time public key
    32  ring member commitment
  }
```

Then, for each output:

```
  u8    flags (bit0 = is_subaddress, bit1 = is_change, bit2 = is_integrated)
  32    destination spend public key
  32    destination view public key
  64    destination payment id (integrated addresses only; 8 bytes used)
  8     amount
```

The signing device MUST recompute and display the total output amount plus fee
and MUST reject the transaction if they do not balance against the sum of the
input commitments it can verify.

## B.4 Message type 0x02 — signature set

```
 0    u8    input count (must equal the unsigned message's input count)
 1    32    hash of the unsigned payload this set signs (BLAKE2b-256 of the
            reassembled unsigned payload, CRC excluded)
33    for each input, in the same order as message 0x01:
   32   D   (CLSAG key-image binding point)
   32   s0
   ring size × 32  s_i
 32   key image of each input, appended after all signature vectors
 ...  (input count × 32 bytes)
```

A verifier MUST check the payload hash matches the unsigned transaction it
issued, that ring sizes match, and that the key images are non-zero and
distinct.

## B.5 Interoperability with wallet2

This format is a *transport*. An implementation bridging to
`monero-wallet-cli` must:

* Build the `unsigned_tx_set` from its own state on the hot side; and
* On the cold side, either sign natively and return B.4, or convert to
  `signed_monero_tx`.

Until a core-wallet-side implementation exists, the bridging direction is
hot wallet → B.3 → cold device → B.4 → hot wallet, with the hot wallet never
needing to read `unsigned_monero_tx` at all.

---

# Part C — Conformance

An implementation claiming conformance MUST:

1. Implement Part A parsing for at least the single-signature version 3 prefix
   set (read and write), or explicitly declare Part A read-only support.
2. Reject any Part A file whose magic/version is unknown, whose decrypted body
   is truncated, or whose declared counts exceed implementation limits.
3. Display the full destination list and total amount + fee before signing.
4. Implement Part B framing with CRC-32 and the 8192-byte payload cap.

# Part D — Open items

* Exact field ordering of `unsigned_tx_set` / `signed_tx_set` for the current
  wallet2 release, captured as test vectors (hex) in `docs/airgapped-vectors/`.
* Measured sizes of real `unsigned_monero_tx` files for 1-in/1-out and
  2-in/2-out to replace the estimates in A.7.
* Ratification of Part B by a core wallet developer, or by two independent
  wallet developers.

# References

* `src/wallet/wallet2.h`, `src/wallet/wallet2.cpp` — `unsigned_tx_set`,
  `signed_tx_set`, `save_tx`, `sign_tx`, `submit_transfer`.
* Epee portable storage: <https://github.com/jeffro256/serde_epee/blob/master/PORTABLE_STORAGE.md>
* Feather offline signing guide: <https://docs.featherwallet.org/guides/offline-tx-signing>
* Offline signing details: <https://monero.stackexchange.com/a/2916>
* CLSAG: <https://eprint.iacr.org/2019/654>
