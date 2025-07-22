# SPDX-FileCopyrightText: © 2022 Foundation Devices, Inc. <hello@foundationdevices.com>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# SPDX-FileCopyrightText: 2018 Coinkite, Inc. <coldcardwallet.com>
# SPDX-License-Identifier: GPL-3.0-only
#
# (c) Copyright 2018 by Coinkite Inc. This file is part of Coldcard <coldcardwallet.com>
# and is covered by GPLv3 license found in COPYING.
#
# verify_address_flow.py - Scan an address QR code and verify that it belongs to this Passport.

from flows import Flow
from common import ui
import microns
from xmr.addresses import AddressTypes

_NUM_TO_CHECK = const(100)

class VerifyAddressFlow(Flow):
    def __init__(self, sig_type=None, multisig_wallet=None):
        initial_state = self.scan_address

        super().__init__(initial_state=initial_state, name='VerifyAddressFlow')
        self.acct_num = ui.get_active_account().get('acct_num')
        self.sig_type = sig_type
        self.multisig_wallet = multisig_wallet
        self.is_multisig = False
        self.found_addr_idx = None
        self.addr_type = None
        self.network_type = None
        self.address = None

        self.lower_bound = 0
        self.upper_bound = self.lower_bound + _NUM_TO_CHECK

    async def scan_address(self):
        import chains
        from pages import ErrorPage, ScanQRPage
        from xmr.addresses import get_address_info

        result = await ScanQRPage(
            left_micron=microns.Back,
            right_micron=None).show()

        if result is None:
            if not self.back():
                self.set_result(False)
                return
            return
        elif result.is_failure():
            await ErrorPage(text='Unable to scan QR code.').show()
            self.set_result(False)
            return

        # print('{}, {}, {}'.format(result.data, result.error, result.qr_type))
        self.address = result.data

        # Simple check on the data type first
        chain_name = chains.current_chain().name
        self.address, self.network_type, self.addr_type = get_address_info(self.address)
        if self.addr_type == None:
            await ErrorPage("Not a valid {} address.".format(chain_name)).show()
            return
        #TODO: Compare used network to the address network
        #if chains.current_chain().net != self.network_type:
        #    await ErrorPage("Address not on the same network as this wallet.").show()
        #    return

        if self.addr_type == AddressTypes.PRIMARY or self.addr_type == AddressTypes.INTEGRATED:
            self.lower_bound = 0
            self.upper_bound = 1
        elif self.acct_num == 0:
            self.lower_bound += 1
            self.upper_bound += 1

        self.goto(self.search_for_address)

    async def search_for_address(self):
        from tasks import search_for_address_task
        from utils import spinner_task

        # print('CHECKING: self.lower_bound={}  self.upper_bound={}'.format(self.lower_bound, self.upper_bound))
        (addr_idx, error) = await spinner_task(
            'Searching Addresses',
            search_for_address_task,
            args=[self.acct_num,
                self.address,
                self.addr_type,
                self.network_type,
                self.lower_bound,
                self.upper_bound])

        if addr_idx >= 0:
            self.found_addr_idx = addr_idx
            self.goto(self.found)
        else:
            self.goto(self.not_found)

    async def not_found(self):
        from pages import ErrorPage

        if self.addr_type == AddressTypes.PRIMARY or self.addr_type == AddressTypes.INTEGRATED:
            msg = 'That {} address does not belong to this wallet.'.format('primary' if self.addr_type == AddressTypes.PRIMARY else 'integerated')
            await ErrorPage(msg, left_micron=microns.Cancel, right_micron=None).show()
            self.set_result(False)
        else:
            msg = 'Address Not Found\nRange Checked:\n'

            msg += 'Subaddresses: ({}, {}-{})'.format(self.acct_num, self.lower_bound, self.upper_bound-1)

            msg += '\n\nContinue searching?'

            result = await ErrorPage(msg, left_micron=microns.Cancel, right_micron=microns.Checkmark).show()
            if result:
                self.lower_bound = self.upper_bound
                self.upper_bound = self.lower_bound + _NUM_TO_CHECK
                self.goto(self.search_for_address)
            else:
                self.set_result(False)

    async def found(self):
        from pages import SuccessPage

        if self.addr_type == AddressTypes.PRIMARY:
            address_type_name = 'Primary'
            major_index = 0
            minor_index = self.found_addr_idx
        elif self.addr_type == AddressTypes.INTEGRATED:
            address_type_name = 'Integrated'
            major_index = 0
            minor_index = self.found_addr_idx
        else: #if self.addr_type == AddressTypes.SUB:
            address_type_name = 'Sub'
            major_index = self.acct_num
            minor_index = self.found_addr_idx

        msg = '''{}

{} Address ({}, {})'''.format(
            self.address,
            address_type_name,
            major_index,
            minor_index)

        await SuccessPage(msg).show()
        self.set_result(True)
