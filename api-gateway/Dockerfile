FROM nginx:1.27-alpine

RUN apk add --no-cache gettext

COPY hide-upstream-cors.inc /etc/nginx/hide-upstream-cors.inc
COPY nginx.conf.template /etc/nginx/templates/nginx.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/docker-entrypoint.sh"]
