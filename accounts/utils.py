import os
from functools import lru_cache

import firebase_admin
from firebase_admin import auth, credentials


@lru_cache(maxsize=1)
def get_firebase_app():
    """
    Инициализация Firebase Admin из переменных окружения (.env).
    ВАЖНО: PRIVATE_KEY в .env обычно хранится с '\\n' — конвертируем в реальные переносы.
    """
    if firebase_admin._apps:
        return list(firebase_admin._apps.values())[0]

    private_key = os.getenv("FIREBASE_PRIVATE_KEY", "")
    private_key = private_key.replace("\\n", "\n")

    cred_dict = {
        "type": os.getenv("FIREBASE_TYPE", "service_account"),
        "project_id": os.getenv("FIREBASE_PROJECT_ID", ""),
        "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID", ""),
        "private_key": private_key,
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL", ""),
        "client_id": os.getenv("FIREBASE_CLIENT_ID", ""),
        "auth_uri": os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
        "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL", ""),
        "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL", ""),
        "universe_domain": os.getenv("FIREBASE_UNIVERSE_DOMAIN", "googleapis.com"),
    }

    cred = credentials.Certificate(cred_dict)
    return firebase_admin.initialize_app(cred)


def verify_firebase_id_token(id_token: str) -> dict:
    app = get_firebase_app()
    return auth.verify_id_token(id_token, app=app)

