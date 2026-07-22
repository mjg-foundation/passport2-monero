import os
import json

class MicroSDCommunication:
    @staticmethod
    def write_to_sd(data, filename):
        try:
            # Convert data to JSON string
            json_data = json.dumps(data)

            # Write data to file
            with open(filename, 'w') as f:
                f.write(json_data)

            return True
        except Exception as e:
            print(f"Error writing to microSD: {e}")
            return False

    @staticmethod
    def read_from_sd(filename):
        try:
            # Read data from file
            with open(filename, 'r') as f:
                json_data = f.read()

            # Parse the JSON data
            return json.loads(json_data)
        except Exception as e:
            print(f"Error reading from microSD: {e}")
            return None