# Containerized connector: runs the loader on any host/scheduler (cron, K8s CronJob, ECS).
# The connector is the only part that runs outside Snowflake; it needs network access to the
# source database. Everything else (transform, governance, orchestration) runs in Snowflake.
FROM python:3.12-slim

# Microsoft ODBC Driver 18 for the SQL Server source.
ENV ACCEPT_EULA=Y
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl gnupg apt-transport-https \
 && curl -sSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY loader ./loader
COPY config ./config

# Snowflake creds: mount ~/.snowflake/connections.toml or pass via a secret volume.
# Source creds: in the loader config (trusted auth) or an env-referenced connection string.
ENTRYPOINT ["python", "-m", "loader"]
CMD ["--config", "config/loader.control.yaml"]
