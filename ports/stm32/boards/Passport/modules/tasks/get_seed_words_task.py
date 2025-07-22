# SPDX-FileCopyrightText: © 2022 Foundation Devices, Inc. <hello@foundationdevices.com>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# get_seed_words_task.py - Task to get the seed words of the current wallet.

import stash
import moneromnemonics
from monero_mnemonic_languages import enum_values as languages


async def get_seed_words_task(on_done):
    try:
        with stash.SensitiveValues() as sv:
            assert sv.mode == 'words'

            words = moneromnemonics.legacy.from_seed(sv.raw, languages.english).split(' ')
            await on_done(words, None)

    except Exception as e:
        # print('get_seed_words_task(): Exception: {}'.format(e))
        # Unable to read seed!
        await on_done(None, None, '{}'.format(e))
