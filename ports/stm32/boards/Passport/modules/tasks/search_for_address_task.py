# SPDX-FileCopyrightText: © 2022 Foundation Devices, Inc. <hello@foundationdevices.com>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# SPDX-FileCopyrightText: 2018 Coinkite, Inc. <coldcardwallet.com>
# SPDX-License-Identifier: GPL-3.0-only
#
# (c) Copyright 2018 by Coinkite Inc. This file is part of Coldcard <coldcardwallet.com>
# and is covered by GPLv3 license found in COPYING.
#
# search_for_address_task.py - Task to search a given range of addresses to see if we find a match


async def search_for_address_task(
        on_done,
        account_number,
        address,
        address_type,
        network_type,
        lower,
        upper):

    import stash
    from errors import Error
    from uasyncio import sleep_ms
    from xmr.monero import generate_monero_keys, generate_sub_address_keys
    from xmr.addresses import AddressTypes, encode_addr, decode_addr
    from xmr.networks import NetworkTypes, net_version
    from xmr import crypto

    try:
        with stash.SensitiveValues() as sv:
            _, spend_pub, view_priv, view_pub = generate_monero_keys(sv.raw)

            if address_type == AddressTypes.PRIMARY or address_type == AddressTypes.INTEGRATED:
                _, s_p, v_p = decode_addr(bytes(address, 'ascii'))
                match = crypto.encodepoint(spend_pub) == s_p and crypto.encodepoint(view_pub) == v_p
                await on_done(0 if match else -1, None if match else Error.ADDRESS_NOT_FOUND)
                return

            for i in range(lower, upper):
                current_spend_pub, current_view_pub = generate_sub_address_keys(view_priv, spend_pub, account_number, i)
                public_address = encode_addr(net_version(network_type, address_type == AddressTypes.SUB, address_type == AddressTypes.INTEGRATED), crypto.encodepoint(current_spend_pub), crypto.encodepoint(current_view_pub)).decode('ascii')
                # print('i={}: indices=({}, {}) address_type={} public_address={} address={}\n'.format(i, account_number, i, address_type, public_address, address))
                if public_address == address:
                    await on_done(i, None)
                    return
                await sleep_ms(1)

        await on_done(-1, Error.ADDRESS_NOT_FOUND)
    except Exception as e:
        # print('EXCEPTION: e={}'.format(e))
        # Any address handling exceptions result in no address found
        await on_done(-1, Error.ADDRESS_NOT_FOUND)
