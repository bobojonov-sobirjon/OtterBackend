import os
import json
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

    # Most robust option: point to the downloaded Firebase service account json
    # (e.g. FIREBASE_CREDENTIALS_FILE=path/to/serviceAccountKey.json)
    cred_file = os.getenv("FIREBASE_CREDENTIALS_FILE", "").strip().strip('"').strip("'")
    if cred_file:
        cred = credentials.Certificate(cred_file)
        return firebase_admin.initialize_app(cred)

    # Common convention supported by Google libraries
    google_app_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip().strip('"').strip("'")
    if google_app_creds:
        cred = credentials.Certificate(google_app_creds)
        return firebase_admin.initialize_app(cred)

    # Alternative: store the whole service account JSON as a single env var
    # (useful in Docker/CI). Example: FIREBASE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
    sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if sa_json:
        try:
            cred_dict = json.loads(sa_json)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Firebase Admin credential error: FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON ({e})."
            ) from e
        cred = credentials.Certificate(cred_dict)
        return firebase_admin.initialize_app(cred)

    private_key = os.getenv("FIREBASE_PRIVATE_KEY", "")
    # dotenv sometimes keeps surrounding quotes; also normalize newlines for PEM
    private_key = private_key.strip().strip('"').strip("'")
    private_key = private_key.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n")

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

    # Fail fast with a clearer error than cryptography's "InvalidByte(...)"
    if not private_key or "BEGIN PRIVATE KEY" not in private_key:
        raise ValueError(
            "Firebase Admin credential error: FIREBASE_PRIVATE_KEY is missing or not a PEM key. "
            "Prefer setting FIREBASE_CREDENTIALS_FILE (or GOOGLE_APPLICATION_CREDENTIALS) to the service account json file path."
        )

    try:
        cred = credentials.Certificate(cred_dict)
        return firebase_admin.initialize_app(cred)
    except Exception as e:
        raise ValueError(
            "Firebase Admin credential error: service account credentials could not be loaded from env vars. "
            "Most likely FIREBASE_PRIVATE_KEY is malformed. "
            "Fix by using FIREBASE_CREDENTIALS_FILE/GOOGLE_APPLICATION_CREDENTIALS with the downloaded service account JSON."
        ) from e


def verify_firebase_id_token(id_token: str) -> dict:
    app = get_firebase_app()
    return auth.verify_id_token(id_token, app=app)

