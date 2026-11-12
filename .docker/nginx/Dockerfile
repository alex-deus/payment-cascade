FROM nginx:mainline-alpine

ARG DOMAIN
ENV DOMAIN $DOMAIN

COPY nginx.conf /etc/nginx/nginx.conf

COPY conf.d/site.conf.template /tmp/site.conf.template
RUN envsubst '${DOMAIN}' < /tmp/site.conf.template > /etc/nginx/conf.d/default.conf && rm /tmp/site.conf.template
