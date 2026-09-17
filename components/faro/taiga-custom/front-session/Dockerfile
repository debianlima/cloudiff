FROM cloudif-local/taiga-front-oidc:6.10.3-c623b753-r2
COPY cloudif-session-isolation.js /usr/share/nginx/html/plugins/cloudif-session-isolation.js
RUN sed -i 's#<head>#<head>\n    <script src="/plugins/cloudif-session-isolation.js"></script>#' /usr/share/nginx/html/index.html \
 && grep -q '/plugins/cloudif-session-isolation.js' /usr/share/nginx/html/index.html
