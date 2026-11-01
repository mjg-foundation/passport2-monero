# Airgapped (Offline) Monero Transaction Signing

Status: Draft / Request for Comments
Applies to: Passport2 firmware, companion mobile wallets, and any tool that
exchanges Monero transactions with an airgapped signer.

This document formalizes the data exchanged during airgapped Monero signing.
It records the format used by `monero-wallet-cli` today, explains why that
format is a poor fit for constrained signers, and specifies a minimal,
portable format that a hot (online, view-only) wallet and a cold (offline,
spend-key-holding) signer can agree on.

---

## 1. Terminology

* **Hot wallet** -- an online, view-only wallet (`--generate-from-view-key`)
  attached to a fully synced node. It can see incoming funds and construct
  transactions, but holds no spend key.
* **Cold wallet** -- an offline wallet holding the spend key. It needs no
  blockchain and no key images. This is the airgapped device (e.g. Passport2).
* **Airgap** -- any channel that moves bytes between the two without a network
  connection (SD card, QR codes, audio, USB drive in a clean room).
* **Unsigned transfer** -- everything the cold wallet needs to produce
  signatures, produced by the hot wallet.
* **Signed transfer** -- the signatures (and enough context to bind them),
  produced by the cold wallet and submitted by the hot wallet.

---

## 2. High-level UX flow

This is the flow every implementation should follow, and it is the flow the
official CLI already implements:

1. On the **hot wallet**, build the transaction. The CLI writes a file named
   `unsigned_monero_tx` by default.
2. Move `unsigned_monero_tx` across the airgap to the **cold wallet**.
3. On the **cold wallet**, run `sign_transfer`. The wallet decodes the file,
   displays the transaction details, and prompts the user to confirm. On
   confirmation it writes `signed_monero_tx` by default.
4. Move `signed_monero_tx` back across the airgap to the **hot wallet** and run
   `submit_transfer`, which broadcasts to the network.

Key property: the cold wallet never needs chain state. Everything required to
sign (ring members, commitments, amounts, destinations) must be present in the
unsigned transfer.

---

## 3. The existing `wallet2` format

The files produced by `monero-wallet-cli` are **not** a documented interchange
format. They are a serialization of internal `wallet2` structures.

### 3.1 Envelope

Both `unsigned_monero_tx` and `signed_monero_tx` use the same envelope:

| Field   | Description                                                        |
|---------|--------------------------------------------------------------------|
| magic   | Project magic bytes identifying a Monero wallet transfer file.     |
| version | Serialization version (varint).                                     |
| body    | EPEE serialization of the corresponding `*_tx_set` structure.      |

The body is **encrypted with the wallet's private view key** in the unsigned
case. This is an integrity/confidentiality measure for the file at rest; it is
not authentication of the sender, and it gives no protection against a
malicious hot wallet that knows the view key.

EPEE is Monero's internal portable-storage binary format. A readable
description of the wire encoding (varints, strings, arrays, nested structs) is
available at:
<https://github.com/jeffro256/serde_epee/blob/master/PORTABLE_STORAGE.md>

### 3.2 `unsigned_tx_set`

The body is a `unsigned_tx_set`, which is large and contains several nested
structures. Conceptually it carries:

1. **Per-input signing data**
   * the real input's key derivation / one-time output key,
   * the amount and commitment,
   * the ring members used for the ring signature: for each of the 16 decoys a
     public key (32 bytes) and a commitment (32 bytes), i.e. `16 * 64` bytes,
   * the key image (or the data required to recompute it),
   * transaction construction flags (RCT type, unlock time, etc.).
2. **Payments**
   * destination address (spend public key + view public key = 64 bytes),
   * amount (8 bytes),
   * roughly 80 bytes per output.
3. **A wallet-state update payload**
   * `tx_construction_data`: selected transfers, change destination, additional
     tx keys, `sources`, `splitted_dsts`, `use_rct`, `unlock_time`, and other
     wallet bookkeeping.

A rough lower bound for a 2-input / 2-output transaction in this format is
`2 * (40 + 16*64) + 2 * 80` bytes of *actual* signing data, under 3 KB. The
real file is substantially larger because of the wallet-state payload and the
EPEE overhead.

### 3.3 `signed_tx_set`

For each signed transaction the cold wallet returns:

* the serialized transaction (`transaction`), and
* the destination list, so the hot wallet can sanity-check what it is about to
  broadcast.

The cryptographic payload that the cold device must actually produce is one
CLSAG per input: `96 + 16 * 32` bytes, i.e. **608 bytes per input**, plus or
minus 32 bytes depending on the exact variant.

### 3.4 Why this is a poor portable standard

* It is a "kitchen sink" of `wallet2` internals, not a designed interchange
  format.
* It is large: it can plausibly exceed the RAM of a constrained signer, and it
  does not fit in a QR code (so the airgap must be a file transfer).
* It couples the signer to the exact internal struct layout and version of the
  online wallet that produced it.
* Decoding is a large attack surface for a security-critical device; the
  signer must treat every field as untrusted.
* The encryption with the view key provides no protection against a
  compromised hot wallet, which is the threat model that matters most.

None of this means `wallet2` compatibility is wrong -- it is required to
interoperate with stock `monero-wallet-cli` -- but it should be an *adapter*,
not the internal representation of the signer.

---

## 4. A minimal portable standard

This section defines a compact format that carries exactly the information a
cold signer needs and nothing else. It is designed so that both the unsigned
transfer and the signed transfer fit in one or two QR codes.

### 4.1 Envelope

All integers are little-endian. `varint` is the unsigned LEB128 used by Monero.

| Field        | Size     | Notes                                          |
|--------------|----------|------------------------------------------------|
| magic        | 4        | ASCII `MXAG` (`0x4D 0x58 0x41 0x47`)           |
| version      | 1        | `1` for this document                          |
| type         | 1        | `1` = unsigned transfer, `2` = signed transfer |
| network      | 1        | `0` mainnet, `1` testnet, `2` stagenet         |
| payload_len  | 4        | Length of the payload in bytes                 |
| payload      | variable | See 4.2 / 4.3                                  |
| crc32        | 4        | CRC-32 of everything above, for corruption     |

The envelope is deliberately unencrypted: the airgapped device must be able to
parse and display the transaction before the user approves it.

### 4.2 Unsigned payload (`type = 1`)

```
uint8   rct_type
varint  unlock_time
varint  num_inputs
repeat num_inputs times:
    bytes32  real_out_tx_pubkey      // one-time output key
    bytes32  real_out_commitment     // Pedersen commitment
    bytes32  key_image
    bytes32  real_out_key_derivation // needed for CLSAG
    varint   real_out_index          // position in the ring
    varint   num_ring_members        // 16 for current ring size
    repeat num_ring_members times:
        bytes32  ring_pubkey
        bytes32  ring_commitment
varint  num_outputs
repeat num_outputs times:
    bytes32  dest_spend_pubkey
    bytes32  dest_view_pubkey
    uint64   amount
    bytes32  commitment
bytes32 additional_tx_key              // or all-zero if none
```

Sizes for a 2-in / 2-out transaction:

* inputs: `2 * (32*4 + 16*(32+32) + small)` ~= 2.4 KB
* outputs: `2 * 104` ~= 208 bytes
* **total well under 3 KB**, encodable as a single QR code.

### 4.3 Signed payload (`type = 2`)

```
bytes32 unsigned_hash        // hash of the unsigned payload that was signed
varint  num_inputs
repeat num_inputs times:
    bytes32 clsag_s0           // 96-byte CLSAG prefix scalar
    bytes32 clsag_s[...]       // 16 ring scalars (32 bytes each)
```

`96 + 16 * 32 = 608` bytes per input, so a 2-input transaction is ~1.3 KB and
fits in one QR code. The `unsigned_hash` binds the signatures to the exact
transaction the user reviewed; a signer MUST refuse to produce signatures for
a payload it did not itself parse and display.

### 4.4 QR / transport encoding

For QR transport the envelope is encoded in uppercase Base32 without padding,
prefixed with `MXAG1:`. Transfers larger than one QR code are split into
numbered chunks of at most 1 KB:

```
MXAG1:<index>/<total>:<data>
```

The receiver reassembles chunks, verifies `crc32`, and then parses the
envelope. A file-based transport (SD card) simply writes the raw envelope bytes
with `.mxag` appended to the filename.

---

## 5. Requirements for the cold signer

1. **Never trust the host.** Parse, bounds-check, and re-serialize every field.
2. **Display before signing**: destinations, amounts, fee, and the total spent.
   Amounts come from the commitments; verify the commitment sum equals
   `sum(outputs) + fee` and that the fee is not absurd.
3. **Verify the ring**: exactly one ring member must correspond to
   `real_out_index`, and the key image must not be reused (the cold device may
   keep a small key-image cache).
4. **Network binding**: the `network` byte must match the wallet's configured
   network.
5. **Version policy**: reject unknown envelope versions instead of guessing.

---

## 6. Compatibility path

* Phase 1: implement the portable `MXAG` format between Passport2 and a
  companion mobile wallet. This is the "chicken and egg" pair that can be
  tested against each other.
* Phase 2: add an adapter that converts a `wallet2` `unsigned_monero_tx` into
  the portable unsigned payload, and a signed payload back into
  `signed_monero_tx`, so the Passport can also serve users of stock
  `monero-wallet-cli`. The adapter must be treated as hostile-input parsing
  code.

---

## 7. Open questions

* Exact `wallet2` magic constant and version history (needed for Phase 2).
* Measured size of a real `unsigned_monero_tx` for 2-in / 2-out, and its
  variance with ring size and number of inputs.
* Whether to carry the fee explicitly or recompute it from commitments.
* Test vectors: a fixed seed, a fixed set of decoys, and the resulting
  unsigned/signed payloads for regression testing.

---

## 8. References

* Offline transaction signing details:
  <https://monero.stackexchange.com/questions/2426/offline-transaction-signing-what-are-the-details>
* Feather wallet offline signing guide:
  <https://docs.featherwallet.org/guides/offline-tx-signing>
* EPEE portable storage description:
  <https://github.com/jeffro256/serde_epee/blob/master/PORTABLE_STORAGE.md>
* BIP-370 (PSBT v2), as a model for how to write this kind of document:
  <https://github.com/bitcoin/bips/blob/master/bip-0370.mediawiki>
