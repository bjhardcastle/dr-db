ARG POSTGRES_IMAGE=pgautoupgrade/pgautoupgrade:17-bookworm

FROM ${POSTGRES_IMAGE} AS builder

ARG CARGO_PGRX_VERSION=0.16.0
ARG PG_PARQUET_VERSION=0.5.1
ARG RUST_VERSION=1.90.0

ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV PATH=/usr/local/cargo/bin:${PATH}

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        build-essential \
        ca-certificates \
        curl \
        git \
        libssl-dev \
        pkg-config \
        postgresql-server-dev-17 \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 --silent --show-error --fail \
        https://sh.rustup.rs \
        | sh -s -- --default-toolchain ${RUST_VERSION} --profile minimal -y \
    && cargo install --locked cargo-pgrx@${CARGO_PGRX_VERSION}

WORKDIR /tmp/pg_parquet

RUN git clone --depth 1 --branch v${PG_PARQUET_VERSION} \
        https://github.com/CrunchyData/pg_parquet.git . \
    && cargo pgrx init --pg17 /usr/bin/pg_config \
    && cargo pgrx install --release --features pg17 --no-default-features

FROM ${POSTGRES_IMAGE}

COPY --from=builder /usr/lib/postgresql/17/lib/pg_parquet.so \
    /usr/lib/postgresql/17/lib/pg_parquet.so
COPY --from=builder /usr/share/postgresql/17/extension/pg_parquet* \
    /usr/share/postgresql/17/extension/
