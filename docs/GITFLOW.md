# ブランチ運用（GitFlow）

## ブランチ

| ブランチ | 役割 | どこから切る | どこへ戻す |
|---|---|---|---|
| `main` | 本番（Render が自動デプロイ） | — | — |
| `develop` | 開発の統合先 | main（初回だけ） | — |
| `feature/<名前>` | 新機能 | develop | develop |
| `bugfix/<名前>` | develop 上のバグ修正 | develop | develop |
| `release/X.Y.Z` | リリース準備（版上げ・最終確認） | develop | main と develop |
| `hotfix/X.Y.Z` | 本番の緊急修正 | main | main と develop |

名前は小文字・数字・`-` `.` `_`。例: `feature/order-memo`、`release/1.0.0`。

## 普段の流れ

```bash
git switch develop && git pull
git switch -c feature/order-memo
# …作業してコミット（pre-commit が自動チェック）…
git push -u origin feature/order-memo     # pre-push がテストを実行
gh pr create --base develop --fill        # GitHub で PR → CI が通ったらマージ
```

## リリース

```bash
git switch develop && git pull
git switch -c release/1.0.0
git push -u origin release/1.0.0
gh pr create --base main --title "Release 1.0.0" --fill
# main にマージ → Render が CI 通過後に自動デプロイ
git switch main && git pull && git tag -a v1.0.0 -m "1.0.0" && git push origin v1.0.0
gh pr create --base develop --head release/1.0.0 --title "Back-merge 1.0.0" --fill
```

hotfix は `main` から `hotfix/1.0.1` を切り、同じく main と develop の両方へ PR。

## 何が止めてくれるか

| タイミング | 仕組み | 止めるもの |
|---|---|---|
| ブランチ作成時 | `.githooks/post-checkout` | 規則外の名前を警告（止めない） |
| コミット時 | `.githooks/pre-commit` | main/develop への直接コミット・規則外の名前・`.env` 等のファイル・Betterleaks が検出したキー |
| ローカルマージ時 | `.githooks/pre-merge-commit` | feature → main のような逆流 |
| push 時 | `.githooks/pre-push` | main/develop への直接 push（初回作成のみ可）・規則外の名前・テスト失敗 |
| PR 時 | `.github/workflows/gitflow.yml` | 合流方向の違反（hooks をすり抜けても止める） |
| PR 時 | `.github/workflows/test-guard.yml` | テスト削除・テスト数の減少・skip の追加（ラベル `test-change-approved` で許可） |
| AI 操作時 | `.claude/hooks/guard.py` | `--no-verify`・main/develop への push |

`git commit --no-verify` で hooks は外せますが、GitHub 側（CI・GitFlow・Betterleaks）で同じことを再チェックするので、すり抜けても PR で止まります。**main / develop のブランチ保護（PR 必須・チェック必須）を GitHub で設定すると完成**です（docs/SETUP.md の手順 4）。

## hooks の有効化

クローンした人は1回だけ:

```bash
bash scripts/setup.sh
```

（中身は `git config core.hooksPath .githooks`）
