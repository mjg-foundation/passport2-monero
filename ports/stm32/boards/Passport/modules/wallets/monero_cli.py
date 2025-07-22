# SPDX-FileCopyrightText: © 2021 Foundation Devices, Inc. <hello@foundationdevices.com>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# monero_cli.py - Monero CLI Wallet
#

from data_codecs.qr_type import QRType
from .generic_json_wallet import create_generic_json_wallet

MoneroCLI = {
    'label': 'Monero CLI',
    'sig_types': [
        {'id': 'single-sig', 'label': 'Single-sig', 'addr_type': None, 'create_wallet': create_generic_json_wallet},
    ],
    'export_modes': [
        {'id': 'microsd', 'label': 'microSD', 'filename_pattern': 'MoneroCLI-View-Wallet.json'}
    ]
}
