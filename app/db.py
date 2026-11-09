"""Neon（PostgreSQL）への接続。リクエストごとに1接続を開き、終了時にコミット/ロールバックして閉じる。"""

from pathlib import Path

import click
import psycopg
from flask import Flask, current_app, g
from psycopg.rows import dict_row

SCHEMA = Path(__file__).with_name("schema.sql")


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_conn)
    app.cli.add_command(init_db_command)


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, connect_timeout=5, row_factory=dict_row)


def get_conn() -> psycopg.Connection:
    if "db_conn" not in g:
        url = current_app.config["DATABASE_URL"]
        if not url:
            raise RuntimeError("DATABASE_URL が未設定です（.env を確認）")
        g.db_conn = connect(url)
    return g.db_conn


def query(sql: str, params: tuple | dict = (), one: bool = False):
    cur = get_conn().execute(sql, params)
    if cur.description is None:
        return None
    return cur.fetchone() if one else cur.fetchall()


def close_conn(exc: BaseException | None = None) -> None:
    conn = g.pop("db_conn", None)
    if conn is None:
        return
    try:
        if exc is None and not conn.closed:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()


def ping() -> str:
    """'ok' / 'skipped'（URL 未設定） / 'error' を返す。"""
    if not current_app.config["DATABASE_URL"]:
        return "skipped"
    try:
        query("SELECT 1", one=True)
        return "ok"
    except psycopg.Error:
        current_app.logger.exception("DB ping failed")
        return "error"


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


@click.command("init-db")
def init_db_command():
    """テーブルを作る（何度実行しても安全）。DDL 権限のあるロールの DATABASE_URL で実行する。"""
    with connect(current_app.config["DATABASE_URL"]) as conn:
        apply_schema(conn)
    click.echo("テーブルを作成しました")
