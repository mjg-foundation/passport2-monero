import json

class TransactionFormat:
    @staticmethod
    def create_transaction_data(destination_address, amount):
        return {
            'type': 'transaction',
            'destination_address': destination_address,
            'amount': amount
        }

    @staticmethod
    def create_signed_transaction_data(signed_tx):
        return {
            'type': 'signed_transaction',
            'signed_tx': signed_tx
        }

    @staticmethod
    def parse_transaction_data(data):
        if data['type'] == 'transaction':
            return {
                'destination_address': data['destination_address'],
                'amount': data['amount']
            }
        elif data['type'] == 'signed_transaction':
            return {
                'signed_tx': data['signed_tx']
            }
        else:
            raise ValueError("Invalid transaction data type")