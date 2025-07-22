# SPDX-FileCopyrightText: © 2020 Foundation Devices, Inc. <hello@foundationdevices.com>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# SPDX-FileCopyrightText: 2018 Coinkite, Inc. <coldcardwallet.com>
# SPDX-License-Identifier: GPL-3.0-only
#
# (c) Copyright 2018 by Coinkite Inc. This file is part of Coldcard <coldcardwallet.com>
# and is covered by GPLv3 license found in COPYING.
#
# stash.py - encoding the ultrasecrets: bip39 seeds and words
#
# references:
# - <https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki>
# - <https://iancoleman.io/bip39/#english>
# - zero values:
#    - 'abandon' * 23 + 'art'
#    - 'abandon' * 17 + 'agent'
#    - 'abandon' * 11 + 'about'
#
import trezorcrypto
import uctypes
import gc
from pincodes import SE_SECRET_LEN

marker_value = 0x82

def blank_object(item):
    # Use/abuse uctypes to blank objects until python. Will likely
    # even work on immutable types, so be careful. Also works
    # well to kill references to sensitive values (but not copies).
    #
    if isinstance(item, (bytearray, bytes, str)):
        addr, ln = uctypes.addressof(item), len(item)
        buf = uctypes.bytearray_at(addr, ln)
        for i in range(ln):
            buf[i] = 0
    elif isinstance(item, trezorcrypto.bip32.HDNode):
        pass
        # item.blank()  # node.blank() elsewhere
    else:
        raise TypeError(item)


# Chip can hold 72-bytes as a secret: we need to store either
# a list of seed words (packed), of various lengths, or maybe
# a raw master secret, and so on

class SecretStash:

    @staticmethod
    def encode(seed_bits):
        nv = bytearray(SE_SECRET_LEN)

        if seed_bits:
            vlen = len(seed_bits)

            assert vlen == 32
            nv[0] = marker_value
            nv[1:1 + vlen] = seed_bits
        return nv

    @staticmethod
    def decode(secret):
        # expecting 72-bytes of secret payload; decode meaning
        # returns:
        #    type, secrets bytes
        #
        retrieved_marker = secret[0]

        if retrieved_marker & marker_value:
            seed_bits = secret[1:33]

            return 'words', seed_bits
        elif retrieved_marker == 0x01:
            return 'bitcoin_xprv', None
        else:
            return 'unknown', None


class SensitiveValues:
    # be a context manager, and holder to secrets in-memory

    def __init__(self, secret=None, for_backup=False):
        from common import system

        if secret is None:
            # fetch the secret from bootloader/atecc508a
            from common import pa

            if pa.is_secret_blank():
                raise ValueError('no secrets yet')

            self.secret = pa.fetch()
            self.spots = [self.secret]
        else:
            # sometimes we already know it
            # assert set(secret) != {0}
            self.secret = secret
            self.spots = []


    def __enter__(self):
        import chains

        self.mode, self.raw = SecretStash.decode(self.secret)
        #TODO: Check if self.mode is 'bitcoin_xprv', 'bitcoin_words', or 'unkown'

        self.spots.append(self.raw)

        #Dummy node to maintain functionality. Remove when xpub code is removed.
        self.node = trezorcrypto.bip32.from_seed(trezorcrypto.bip39.seed(trezorcrypto.bip39.from_data(self.raw), ''), 'secp256k1')

        self.chain = chains.current_chain()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clear secrets from memory ... yes, they could have been
        # copied elsewhere, but in normal case, at least we blanked them.
        for item in self.spots:
            blank_object(item)

        if hasattr(self, 'secret'):
            # will be blanked from above
            del self.secret

        if hasattr(self, 'node'):
            # specialized blanking code already above
            del self.node

        # just in case this holds some pointers?
        del self.spots

        # .. and some GC will help too!
        gc.collect()

        if exc_val:
            # An exception happened, but we've done cleanup already now, so
            # not a big deal. Cause it be raised again.
            return False

        return True

    def get_xfp(self):
        return self.node.my_fingerprint()

    def capture_xpub(self, save=False):
        # track my xpubkey fingerprint & value in settings (not sensitive really)
        # - we share these on any USB connection
        import common
        from common import settings

        # # Set the master values if no account selected yet
        # if common.active_account:
        #     # Derive xfp and xpub based on the current active account
        #     # The BIP39 passphrase is already taken into account by SensitiveValues
        #     # print('deriving from path: {}'.format(common.active_account.deriv_path))
        #     if not common.active_account.deriv_path:
        #         return
        #
        #     node = self.derive_path(common.active_account.deriv_path)
        #
        #     xfp = node.my_fingerprint()
        #     print('capture_xpub(): xfp={}'.format(hex(xfp)))
        #     xpub = self.chain.serialize_public(node, common.active_account.addr_type)
        #     print('capture_xpub(): xpub={}'.format(xpub))
        # else:

        xfp = self.node.my_fingerprint()
        # print('capture_xpub(): xfp={}'.format(hex(xfp)))
        xpub = self.chain.serialize_public(self.node)
        # print('capture_xpub(): xpub={}'.format(xpub))

        # Always store these volatile - Takes less than 1 second to recreate, and it will change whenever
        # a passphrase is entered, so no need to waste flash cycles on storing it.
        if True:
            settings.set_volatile('root_xfp', xfp)
            if save:
                settings.set('xfp', xfp)
                settings.set('xpub', xpub)
                settings.save()

        settings.set_volatile('xfp', xfp)
        settings.set_volatile('xpub', xpub)

        settings.set_volatile('chain', self.chain.ctype)
        settings.set('words', (self.mode == 'words'))

    def register(self, item):
        # Caller can add his own sensitive (derived?) data to our wiper
        # typically would be byte arrays or byte strings, but also
        # supports bip32 nodes
        self.spots.append(item)

    def derive_path(self, path, master=None, register=True):
        # Given a string path, derive the related subkey
        rv = (master or self.node).clone()

        if register:
            self.register(rv)

        for i in path.split('/'):
            if i == 'm':
                continue
            if not i:
                continue      # trailing or duplicated slashes

            if i[-1] == "'":
                assert len(i) >= 2, i
                here = int(i[:-1])
                assert 0 <= here < 0x80000000, here
                here |= 0x80000000
            else:
                here = int(i)
                assert 0 <= here < 0x80000000, here

            rv.derive(here)

        return rv

# EOF
