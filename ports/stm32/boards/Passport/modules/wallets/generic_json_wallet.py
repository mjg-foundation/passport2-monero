# SPDX-FileCopyrightText: © 2021 Foundation Devices, Inc. <hello@foundationdevices.com>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# SPDX-FileCopyrightText: 2018 Coinkite, Inc. <coldcardwallet.com>
# SPDX-License-Identifier: GPL-3.0-only
#
# (c) Copyright 2018 by Coinkite Inc. This file is part of Coldcard <coldcardwallet.com>
# and is covered by GPLv3 license found in COPYING.
#
# generic_json_wallet.py - Generic JSON Wallet export
#

import ujson
import stash
from data_codecs.qr_type import QRType
from foundation import ur
from xmr.monero import generate_monero_keys

def create_generic_json_wallet(sw_wallet=None,
                               addr_type=None,
                               acct_num=0,
                               multisig=False,
                               legacy=False,
                               export_mode='qr',
                               qr_type=QRType.UR2):
    accts = [{'fmt': addr_type, 'deriv': None, 'acct': acct_num}]
    with stash.SensitiveValues() as sv:
        _, spend_pub, private_view_key, view_pub = generate_monero_keys(sv.raw)
        #TODO: Generate Testnet addresses too after chains is updated to monero
        try:
            from xmr.addresses import encode_addr
            from xmr.networks import NetworkTypes, net_version
            from xmr import crypto
            public_address = encode_addr(net_version(NetworkTypes.MAINNET), crypto.encodepoint(spend_pub), crypto.encodepoint(view_pub))
        except Exception as e:
            return (dict(error=e), accts)

    rv = dict(privateViewKey=''.join('{:02x}'.format(x) for x in crypto.encodeint(private_view_key)), primaryAddress=public_address, restoreHeight=0)

    msg = ujson.dumps(rv)

    if export_mode == 'qr' and qr_type == QRType.UR2:
        return (ur.new_bytes(msg), accts)

    return (msg, accts)
