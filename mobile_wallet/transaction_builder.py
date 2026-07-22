import json
from monero.wallet import Wallet

class TransactionBuilder:
    def __init__(self, wallet_path, password):
        self.wallet = Wallet(wallet_path, password)

    def build_transaction(self, destination_address, amount):
        try:
            # Create a new transaction
            tx = self.wallet.new_tx()
            tx.add_output(destination_address, amount)

            # Get the unsigned transaction data
            unsigned_tx = tx.serialize_unsigned()

            return unsigned_tx
        except Exception as e:
            print(f"Error building transaction: {e}")
            return None

    def publish_transaction(self, signed_tx):
        try:
            # Deserialize the signed transaction
            tx = self.wallet.deserialize_signed(signed_tx)

            # Publish the transaction to the network
            tx_id = self.wallet.publish_tx(tx)

            return tx_id
        except Exception as e:
            print(f"Error publishing transaction: {e}")
            return None