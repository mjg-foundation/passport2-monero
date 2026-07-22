from sign_psbt_flow import SignPsbtFlow
from monero_psbt import MoneroPsbt

class SignMoneroPsbtFlow(SignPsbtFlow):
    def __init__(self, device, psbt):
        super().__init__(device, psbt)
        self.monero_psbt = MoneroPsbt(psbt)

    def validate_transaction(self):
        # Monero-specific validation logic
        if not self.monero_psbt.validate():
            raise ValueError("Invalid Monero transaction data")

    def sign_transaction(self):
        # Monero-specific signing logic
        self.monero_psbt.sign()