import unicodedata

from django.apps import apps
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from taiga.auth.services import send_register_email
from taiga.auth.signals import user_registered as user_registered_signal


class TaigaOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """CloudIFF identity-safe OIDC backend.

    Stable OIDC subject and institutional username take precedence over e-mail.
    This allows users provisioned by CloudIFF before first login to bind safely
    without creating a second Taiga account.
    """

    AUTHDATA_KEY = "oidc"
    AUTHDATA_SUB_KEY = "oidc_sub"
    PLACEHOLDER_SUFFIX = "@pending.cloudif.invalid"

    def get_username(self, claims):
        candidate = claims.get("preferred_username") or claims.get("nickname")
        if not candidate:
            candidate = super().get_username(claims)
        return unicodedata.normalize("NFKC", str(candidate or ""))[:150]

    def _authdata_user(self, key, value):
        if not value:
            return None
        AuthData = apps.get_model("users", "AuthData")
        row = AuthData.objects.filter(key=key, value=str(value)).select_related("user").first()
        return row.user if row else None

    def filter_users_by_claims(self, claims):
        sub = str(claims.get("sub") or "").strip()
        user = self._authdata_user(self.AUTHDATA_SUB_KEY, sub)
        if user:
            return [user]

        username = self.get_username(claims).strip()
        if username:
            # Preserve an existing OIDC binding before considering a newly
            # pre-provisioned Taiga username with the same institutional id.
            user = self._authdata_user(self.AUTHDATA_KEY, username)
            if user:
                return [user]
            user = self.UserModel.objects.filter(username__iexact=username).first()
            if user:
                return [user]

        # A present institutional username is authoritative. Falling back to
        # e-mail here can merge two different people when a directory exposes
        # the same/shared address for multiple principals.
        if username:
            return self.UserModel.objects.none()
        email = str(claims.get("email") or "").strip().lower()
        if email:
            user = self.UserModel.objects.filter(email__iexact=email).first()
            if user:
                return [user]
        return self.UserModel.objects.none()

    def _ensure_authdata(self, user, claims, username):
        AuthData = apps.get_model("users", "AuthData")
        sub = str(claims.get("sub") or "").strip()
        if sub:
            AuthData.objects.get_or_create(
                key=self.AUTHDATA_SUB_KEY,
                value=sub,
                defaults={"user": user, "extra": {}},
            )
        if username:
            AuthData.objects.get_or_create(
                key=self.AUTHDATA_KEY,
                value=username,
                defaults={"user": user, "extra": {}},
            )

    def _update_identity_fields(self, user, claims):
        changed = []
        email = str(claims.get("email") or "").strip().lower()
        if email and email != str(user.email or "").lower():
            collision = self.UserModel.objects.filter(email__iexact=email).exclude(pk=user.pk).exists()
            current = str(user.email or "").lower()
            if not collision and (not current or current.endswith(self.PLACEHOLDER_SUFFIX)):
                user.email = email
                changed.append("email")
                if hasattr(user, "verified_email") and not user.verified_email:
                    user.verified_email = True
                    changed.append("verified_email")
        name = str(claims.get("name") or "").strip()
        if name and user.full_name != name:
            user.full_name = name
            changed.append("full_name")
        if not user.is_active:
            user.is_active = True
            changed.append("is_active")
        if changed:
            user.save(update_fields=changed)
        return user

    def create_user(self, claims):
        email = str(claims.get("email") or "").strip().lower()
        username = self.get_username(claims).strip()
        if not username:
            return None

        user = self.UserModel.objects.filter(username__iexact=username).first()

        created = False
        if not user:
            collision=bool(email and self.UserModel.objects.filter(email__iexact=email).exists())
            effective_email=email if (email and not collision) else (username+self.PLACEHOLDER_SUFFIX)
            user = self.UserModel.objects.create(
                email=effective_email,
                username=username,
                full_name=str(claims.get("name") or username),
            )
            if hasattr(user, "verified_email") and (collision or not email):
                user.verified_email=False
                user.save(update_fields=["verified_email"])
            created = True

        self._ensure_authdata(user, claims, username)
        self._update_identity_fields(user, claims)
        if created:
            send_register_email(user)
            user_registered_signal.send(sender=self.UserModel, user=user)
        return user

    def update_user(self, user, claims):
        username = self.get_username(claims).strip()
        self._ensure_authdata(user, claims, username)
        return self._update_identity_fields(user, claims)
