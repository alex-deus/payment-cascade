FROM python:3.14.5-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_SYSTEM_PYTHON=1
ENV WORK_DIR="/application/src"
ENV USER=payment
ENV GROUP=payment

EXPOSE 5555
EXPOSE 8000

WORKDIR ${WORK_DIR}

RUN addgroup --system ${GROUP} &&\
    adduser --system --home ${WORK_DIR}/../user --ingroup ${GROUP} ${USER} --shell /bin/sh &&\
    chown -R ${USER}:${GROUP} ${WORK_DIR}/..

RUN apk add --no-cache git wget grep \
    && rm -rf /var/cache/apk/*

RUN pip install --no-cache-dir uv \
    && rm -rf /root/.cache/pip

ADD pyproject.toml uv.lock .
RUN uv pip install -r pyproject.toml \
    && rm -rf /root/.cache/uv

COPY . .

RUN chown -R ${USER}:${GROUP} .
USER ${USER}

ENTRYPOINT ["/application/src/docker-entrypoint.sh"]
