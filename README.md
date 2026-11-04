# 喫茶在庫（20261103）

喫茶店の在庫管理 Web アプリ。仕入先・原価などの秘匿情報を暗号化して扱います。

- **アプリ**: Flask（フロント + アプリサーバー）on Render / DB: Neon（PostgreSQL 17）
- **守り**: Claude Code hooks → Git hooks（GitFlow・Betterleaks）→ GitHub Actions（CI・CodeQL・Test guard）→ Render（CI 通過後だけ自動デプロイ）→ Neon（最小権限ロール）→ Gmail（暗号化バックアップ）

## できること

- 在庫一覧（在庫切れ → 要発注 → まもなく → 十分 の順）・1日の使用量・残り日数
- 入荷 / 使用 / 棚卸しの記録（記録者つき）、店主による取消（削除せず履歴に残す）
- 役割: 店主（品目の登録・編集、仕入先・単価・メモの閲覧、取消）／スタッフ（閲覧と記録だけ）

## ドキュメント

| 読むもの                                     | 内容                                       |
| -------------------------------------------- | ------------------------------------------ |
| [docs/SETUP.md](docs/SETUP.md)               | 構築手順（済み / 本人作業の区別つき）      |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 構成図・各層の役割・セキュリティ対策の一覧 |
| [docs/GITFLOW.md](docs/GITFLOW.md)           | ブランチ運用と hooks                       |
| [LOG.md](LOG.md)                             | 作業記録                                   |

## すぐ始める

```bash
bash scripts/setup.sh
TEST_DATABASE_URL=postgresql://localhost/cafe_test .venv/bin/pytest
```
