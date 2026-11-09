-- Neon の権限管理（最小権限）。Neon の SQL Editor か psql で、owner ロール（neondb_owner）として実行する。
-- ※ ロールは Console ではなく SQL で作る。Console で作ったロールは neon_superuser に入り、権限が広すぎるため。
-- ※ パスワードは本人が psql で設定する（この SQL 文やファイルには書かない）。手順は docs/SETUP.md の 5-4
--
-- ロールの役割
--   neondb_owner : テーブル作成・変更（flask --app app init-db）。アプリからは使わない
--   app_rw       : アプリ（Render の DATABASE_URL）。行の読み書きだけ。テーブルの作成・削除は不可
--   backup_ro    : バックアップ（Render Cron の BACKUP_DATABASE_URL）。読み取りだけ

CREATE ROLE app_rw LOGIN;
CREATE ROLE backup_ro LOGIN;
-- psql で:  \set pw `pbpaste`  →  ALTER ROLE app_rw WITH PASSWORD :'pw';  →  \unset pw
--   （Neon は \password を拒否する。ハッシュではなく平文で受け取る仕様のため。通信は TLS）

-- public スキーマに誰でもテーブルを作れる状態をやめる
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO app_rw, backup_ro;

-- ===== app_rw: 必要な操作だけ =====
-- 在庫の記録（moves）・品目（items）・ユーザー（users）は「消さない」設計なので DELETE を与えない
GRANT SELECT, INSERT, UPDATE ON users, items, moves TO app_rw;
GRANT SELECT, INSERT, UPDATE, DELETE ON login_failures TO app_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rw;

-- ===== backup_ro: 読むだけ =====
GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO backup_ro;
-- 今後 owner が作るテーブルも読めるように
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public GRANT SELECT ON TABLES TO backup_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE neondb_owner IN SCHEMA public GRANT SELECT ON SEQUENCES TO backup_ro;

-- 確認: app_rw で DROP / DELETE ができないこと
--   psql で app_rw として接続し（\c - app_rw）、DELETE FROM moves;  → permission denied になれば OK
--   ※ SET ROLE app_rw は Neon（PG16 以降）では permission denied で使えない。作った側でも自動では成り代われないため
--   SQL Editor（owner）で確かめるなら: SELECT has_table_privilege('app_rw', 'moves', 'DELETE');  → f
