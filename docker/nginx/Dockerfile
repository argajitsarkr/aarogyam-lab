FROM nginx:1.27-alpine
RUN apk add --no-cache openssl
COPY templates/ /etc/nginx/templates/
COPY 05-selfsigned-cert.sh /docker-entrypoint.d/05-selfsigned-cert.sh
RUN chmod +x /docker-entrypoint.d/05-selfsigned-cert.sh && rm -f /etc/nginx/conf.d/default.conf
