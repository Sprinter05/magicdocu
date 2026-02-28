FROM postgres:18-trixie

RUN apt-get update &&\
    apt-get install -y postgresql-18-pgvector &&\
    rm -rf /var/lib/apt/lists/*

COPY ./docker/postgres/01-init.sql /docker-entrypoint-initdb.d/

HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
    CMD pg_isready -U postgres || exit 1