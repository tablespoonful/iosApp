#!/usr/bin/env python3
"""App Store Connect の サポートURL / プライバシーポリシーURL を apps.json に合わせて更新する。

既定はドライラン（変更内容を表示するだけ）。実際に書き込むには --apply を付ける。

必要な環境変数:
  ASC_KEY_ID    App Store Connect API キーの Key ID
  ASC_ISSUER_ID Issuer ID
  ASC_KEY_PATH  .p8 ファイルのパス（リポジトリに置かないこと）

依存: pip install pyjwt cryptography requests

対象:
  - プライバシーポリシーURL … App 情報（appInfoLocalizations.privacyPolicyUrl）
  - サポートURL           … 編集可能バージョン（appStoreVersionLocalizations.supportUrl）
更新するロケールは既定 ja（--locales で変更可）。
URL は apps.json の site.baseUrl + "/<id>.html"。

制約（重要）: どちらの URL も **編集可能なバージョン（保留中の App バージョン）が存在するときだけ**
変更できる。配信中（READY_FOR_SALE）のみで保留バージョンが無いアプリは Apple 側でロックされ、
本スクリプトは 409 を避けてスキップする。→ 次回アップデートの提出準備中に本スクリプトを再実行する。
（旧URLをリダイレクトで運用しているなら、変更しなくてもリンクは正しいページに到達する）
"""
import argparse
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.appstoreconnect.apple.com/v1"

# 編集可能とみなすバージョン状態（サポートURLはこの状態でのみ確実に更新できる）
EDITABLE_STATES = {
    "PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED",
    "METADATA_REJECTED", "INVALID_BINARY",
}


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def make_token() -> str:
    try:
        import jwt  # PyJWT
    except ImportError:
        die("PyJWT が必要です: pip install pyjwt cryptography")
    key_id = os.environ.get("ASC_KEY_ID")
    issuer = os.environ.get("ASC_ISSUER_ID")
    key_path = os.environ.get("ASC_KEY_PATH")
    if not (key_id and issuer and key_path):
        die("環境変数 ASC_KEY_ID / ASC_ISSUER_ID / ASC_KEY_PATH を設定してください")
    private_key = pathlib.Path(os.path.expanduser(key_path)).read_text()
    now = int(time.time())
    payload = {"iss": issuer, "iat": now, "exp": now + 19 * 60, "aud": "appstoreconnect-v1"}
    return jwt.encode(payload, private_key, algorithm="ES256",
                      headers={"kid": key_id, "typ": "JWT"})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="実際に ASC に書き込む（無指定はドライラン）")
    ap.add_argument("--locales", nargs="+", default=["ja"], help="更新するロケール（既定: ja）")
    ap.add_argument("--only", nargs="+", help="対象アプリの id を限定（例: dining-search）")
    args = ap.parse_args()

    try:
        import requests
    except ImportError:
        die("requests が必要です: pip install requests")

    data = json.loads((ROOT / "apps.json").read_text(encoding="utf-8"))
    base_url = data["site"]["baseUrl"].rstrip("/")
    apps = [a for a in data["apps"] if a.get("appStoreId")]
    if args.only:
        apps = [a for a in apps if a["id"] in args.only]
    if not apps:
        die("appStoreId を持つ対象アプリがありません")

    token = make_token()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] locales={args.locales}  対象 {len(apps)} アプリ\n")

    def get(path, **params):
        r = s.get(f"{API}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def patch(path, type_, id_, attrs):
        if not args.apply:
            print(f"    would PATCH {path}  {attrs}")
            return
        body = {"data": {"type": type_, "id": id_, "attributes": attrs}}
        r = s.patch(f"{API}{path}", json=body, timeout=30)
        if not r.ok:
            print(f"    FAILED {r.status_code}: {r.text[:300]}")
        else:
            print(f"    OK {path}  {attrs}")

    for app in apps:
        app_id = app["appStoreId"]
        url = f"{base_url}/{app['id']}.html"
        print(f"■ {app['name']} (id={app_id}) → {url}")

        # --- プライバシーポリシーURL: appInfoLocalizations ---
        try:
            infos = get(f"/apps/{app_id}/appInfos")["data"]
            # 編集可能な appInfo（保留バージョン）だけが privacyPolicyUrl を変更できる。
            # READY_FOR_SALE（配信中）は API/画面ともロックされ 409 になるためスキップ。
            editable_infos = [i for i in infos
                              if (i["attributes"].get("state")
                                  or i["attributes"].get("appStoreState")) in EDITABLE_STATES]
            if not editable_infos:
                print("    （編集可能な App 情報なし → プライバシーURLは次回アップデート時に設定してください）")
            for info in editable_infos:
                locs = get(f"/appInfos/{info['id']}/appInfoLocalizations")["data"]
                for loc in locs:
                    if loc["attributes"]["locale"] in args.locales:
                        patch(f"/appInfoLocalizations/{loc['id']}",
                              "appInfoLocalizations", loc["id"],
                              {"privacyPolicyUrl": url})
        except Exception as e:  # noqa: BLE001
            print(f"    プライバシーURL 取得/更新に失敗: {e}")

        # --- サポートURL: 編集可能バージョンの appStoreVersionLocalizations ---
        try:
            versions = get(f"/apps/{app_id}/appStoreVersions", limit=10)["data"]
            editable = [v for v in versions
                        if v["attributes"].get("appStoreState") in EDITABLE_STATES]
            if not editable:
                print("    （編集可能バージョンなし → サポートURLは次回アップデート時に設定してください）")
            else:
                ver = editable[0]
                locs = get(f"/appStoreVersions/{ver['id']}/appStoreVersionLocalizations")["data"]
                for loc in locs:
                    if loc["attributes"]["locale"] in args.locales:
                        patch(f"/appStoreVersionLocalizations/{loc['id']}",
                              "appStoreVersionLocalizations", loc["id"],
                              {"supportUrl": url})
        except Exception as e:  # noqa: BLE001
            print(f"    サポートURL 取得/更新に失敗: {e}")
        print()

    if not args.apply:
        print("ドライラン完了。問題なければ --apply を付けて再実行してください。")


if __name__ == "__main__":
    main()
