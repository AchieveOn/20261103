# Render Cron Job 用: pg_dump 17（Neon と同じメジャー版）+ Python
# Debian 標準の postgresql-client は版が古く PG17 をダンプできないので、PGDG の apt リポジトリから入れる
FROM python:3.13-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc \
 && . /etc/os-release \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client-17 \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /job
COPY requirements.txt backup_db.py ./
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home job
USER job
CMD ["python", "backup_db.py"]
