# SPDX-FileCopyrightText: © 2022 Foundation Devices, Inc. <hello@foundationdevices.com>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# restore_seed_flow.py -Restore a seed to Passport by entering the seed words.


from flows import Flow
import microns
from pages import ErrorPage, PredictiveTextInputPage, SuccessPage, QuestionPage
from utils import spinner_task
from tasks import save_seed_task
from monero_mnemonic_languages import enum_values as languages


class RestoreSeedFlow(Flow):
    def __init__(self, refresh_cards_when_done=False):
        super().__init__(initial_state=self.choose_restore_method, name='RestoreSeedFlow')
        self.refresh_cards_when_done = refresh_cards_when_done
        self.seed_words = []

    async def choose_restore_method(self):
        from pages import ChooserPage

        options = [{'label': '24 words (legacy)', 'value': 24},
                   {'label': '25 words (legacy)', 'value': 25}]

        choice = await ChooserPage(card_header={'title': 'Seed Format'}, options=options).show()

        if choice is None:
            self.set_result(False)
            return

        if isinstance(choice, int):
            self.seed_length = choice
            self.goto(self.explain_input_method)
        else:
            self.goto(choice)

    async def scan_qr(self):
        from flows import ScanPrivateKeyQRFlow
        result = await ScanPrivateKeyQRFlow(
            refresh_cards_when_done=self.refresh_cards_when_done).run()
        self.set_result(result)

    async def explain_input_method(self):
        from pages import InfoPage

        result = await InfoPage([
            "Passport uses predictive text input to help you restore your seed words.",
            "Example: If you want to enter \"car\", type 2 2 7 and select \"car\" from the dropdown."]
        ).show()
        self.goto(self.enter_seed_words)

    async def enter_seed_words(self):
        used_word_list = 'moneroenglish'
        result = await PredictiveTextInputPage(
            word_list=used_word_list,
            total_words=self.seed_length,
            initial_words=self.seed_words).show()
        if result is None:
            cancel = await QuestionPage(
                text='Cancel seed entry? All progress will be lost.').show()
            if cancel:
                self.set_result(False)
                return
        else:
            self.seed_words, self.prefixes = result
            self.goto(self.validate_seed_words)

    async def validate_seed_words(self):
        import moneromnemonics

        self.mnemonic = ' '.join(self.seed_words)

        if not moneromnemonics.legacy.check(self.mnemonic, languages.english):
            self.goto(self.invalid_seed)
        else:
            self.goto(self.valid_seed)

    async def invalid_seed(self):
        result = await ErrorPage(text='Seed phrase is invalid. One or more of your seed words is incorrect.',
                                 left_micron=microns.Cancel, right_micron=microns.Retry).show()
        if result is None:
            cancel = await QuestionPage(
                text='Cancel seed entry? All progress will be lost.').show()
            if cancel:
                self.set_result(False)
                return

        # Retry
        self.goto(self.enter_seed_words)

    async def valid_seed(self):
        import moneromnemonics

        entropy = moneromnemonics.legacy.to_seed(self.mnemonic, languages.english)

        (error,) = await spinner_task('Saving seed', save_seed_task, args=[entropy])
        if error is None:
            import common
            await SuccessPage(text='New seed restored and saved.').show()

            if self.refresh_cards_when_done:
                common.ui.full_cards_refresh()

                await self.wait_to_die()
            else:
                self.set_result(True)
        else:
            # WIP: This is not complete - offer backup?
            pass
