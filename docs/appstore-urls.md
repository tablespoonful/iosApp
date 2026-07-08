# App Store Connect のサポート/プライバシーURL 差し替え

配信中アプリの旧URL（`app3.html` 等）はリダイレクトで動作し続けますが、**新しい意味ベースURLへ
直接向ける**とリダイレクトを介さずに済み、リンクも分かりやすくなります。以下に対応表と反映方法を示します。

- 公開ベースURL：`https://tablespoonful.github.io/iosApp/`
- サポートURL / プライバシーポリシーURL とも、各アプリの `<id>.html` を設定します。

## アプリ別 URL 対応表
| アプリ | App Store ID | 設定するURL（サポート＝プライバシー）|
|---|---|---|
| 西暦和暦変換器 | 6711329947 | https://tablespoonful.github.io/iosApp/era-converter.html |
| 10秒止めゲーム | 6733242058 | https://tablespoonful.github.io/iosApp/stop-game.html |
| 外食サーチ | 6736398611 | https://tablespoonful.github.io/iosApp/dining-search.html |
| シンプル写真帳 | 6739175712 | https://tablespoonful.github.io/iosApp/photo-book.html |

## 方法A：ASC 画面で手動（推奨・確実）
新規ビルド提出は不要です。
- **プライバシーポリシーURL**：対象アプリ → **App のプライバシー**（または App 情報）→ プライバシーポリシーURL を上表に更新 → 保存。いつでも変更可。
- **サポートURL**：対象アプリ → 編集可能なバージョン（"提出準備中" など）→ **プロモーション/一般情報** の「サポートURL」を上表に更新 → 保存。
  - 編集可能なバージョンが無い場合でも、App 情報側の値は更新できます。次回アップデート時に反映されます。

## 方法B：スクリプトで一括（ASC API キーが必要）
`scripts/set_appstore_urls.py` が `apps.json` を読み、ASC API で各アプリの
プライバシーポリシーURL（App 情報・ja）とサポートURL（編集可能バージョン・ja）を更新します。

1. App Store Connect → ユーザーとアクセス → **統合（Keys）** で API キー（.p8）を発行（役割は App Manager 以上）。
2. 環境変数を設定（`.p8` はリポジトリに置かない）：
   ```bash
   export ASC_KEY_ID=XXXXXXXXXX
   export ASC_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   export ASC_KEY_PATH=~/.appstoreconnect/private_keys/AuthKey_XXXXXXXXXX.p8
   ```
3. 依存をインストール：`pip install pyjwt cryptography requests`
4. **まずドライラン**（変更内容を表示するだけ・書き込まない）：
   ```bash
   python3 scripts/set_appstore_urls.py
   ```
5. 内容を確認してから適用：
   ```bash
   python3 scripts/set_appstore_urls.py --apply
   ```

> スクリプトは既定でドライランです。`--apply` を付けたときだけ ASC に書き込みます。
> locale は `ja`（日本語）を対象にします。英語ロケール等も更新したい場合は `--locales ja en-US` のように指定。
