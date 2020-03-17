import json
# noinspection PyPackageRequirements
from Crypto.Cipher import AES


class MessageCrypt:
    def __init__(self, key: bytearray, iv: bytearray):
        self.key = key
        self.iv = iv

    def decrypt_data(self, data: str) -> dict:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        decrypted_bytes = cipher.decrypt(bytearray.fromhex(data))
        for i, b in enumerate(decrypted_bytes):
            if b != 0:
                decrypted_bytes = decrypted_bytes[i:]
                break
        return json.loads(decrypted_bytes.decode('utf8', errors='replace'))

    def encrypt_data(self, data: dict) -> str:
        data = json.dumps(data).encode('utf8')
        mod = 16 - (len(data) % 16)
        if mod != 16:
            data = bytearray(([0] * mod) + list(data))
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return cipher.encrypt(data).hex()
