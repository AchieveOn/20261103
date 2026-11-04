-- 喫茶店の在庫管理スキーマ（PostgreSQL 17 / Neon）
-- 適用: flask --app app init-db（DDL 権限のある owner ロールの接続で実行する。app_rw では実行できない）
-- 在庫数の列は持たない。在庫 = moves.delta の合計（取消済みを除く）

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    login_id      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,                       -- scrypt（ソルトつき）。平文は保存しない
    role          TEXT NOT NULL CHECK (role IN ('owner', 'staff')),
    session_gen   INTEGER NOT NULL DEFAULT 0,          -- ログアウトで+1。古い Cookie を無効化
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS login_failures (
    login_id     TEXT PRIMARY KEY,                     -- 存在しない ID も同じように数える
    count        INTEGER NOT NULL,
    locked_until TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS items (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    unit          TEXT NOT NULL,
    threshold     INTEGER NOT NULL DEFAULT 0 CHECK (threshold >= 0),   -- 発注点
    lead_days     INTEGER NOT NULL DEFAULT 3 CHECK (lead_days >= 0),   -- 発注から届くまでの日数
    supplier_enc  TEXT,                                -- 仕入先（Fernet 暗号文）
    unit_cost_enc TEXT,                                -- 仕入単価（Fernet 暗号文）
    note_enc      TEXT,                                -- 店主メモ（Fernet 暗号文）
    archived      BOOLEAN NOT NULL DEFAULT FALSE,      -- 取扱終了は論理削除
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS moves (
    id         BIGSERIAL PRIMARY KEY,
    item_id    BIGINT NOT NULL REFERENCES items(id),
    kind       TEXT NOT NULL CHECK (kind IN ('in', 'out', 'count')),
    delta      INTEGER NOT NULL,
    note       TEXT NOT NULL DEFAULT '',
    user_id    BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    voided_at  TIMESTAMPTZ,                            -- 取消は削除せず印を付ける（監査用）
    voided_by  BIGINT REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_moves_item ON moves (item_id, created_at);
