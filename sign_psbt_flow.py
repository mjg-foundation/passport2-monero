# Add Monero as an option in the transaction type selection
def select_transaction_type(self):
    options = [
        ("Bitcoin", self.sign_bitcoin_psbt),
        ("Monero", self.sign_monero_psbt),
        # Other transaction types...
    ]
    # Existing selection logic...