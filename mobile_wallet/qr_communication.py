import qrcode
import cv2
import json

class QRCommunication:
    @staticmethod
    def generate_qr(data, filename=None):
        try:
            # Convert data to JSON string
            json_data = json.dumps(data)

            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(json_data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            if filename:
                img.save(filename)

            return img
        except Exception as e:
            print(f"Error generating QR code: {e}")
            return None

    @staticmethod
    def scan_qr():
        try:
            # Initialize the camera
            cap = cv2.VideoCapture(0)

            # Find the QR code detector
            detector = cv2.QRCodeDetector()

            while True:
                # Capture frame-by-frame
                ret, frame = cap.read()

                # Detect and decode the QR code
                data, bbox, _ = detector.detectAndDecode(frame)

                if data:
                    # Release the camera
                    cap.release()
                    cv2.destroyAllWindows()

                    # Parse the JSON data
                    return json.loads(data)

                # Display the resulting frame
                cv2.imshow('QR Code Scanner', frame)

                # Exit if 'q' is pressed
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            # Release the camera
            cap.release()
            cv2.destroyAllWindows()

            return None
        except Exception as e:
            print(f"Error scanning QR code: {e}")
            return None