FROM postgres:18-trixie

RUN apt-get update &&\
    apt-get install -y postgresql-18-pgvector &&\
    rm -rf /var/lib/apt/lists/*

COPY ./docker/postgres/init.sql /docker-entrypoint-initdb.db/init.sql

HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
    CMD pg_isready -U postgres || exit 1