FROM cloudif-local/taiga-back-oidc:6.10.2-c623b753
COPY oidc.py /opt/venv/lib/python3.11/site-packages/taiga_contrib_oidc_auth/oidc.py
COPY oidc_settings.py /tmp/cloudif_oidc_settings.py
RUN cat /tmp/cloudif_oidc_settings.py >> /taiga-back/settings/config.py \
 && rm -f /tmp/cloudif_oidc_settings.py \
 && /opt/venv/bin/python -m py_compile /opt/venv/lib/python3.11/site-packages/taiga_contrib_oidc_auth/oidc.py /taiga-back/settings/config.py
