FROM pgvector/pgvector:pg16

USER root

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    postgresql-server-dev-16 \
    flex \
    bison \
    && rm -rf /var/lib/apt/lists/*

# Install Apache AGE (Graph Database)
RUN cd /tmp && \
    git clone https://github.com/apache/age.git && \
    cd age && \
    (git checkout PG16 || echo "PG16 branch not found, using default") && \
    make install && \
    cd .. && \
    rm -rf age

# Configure shared_preload_libraries
# We append to the default config.
RUN echo "shared_preload_libraries = 'age'" >> /usr/share/postgresql/postgresql.conf.sample

USER postgres
