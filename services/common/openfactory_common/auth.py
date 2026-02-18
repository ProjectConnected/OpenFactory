import hmac
from .utils import read_secret

def load_api_key(api_key_file: str) -> str:
    k = read_secret(api_key_file)
    if len(k) < 16:
        raise RuntimeError("openfactory_api_key.txt too short; use 32+ chars")
    return k

def api_key_ok(got: str, expected: str) -> bool:
    # constant-time compare
    return hmac.compare_digest(got or "", expected or "")
