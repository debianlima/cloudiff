#!/usr/bin/env python3
import base64, hashlib, hmac, json, sys, time

secret = sys.argv[1].encode()
role = sys.argv[2]
now = int(time.time())

header = {"alg": "HS256", "typ": "JWT"}
payload = {
    "iss": "supabase",
    "ref": "cloudif",
    "role": role,
    "iat": now,
    "exp": now + 10 * 365 * 24 * 3600,
}

def b64(x):
    return base64.urlsafe_b64encode(json.dumps(x, separators=(",", ":")).encode()).rstrip(b"=")

msg = b64(header) + b"." + b64(payload)
sig = base64.urlsafe_b64encode(hmac.new(secret, msg, hashlib.sha256).digest()).rstrip(b"=")
print((msg + b"." + sig).decode())
