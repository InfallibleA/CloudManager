FROM nginx:alpine

# Единая точка входа: балансировка реплик api, rate limiting и прокси на Garage.
# default.conf.template кладется в /etc/nginx/templates: штатный entrypoint образа
# (20-envsubst-on-templates.sh) сам подставляет в него переменные окружения
# (GARAGE_HOST/GARAGE_PORT) и рендерит результат в /etc/nginx/conf.d/default.conf.
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/proxy_params.conf /etc/nginx/proxy_params.conf
