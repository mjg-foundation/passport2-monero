import json
from monero.wallet import Wallet

class Signing:
    def __init__(self, wallet_path, password):
        self.wallet = Wallet(wallet_path, password)

    def sign_transaction(self, unsigned_tx):
        try:
            # Deserialize the unsigned transaction
            tx = self.wallet.deserialize_unsigned(unsigned_tx)

            # Sign the transaction
            signed_tx = self.wallet.sign_tx(tx)

            # Serialize the signed transaction
            return signed_tx.serialize_signed()
        except Exception as e:
            print(f"Error signing transaction: {e}")
            return None