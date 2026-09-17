# CloudIFF shared-workstation identity isolation.
# The IdP must ask for credentials/identity again instead of silently reusing
# an earlier Authentik browser session from another lab user.
if ENABLE_OIDC_AUTH:
    OIDC_AUTH_REQUEST_EXTRA_PARAMS = {
        "prompt": os.getenv("OIDC_AUTH_PROMPT", "login"),
    }
