import unittest
from mobile_wallet.transaction_builder import TransactionBuilder

class TestTransactionBuilder(unittest.TestCase):
    def setUp(self):
        # Initialize with test wallet path and password
        self.tx_builder = TransactionBuilder("test_wallet", "test_password")

    def test_build_transaction(self):
        # Test building a transaction
        unsigned_tx = self.tx_builder.build_transaction("test_address", 1000000)
        self.assertIsNotNone(unsigned_tx)

    def test_publish_transaction(self):
        # Test publishing a transaction (mock signed transaction)
        tx_id = self.tx_builder.publish_transaction("signed_tx_data")
        self.assertIsNotNone(tx_id)

if __name__ == '__main__':
    unittest.main()