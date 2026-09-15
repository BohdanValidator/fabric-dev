# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-17-jdk-headless \
        procps \
        git \
        ca-certificates \
        curl \
        gnupg \
        make \
    && rm -rf /var/lib/apt/lists/*

# ODBC driver for the SQL analytics endpoint
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > /usr/share/keyrings/microsoft.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql.list \
    && apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 10 pyspark==3.5.1 delta-spark==3.1.0

COPY requirements-local.txt /tmp/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 300 --retries 10 -r /tmp/requirements-local.txt

COPY jars/ /opt/spark-jars/
ENV SPARK_EXTRA_JARS=/opt/spark-jars