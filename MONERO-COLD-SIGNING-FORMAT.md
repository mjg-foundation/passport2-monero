<!--
SPDX-FileCopyrightText: Copyright (c) 2026 Guoqiang Liu

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Monero `wallet2` cold-signing file format

## Status and scope

This document is a descriptive compatibility profile for the files exchanged by
the official `monero-wallet-cli` cold-signing workflow. It describes the current
version 5 files written by Monero
[`v0.18.5.1`](https://github.com/monero-project/monero/releases/tag/v0.18.5.1),
pinned to commit
[`4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`](https://github.com/monero-project/monero/tree/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5).
It does not define a new transaction protocol or a Monero consensus format.

The words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** identify either a
wire-compatibility requirement of the pinned `wallet2` implementation or an
explicit decoder-validation requirement in this profile. The surrounding text
states which kind applies. These requirements do not freeze future Monero
wallet formats.

This profile covers:

- the `unsigned_monero_tx` and `signed_monero_tx` file envelopes;
- authenticated encryption with the wallet private view key;
- the version 5 Monero binary-archive payloads;
- the fields needed to decode both transaction sets;
- historical outer versions 3 and 4; and
- fixture generation and interoperability checks.

Multisig transaction-set files, output-only export files, wallet RPC framing,
QR encoding, and UR fragmentation are outside the byte format defined here.

## Cold-signing lifecycle

The normal CLI flow uses two representations of the same account. The online
watch-only wallet has the account public address, including its spend public
key, and the private view key. The offline full wallet has the corresponding
private spend and view keys:

1. A synced view-only wallet constructs a transaction and writes
   `unsigned_monero_tx`.
2. The file is transported byte-for-byte to the offline full wallet.
3. The offline wallet runs `sign_transfer`, displays the transaction for
   approval, and writes `signed_monero_tx`.
4. The signed file is transported byte-for-byte to the view-only wallet.
5. The view-only wallet runs `submit_transfer`, imports returned key-image
   state, and relays the transactions.

The unsigned set carries an output-state update in addition to transaction
construction data. The signed set returns wallet key images in addition to the
signed transactions. Implementations MUST NOT treat either file as just a raw
Monero transaction blob. The CLI entry points and default file names are in
[`simplewallet.cpp`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/simplewallet/simplewallet.cpp#L8057-L8150).

## Two independent version layers

Each current file contains two versions:

- The **outer version** is byte `0x05` immediately after the ASCII magic. It
  selects encryption and the archive family.
- The **embedded schema version** is the first unsigned varint in the decrypted
  archive. It is currently `2` for `unsigned_tx_set` and `0` for
  `signed_tx_set`.

These layers MUST be parsed independently. In particular, outer version 5 does
not imply embedded version 5.

## Version 5 outer envelope

The source constants include the outer version as the final byte. The reader
compares the ASCII portion as magic and then dispatches on that final byte. See
the
[`wallet2.cpp` prefix definitions](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.cpp#L114-L116).

### Unsigned file

| Offset | Length | Value |
| ---: | ---: | --- |
| 0 | 22 | ASCII `Monero unsigned tx set` |
| 22 | 1 | Outer version `0x05` |
| 23 | 8 | ChaCha IV |
| 31 | variable | ChaCha20 ciphertext |
| EOF - 64 | 64 | `crypto::signature` |

The minimum total length of a structurally encoded current unsigned set is 101
bytes: 22-byte magic, 1-byte version, 8-byte IV, 6-byte plaintext/ciphertext,
and a 64-byte signature.

### Signed file

| Offset | Length | Value |
| ---: | ---: | --- |
| 0 | 20 | ASCII `Monero signed tx set` |
| 20 | 1 | Outer version `0x05` |
| 21 | 8 | ChaCha IV |
| 29 | variable | ChaCha20 ciphertext |
| EOF - 64 | 64 | `crypto::signature` |

The corresponding minimum is 97 bytes because the signed-set empty plaintext
is four bytes.

An implementation MUST first require enough input for the relevant magic,
version, IV, and signature. It MUST compare the full ASCII magic, MUST reject an
unknown outer version, and MUST authenticate the encrypted frame before using
the plaintext.

## Authenticated encryption frame

The bytes after outer version 5 are:

```text
view_key_frame = iv[8] || chacha20(plaintext) || signature[64]
```

The pinned implementation constructs the frame as follows:

1. Take the wallet's raw 32-byte private view key.
2. Derive a 32-byte ChaCha key with `generate_chacha_key`. Run CryptoNight
   `cn_slow_hash(view_secret_key, variant=0, prehashed=0, height=0)` once, then
   rehash the preceding 32-byte result `kdf_rounds - 1` times with the same
   parameters. The total is exactly `kdf_rounds` invocations.
3. Generate a random 8-byte IV.
4. Encrypt the binary-archive plaintext with Monero's original ChaCha20 layout.
   It uses a 64-bit counter starting at zero and the 64-bit IV as the nonce. It
   is not the RFC 8439/IETF variant with a 96-bit nonce.
5. Compute `cn_fast_hash(iv || ciphertext)`.
6. Sign that hash using the private view key and its corresponding public key,
   then append the 64-byte signature.

The signature is Monero's packed `crypto::signature`, serialized as the raw
32-byte scalar `c` followed by the raw 32-byte scalar `r`. It is generated and
checked by Monero's `generate_signature` and `check_signature` operations; it
is not an Ed25519 signature. See the
[`crypto::signature` layout](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/crypto/crypto.h#L98-L114)
and the
[`generate_signature`/`check_signature` implementation](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/crypto/crypto.cpp#L290-L340).

The implementation is in
[`wallet2.cpp`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.cpp#L15510-L15581),
and the key derivation and IV sizes are in
[`chacha.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/crypto/chacha.h#L36-L79).
The counter and nonce placement are in
[`chacha.c`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/crypto/chacha.c#L45-L69).

The KDF round count is not stored in the file. Both endpoints MUST use the same
positive value. Monero defaults it to `1`; a wallet opened with a different
`--kdf-rounds` value creates an out-of-band compatibility requirement.

The magic and outer version are not encrypted or signed. The authenticated
portion begins at the IV. Because the IV and signature generation vary between
runs, an encrypted file has no single canonical hexadecimal encoding.

## Version 5 binary-archive grammar

Version 5 uses Monero `binary_archive`, not epee portable
storage. Field names are not emitted. The exact declaration order is therefore
part of the byte format. The relevant implementation is
[`binary_archive.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/serialization/binary_archive.h#L95-L236).

The generic encoders used by the structures below are pinned separately:

- unsigned varints in
  [`varint.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/common/varint.h#L55-L127);
- strings in
  [`string.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/serialization/string.h#L35-L61);
- pairs in
  [`pair.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/serialization/pair.h#L40-L107);
- tuples in
  [`tuple.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/serialization/tuple.h#L39-L167);
- sequential and associative containers in
  [`container.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/serialization/container.h#L41-L141)
  and
  [`containers.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/serialization/containers.h#L47-L127);
  and
- tagged alternatives in
  [`variant.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/serialization/variant.h#L63-L145).

The notation used below has these definitions:

```text
uvarint(x)       Monero unsigned LEB128 representation of x
fixed_le<T>(x)   sizeof(T) bytes, least-significant byte first
blob<N>          exactly N uninterpreted bytes
bool             one byte: false is 00 and true is 01 in writer output
string           uvarint(byte_length) || raw bytes
vector<T>        uvarint(element_count) || T[0] || ... || T[n-1]
set<T>           uvarint(element_count) || each serialized T
map<K,V>         uvarint(element_count) || pair<K,V> entries
pair<A,B>        uvarint(2) || A || B
tuple<A,B,C>     uvarint(3) || A || B || C
```

Additional rules:

- `VERSION_FIELD(n)` is a uvarint.
- `VARINT_FIELD(x)` is a uvarint.
- A bare integral `FIELD(x)` is fixed-width little-endian, except where the
  containing tuple, pair, or integral container explicitly selects varints.
- Container lengths are uvarints. Unsigned integral elements wider than one
  byte in standard containers are also encoded as uvarints.
- Variant tags occupy one byte and are followed by the selected value.
- `crypto::public_key`, `crypto::secret_key`, `crypto::key_image`, and
  `rct::key` are 32-byte blobs. `rct::ctkey` is a 64-byte blob, and
  `rct::multisig_kLRki` is a 128-byte blob.
- `account_public_address` is its 32-byte spend public key followed by its
  32-byte view public key.
- The top-level decoder MUST consume all decrypted bytes. The Monero
  `serialize` entry point rejects trailing data.

The Monero varint implementation rejects overflow and non-canonical values.
Compatible decoders SHOULD impose implementation-appropriate upper bounds on
container counts before allocation.

## Unsigned payload

The current writer serializes this grammar:

```text
unsigned_tx_set =
    uvarint(2)                               # embedded schema version
    vector<tx_construction_data> txes
    tuple<u64,u64,vector<exported_transfer_details>> new_transfers
```

The tuple contains `(offset, total_outputs, exported_outputs)`. Entry `n` in the
third element represents wallet transfer index `offset + n`, while
`total_outputs` is the hot wallet's complete transfer count at export time. The
first two `u64` values use the tuple serializer's uvarint representation, not
fixed-width eight-byte values. The writer obtains this tuple from
`export_outputs()`.

The declaration and compatibility branches are in
[`wallet2.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.h#L697-L727),
and the current write path is in
[`wallet2.cpp`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.cpp#L7663-L7690).

### `tx_construction_data`

There is no leading version for this structure. Fields occur in this order:

| # | Field | Encoding |
| ---: | --- | --- |
| 1 | `sources` | `vector<tx_source_entry>` |
| 2 | `change_dts` | `tx_destination_entry` |
| 3 | `splitted_dsts` | `vector<tx_destination_entry>` |
| 4 | `selected_transfers` | vector of uvarint indices |
| 5 | `extra` | length-prefixed byte vector |
| 6 | `unlock_time` | fixed little-endian `u64` |
| 7 | `construction_flags` | one byte, serialized under historical field name `use_rct` |
| 8 | `rct_config` | `RCTConfig` |
| 9 | `dests` | `vector<tx_destination_entry>` |
| 10 | `subaddr_account` | fixed little-endian `u32` |
| 11 | `subaddr_indices` | set of uvarint `u32` indices |

`construction_flags` bit 0 means `use_rct`; bit 1 means `use_view_tags`.
`RCTConfig` is embedded version `0`, followed by the uvarint
`range_proof_type` and uvarint `bp_version`. See
[`wallet2.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.h#L561-L617)
and
[`rctTypes.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/ringct/rctTypes.h#L308-L316).

### `tx_source_entry`

Fields occur in this order:

| # | Field | Encoding |
| ---: | --- | --- |
| 1 | `outputs` | vector of `pair<u64,rct::ctkey>`; pair count `2`, index as uvarint, then 64-byte `ctkey` |
| 2 | `real_output` | fixed little-endian `u64` |
| 3 | `real_out_tx_key` | 32-byte public key |
| 4 | `real_out_additional_tx_keys` | vector of 32-byte public keys |
| 5 | `real_output_in_tx_index` | fixed little-endian `u64` |
| 6 | `amount` | fixed little-endian `u64` |
| 7 | `rct` | bool |
| 8 | `mask` | 32-byte `rct::key` |
| 9 | `multisig_kLRki` | 128-byte blob |

A decoder MUST reject an entry where `real_output >= outputs.size()`, matching
the structure serializer. See
[`cryptonote_tx_utils.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/cryptonote_core/cryptonote_tx_utils.h#L42-L71).

### `tx_destination_entry`

```text
string original
uvarint amount
blob<32> address_spend_public_key
blob<32> address_view_public_key
bool is_subaddress
bool is_integrated
```

See
[`cryptonote_tx_utils.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/cryptonote_core/cryptonote_tx_utils.h#L74-L107)
and the
[`account_public_address` serializer](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/cryptonote_basic/cryptonote_basic.h#L511-L519).

### `exported_transfer_details`

```text
uvarint(1)     embedded schema version
blob<32>       m_pubkey
uvarint        m_internal_output_index
uvarint        m_global_output_index
blob<32>       m_tx_pubkey
u8             m_flags.flags
uvarint        m_amount
vector<blob<32>> m_additional_tx_keys
uvarint        m_subaddr_index_major
uvarint        m_subaddr_index_minor
```

Readers MUST reject embedded versions below `1`. The flags masks are spent
`0x01`, frozen `0x02`, RingCT `0x04`, key-image-known `0x08`,
key-image-request `0x10`, and key-image-partial `0x20`. See
[`wallet2.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.h#L406-L443).

## Signed payload

The current writer serializes:

```text
signed_tx_set =
    uvarint(0)                                      # embedded schema version
    vector<pending_tx> ptx
    vector<blob<32>> key_images
    map<blob<32>,blob<32>> tx_key_images
```

`key_images[i]` is the cold wallet's key image for transfer index `i`; the hot
wallet imports this vector starting at index zero. `tx_key_images` maps any new
output public key in a signed transaction that belongs to this wallet to its
newly calculated key image. Its serialized entry order follows an unordered map
and MUST NOT be treated as canonical across runs. The declaration is in
[`wallet2.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.h#L729-L741),
with state populated in
[`wallet2.cpp`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.cpp#L7878-L7941)
and imported in
[`wallet2.cpp`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.cpp#L8121-L8129).

### `pending_tx`

The current `pending_tx` writer emits embedded schema version `1` followed by:

| # | Field | Encoding |
| ---: | --- | --- |
| 1 | `tx` | canonical Monero `transaction` serializer |
| 2 | `dust` | fixed little-endian `u64` |
| 3 | `fee` | fixed little-endian `u64` |
| 4 | `dust_added_to_fee` | bool |
| 5 | `change_dts` | `tx_destination_entry` |
| 6 | `selected_transfers` | vector of uvarint indices |
| 7 | `key_images` | string |
| 8 | `tx_key` | 32-byte secret-key blob |
| 9 | `additional_tx_keys` | vector of 32-byte secret-key blobs |
| 10 | `dests` | `vector<tx_destination_entry>` |
| 11 | `construction_data` | `tx_construction_data` |
| 12 | `multisig_sigs` | `vector<multisig_sig>` |
| 13 | `multisig_tx_key_entropy` | 32-byte secret-key blob; present for version 1 |

The cold-signing path sets the `tx_key` placed in the returned signed set to the
RingCT identity value and does not populate that returned object with the real
additional transaction keys. Its local pending-transaction copy retains the
actual keys. See
[`wallet2.cpp`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.cpp#L7814-L7875).

For embedded version `0`, the pinned reader consumes fields 1 through 12, omits
`multisig_tx_key_entropy`, and sets it to `crypto::null_skey`. For every version
greater than or equal to `1`, it also consumes field 13. The CLI
`sign_transfer` path rejects multisig wallets and constructs a fresh
`pending_tx`, so `multisig_sigs` is an empty vector encoded as `00` in files
covered by this profile. Non-empty `multisig_sigs` values belong to the separate
multisig workflow and are outside this profile.

The remaining `pending_tx` declaration is in
[`wallet2.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.h#L624-L692).

#### Embedded `transaction`

`pending_tx.tx` is a concrete `transaction` object written inline. It does not
have an outer `transaction` variant tag. Its prefix is:

```text
transaction_prefix =
    uvarint(version)
    uvarint(unlock_time)
    vector<txin_v> vin
    vector<tx_out> vout
    vector<u8> extra
```

The prefix fields and input/output structures are defined in
[`cryptonote_basic.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/cryptonote_basic/cryptonote_basic.h#L61-L190).
A normal cold-signed spend uses `txin_to_key` inputs:

```text
txin_to_key =
    uvarint(amount)
    vector<u64-varint> key_offsets
    blob<32> key_image

tx_out =
    uvarint(amount)
    tagged txout_target_v target
```

The complete input and output alternative bodies are:

```text
txin_gen =
    uvarint(height)

txin_to_script =
    blob<32> prev
    uvarint(prevout)
    vector<u8> sigset

txin_to_scripthash =
    blob<32> prev
    uvarint(prevout)
    txout_to_script script
    vector<u8> sigset

txout_to_script =
    vector<blob<32>> keys
    vector<u8> script

txout_to_scripthash =
    blob<32> hash

txout_to_key =
    blob<32> key

txout_to_tagged_key =
    blob<32> key
    blob<1> view_tag
```

`txout_to_key` and `txout_to_scripthash` are blob-serialized, so their bodies
have no additional object marker or length prefix. A normal cold-signed spend
uses `txin_to_key`; current transactions can use `txout_to_tagged_key`. The
other bodies above complete the registered binary variants. Their declarations
and serializers are in
[`cryptonote_basic.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/cryptonote_basic/cryptonote_basic.h#L61-L165).

The one-byte input and output tags are registered at
[`cryptonote_basic.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/cryptonote_basic/cryptonote_basic.h#L569-L581):

| Alternative | Tag |
| --- | ---: |
| `txin_gen` | `ff` |
| `txin_to_script` | `00` |
| `txin_to_scripthash` | `01` |
| `txin_to_key` | `02` |
| `txout_to_script` | `00` |
| `txout_to_scripthash` | `01` |
| `txout_to_key` | `02` |
| `txout_to_tagged_key` | `03` |

After the prefix, the complete transaction serializer follows the branches in
[`cryptonote_basic.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/cryptonote_basic/cryptonote_basic.h#L242-L317):

- Version `1` writes legacy signatures. Their dimensions are derived from
  `vin`; neither the outer signature array nor each per-input array has a
  normal vector-length prefix.
- Version `2`, with at least one input, writes the RingCT base.
- A full, unpruned transaction whose RingCT type is not `Null` then writes the
  RingCT prunable part.

#### RingCT base and prunable branches

The RingCT type values are fixed by
[`RCTType`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/ringct/rctTypes.h#L298-L306),
and the nested proof/signature records are declared earlier in
[`rctTypes.h`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/ringct/rctTypes.h#L135-L278).
The base serializer is
[`rctSigBase::serialize_rctsig_base`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/ringct/rctTypes.h#L318-L404):

```text
u8 type
if type != Null:
    uvarint(txnFee)
    if type == Simple:
        inputs * blob<32> pseudoOuts
    outputs * ecdhInfo
    outputs * blob<32> outPk.mask
```

The input and output counts come from the transaction prefix and are not
written again. For `Bulletproof2`, `CLSAG`, and `BulletproofPlus`, each
`ecdhInfo` writes only its eight-byte amount field. Older types write the full
32-byte mask followed by the 32-byte amount. Only the commitment/mask half of
each `outPk` is written because its destination key is already in `vout`.

The prunable serializer is
[`rctSigPrunable::serialize_rctsig_prunable`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/ringct/rctTypes.h#L416-L602).
Its important derived-length rules are:

- `Full` and `Simple` write exactly `outputs` Borromean `rangeSig` records
  first. This derived array has no count prefix.
- `BulletproofPlus` writes a uvarint proof count followed by that many
  Bulletproof+ records.
- `Bulletproof2` and `CLSAG` write a uvarint Bulletproof count. The older
  `Bulletproof` type writes that count as a fixed little-endian `u32`.
- `CLSAG` and `BulletproofPlus` write exactly one CLSAG per input. Each CLSAG
  has `mixin + 1` scalar entries in `s`, followed by `c1` and `D`; the `s`
  length is not written as a normal vector count.
- Older RingCT types write MG records whose matrix dimensions are derived from
  the RingCT type, input count, and mixin.
- `Bulletproof`, `Bulletproof2`, `CLSAG`, and `BulletproofPlus` finish with
  exactly one 32-byte `pseudoOut` per input.

The proof records use these exact byte orders:

```text
range_sig =
    64 * blob<32> asig.s0
    64 * blob<32> asig.s1
    blob<32>      asig.ee
    64 * blob<32> Ci

bulletproof =
    blob<32> A
    blob<32> S
    blob<32> T1
    blob<32> T2
    blob<32> taux
    blob<32> mu
    vector<blob<32>> L
    vector<blob<32>> R
    blob<32> a
    blob<32> b
    blob<32> t

bulletproof_plus =
    blob<32> A
    blob<32> A1
    blob<32> B
    blob<32> r1
    blob<32> s1
    blob<32> d1
    vector<blob<32>> L
    vector<blob<32>> R
```

The `L` and `R` vectors each carry their own normal uvarint element count.
For both proof types they MUST be non-empty and have equal counts. The `V`
commitment vector is deliberately absent from both records and is restored
from `outPk`; its position in the C++ structure declaration is not part of the
wire format. These rules come from the explicit
[`Bulletproof` and `BulletproofPlus` serializers](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/ringct/rctTypes.h#L212-L278).

The context-sized signature records are:

```text
clsag =
    (mixin + 1) * blob<32> s
    blob<32> c1
    blob<32> D

mg_sig =
    (mixin + 1) * row
    blob<32> cc

row =
    # Simple, Bulletproof, or Bulletproof2
    2 * blob<32>

    # Full
    (inputs + 1) * blob<32>
```

There is one `mg_sig` per input for `Simple`, `Bulletproof`, and
`Bulletproof2`, but exactly one for `Full`. No count prefixes are written for
the MG array, its rows, or its row elements. The reconstructible CLSAG `I` and
MG `II` values are not serialized. The enclosing proof-count fields described
above remain present; only these context-derived arrays omit their normal
vector counts.

The `mixin` argument is derived as the first `txin_to_key.key_offsets.size()`
minus one by the
[transaction serializer](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/cryptonote_basic/cryptonote_basic.h#L304-L309);
it is not stored separately.

Implementations MUST follow these type-dependent serializers rather than
applying the generic `vector<T>` rule to arrays whose sizes are derived from
transaction context. The complete branch logic, including the fields omitted
because they are reconstructed, is in the pinned
[`rctSigPrunable` serializer](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/ringct/rctTypes.h#L416-L602).

## Embedded unsigned-schema compatibility

The version 5 archive reader retains these `unsigned_tx_set` schema branches:

| Embedded version | Field after `txes` | Conversion performed by reader |
| ---: | --- | --- |
| 0 | `pair<size_t, transfer_container>` | Derives start/end and legacy transfers |
| 1 | `pair<size_t, vector<exported_transfer_details>>` | Derives start/end and current transfers |
| 2 or later | current three-element `new_transfers` tuple | No conversion |

Current writers emit embedded version 2. This table is separate from the outer
file-version history below.

## Outer compatibility history

| Outer version | Payload archive | Encryption | `v0.18.5.1` reader behavior |
| ---: | --- | --- | --- |
| `0x03` | Boost portable binary archive | none | only when `load-deprecated-formats` is enabled |
| `0x04` | Boost portable binary archive | private-view-key frame | only when `load-deprecated-formats` is enabled |
| `0x05` | Monero binary archive described here | private-view-key frame | current default |

The parser branches are visible for the
[`unsigned set`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.cpp#L7712-L7797)
and
[`signed set`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/src/wallet/wallet2.cpp#L8027-L8131).
Version 4 introduced the encrypted Boost payload in
[`d74336d5`](https://github.com/monero-project/monero/commit/d74336d5c9ecee247181b472cebf0c09a386bce4),
and version 5 switched to Monero binary archive in
[`7175dcb1`](https://github.com/monero-project/monero/commit/7175dcb1078abbdaa130a8c5f5fd2b93fa7b3086).

This table describes how the pinned `v0.18.5.1` reader dispatches each outer
version. It does not promise that every file produced by every historical
version 4 writer is interoperable with the current decryption implementation;
the original version 4 change used ChaCha8, while the pinned reader calls the
current ChaCha20 path.

New implementations SHOULD write only outer version 5. A version 3 or 4 reader
is optional and MUST be explicitly treated as legacy behavior.

## Minimal plaintext fixtures

These fixtures test the archive grammar without the nondeterministic encryption
frame. They are structurally decodable empty objects, not transactions that can
be signed or relayed.

### Empty current unsigned set

```text
02 00 03 00 00 00
```

SHA-256 of those six plaintext bytes:
`f8c9c05e41a7641df824c71220c7ec4cb744e2601ba178669bc1bdc318a51220`.

| Byte | Meaning |
| ---: | --- |
| `02` | embedded `unsigned_tx_set` version 2 |
| `00` | zero `txes` elements |
| `03` | tuple arity 3 |
| `00` | output-state offset 0 |
| `00` | total outputs 0 |
| `00` | zero exported-output elements |

### Empty current signed set

```text
00 00 00 00
```

SHA-256 of those four plaintext bytes:
`df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119`.

| Byte | Meaning |
| ---: | --- |
| first `00` | embedded `signed_tx_set` version 0 |
| second `00` | zero pending transactions |
| third `00` | zero key images |
| fourth `00` | zero output-key/key-image map entries |

### Non-empty encrypted round-trip fixture

This repository includes a frozen pair in
[`docs/fixtures/monero-v0.18.5.1`](docs/fixtures/monero-v0.18.5.1/README.md).
It was generated by the pinned upstream `cold_signing` functional test on an
isolated regtest chain with the official v0.18.5.1 binaries. The only local
instrumentation printed the already-generated wallet RPC hex fields and the
published private test view key; it did not change any request or assertion.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| unsigned | 3,204 | `0a68ca780e5833d2808b07b4cd58a6519bc128b8e7197126bd4292602f315ead` |
| signed | 8,522 | `e09504167ea03340172079ca58a711186860b7d41fe38c82e008fbd36c14ebb6` |

The fixture metadata supplies the exact files, private test view key, seed,
IVs, downloaded CLI archive hash, generation command, and expected lifecycle.
The upstream harness accepted the unsigned set in `describe_transfer`, signed
it, accepted the signed set into the regtest mempool, mined it, and reported
`Done, 1/1 tests passed`. This is an end-to-end compatibility vector, not a
claim that encrypted writer output is deterministic.

## Decoder procedure

A compatible version 5 decoder performs these operations in order:

1. Select the unsigned or signed magic expected by the calling context.
2. Enforce the minimum length before reading the outer version.
3. Compare every magic byte and require outer version `0x05`.
4. Split the remaining data into 8-byte IV, ciphertext, and 64-byte signature.
5. Derive the ChaCha key using the private view key and agreed KDF rounds.
6. Verify the signature over `cn_fast_hash(iv || ciphertext)`.
7. Decrypt the ciphertext with ChaCha20.
8. Decode the expected top-level schema with Monero binary-archive rules.
9. Reject malformed varints, invalid variants, impossible field relationships,
   short input, versions disallowed by the selected profile, and trailing
   plaintext bytes.
10. Present and validate transaction semantics before signing or relaying.

An implementation MUST select the top-level type from its operation, not from
untrusted payload data. It MUST NOT silently interpret a failed version 5 decode
as an older archive family.

For exact pinned-reader behavior, apply the documented branches rather than
assuming a new layout from a larger version value: unsigned versions 0 and 1
have legacy branches and every value at least 2 uses the current tuple;
`pending_tx` version 0 omits its last field and every value at least 1 includes
it. The pinned `signed_tx_set` and `RCTConfig` readers do not impose an upper
version bound. A writer-focused profile MAY instead reject values newer than
those emitted at the pinned commit, but that policy is deliberately stricter
than `wallet2 v0.18.5.1`.

## Reproducible interoperability fixtures

Monero includes a
[`cold_signing.py`](https://github.com/monero-project/monero/blob/4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5/tests/functional_tests/cold_signing.py)
functional test. A fixture producer SHOULD build the pinned commit and run its
functional-test harness on a controlled local test network. No mainnet funds or
live wallet secrets are required.

From the pinned Monero source root, after building the release binaries, run:

```shell
python3 tests/functional_tests/functional_tests_rpc.py \
  python3 "$PWD/tests/functional_tests" "$PWD/build/release" cold_signing
```

For each non-empty unsigned/signed fixture pair, record:

- Monero release and full commit ID;
- network and KDF round count;
- a public, non-production deterministic test seed or private view key and its
  corresponding public/account keys, sufficient to repeat decryption and
  signature verification;
- fixture role and expected decoded field tree;
- exact file length and SHA-256 digest;
- outer magic and version;
- decrypted plaintext hexadecimal encoding, or enough public test key material
  to reproduce decryption plus the accepted semantic decoder output; and
- expected accept/reject result at each lifecycle step.

Freeze one generated encrypted pair if exact-byte regression tests are useful.
For newly generated pairs, compare decoded semantics rather than expecting the
encrypted bytes to repeat. IVs, signatures, transaction construction, and
unordered-map iteration can all make whole-file bytes vary.

Fixture keys MUST be generated only for public testing and MUST NOT have ever
controlled live funds. Never publish a production seed or private view/spend
key.

The repository's historical `tests/data/unsigned_monero_tx` and
`tests/data/signed_monero_tx` samples use outer version 3. They MUST NOT be
labelled as version 5 fixtures.

At minimum, an interoperability suite SHOULD test:

- the two empty plaintext vectors above;
- one valid version 5 unsigned/signed round trip;
- wrong magic and unknown outer version;
- truncated IV, ciphertext, and signature;
- wrong private view key or KDF round count;
- altered ciphertext or signature;
- malformed/overflowing varints and unreasonable container counts;
- higher embedded schema versions under the implementation's declared policy;
- invalid `real_output` index; and
- otherwise valid plaintext with trailing bytes.

## Transport binding

microSD, animated QR, or UR are transport choices above this format. A binding
MUST preserve the complete file bytes, including magic and outer version. If a
transport adds a media type, compression, checksum, or fragmentation, those
operations MUST be reversed before the parser described here is invoked.

This document does not assign a Monero UR registry type or mandate Base64,
hexadecimal, CBOR, or compression. Such a binding requires a separate versioned
specification and interoperability fixtures.

## Compatibility checklist

- [ ] Pin the supported Monero release and commit.
- [ ] Distinguish the outer and embedded versions.
- [ ] Preserve the exact magic and envelope byte order.
- [ ] Match private-view-key KDF rounds at both endpoints.
- [ ] Authenticate before decoding plaintext.
- [ ] Use Monero binary archive, not portable storage, for outer version 5.
- [ ] Follow declaration order and each nested type's serializer.
- [ ] Consume the full plaintext and reject malformed input.
- [ ] Import the returned output/key-image state as well as transactions.
- [ ] Preserve exact bytes through the selected air-gap transport.
- [ ] Verify against a pinned official-wallet round trip.

## Review and evolution

This is a source-derived description, not an upstream Monero guarantee. Changes
to any referenced serializer can change compatibility even if the outer version
is not changed. Implementers SHOULD diff the source anchors and regenerate
fixtures before claiming compatibility with a later Monero release.

Ratification requires approval from a developer who has worked on Monero's core
wallet functionality, matching the acceptance condition of the tracking issue.
That reviewer should confirm the envelope, KDF/signature construction,
binary-archive primitive rules, nested field order, state-update semantics, and
the pinned transaction/RingCT serializer boundary.
