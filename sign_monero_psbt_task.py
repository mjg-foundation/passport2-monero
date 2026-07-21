from sign_psbt_task import SignPsbtTask
from monero_psbt import MoneroPsbt

class SignMoneroPsbtTask(SignPsbtTask):
    def __init__(self, device, psbt):
        super().__init__(device, psbt)
        self.monero_psbt = MoneroPsbt(psbt)

    def run(self):
        # Monero-specific signing task
        self.monero_psbt.sign()
        return self.monero_psbt.serialize()