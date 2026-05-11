import requests
import base64
import json
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key

URL = "http://127.0.0.1:5000/api/v1/arduino/verify"
PASS_KEY = "ВАШ_КЛЮЧ_ИЗ_БД"  # Например, "ARD-99-TX-01"
PRIVATE_KEY_PATH = "private.pem" 

def test_verify():
    try:
        # 1. Загружаем приватный ключ АРДУИНО
        with open(PRIVATE_KEY_PATH, "rb") as key_file:
            private_key = load_pem_private_key(key_file.read(), password=None)

        # 2. Подписываем данные (алгоритм PKCS1v15 + SHA256)
        message = PASS_KEY.encode('utf-8')
        signature = private_key.sign(
            message,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # 3. Кодируем в Base64 для JSON
        sign_b64 = base64.b64encode(signature).decode('utf-8')

        # 4. Отправляем запрос
        payload = {
            "pass_key": PASS_KEY,
            "sign": sign_b64
        }
        
        print(f"Отправка на {URL}...")
        response = requests.post(URL, json=payload)
        
        print(f"Статус: {response.status_code}")
        print(f"Ответ: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    test_verify()