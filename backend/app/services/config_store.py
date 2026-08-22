"""リソース設定ファイルの保存/読込/バリデーション。

設定本体は storage/config/<type>/<id>.<json|yaml|py> に保存する。
DB には名前・概要・公開範囲のみ保存し、設定はこのモジュール経由でファイル管理する。
"""
import ast
import importlib.util
import json
import os
import re
from pathlib import Path

import yaml

# リソース種別ごとの許可フォーマット
ALLOWED_FORMATS = ("json", "yaml", "python", "markdown")

# リソース種別ごとのデフォルトフォーマット (UI の固定表示と揃える)
DEFAULT_FORMAT_BY_TYPE = {
    "model": "json",
    "system_prompt": "markdown",
    "rule": "markdown",
    "mcp": "json",
    "skill": "markdown",  # YAMLフロントマター付きMarkdown
    "tool": "json",
    "hook": "json",
    "loop": "markdown",
}

# storage ルート (backend/app から見てプロジェクトルート/storage)
_STORAGE_ROOT = Path(os.getenv("NADA_STORAGE_ROOT", "/app/storage"))
if not _STORAGE_ROOT.exists():
    _STORAGE_ROOT = Path(__file__).resolve().parents[3] / "storage"

CONFIG_DIR = _STORAGE_ROOT / "config"


def config_file_path(resource_type: str, resource_id: str, fmt: str) -> Path:
    """リソースの設定ファイルパスを返す。"""
    ext = {"python": "py", "markdown": "md"}.get(fmt, fmt)
    return CONFIG_DIR / resource_type / f"{resource_id}.{ext}"


def validate_config(fmt: str, text: str) -> tuple[bool, str | None]:
    """設定テキストがフォーマットとして妥当か検証する。

    Returns:
        (ok, error_message) — ok=True ならエラーなし。
    """
    if fmt == "json":
        try:
            json.loads(text)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"JSON構文エラー: {e}"
    if fmt == "yaml":
        try:
            yaml.safe_load(text)
            return True, None
        except yaml.YAMLError as e:
            return False, f"YAML構文エラー: {e}"
    if fmt == "markdown":
        # Markdown は自由記述のためバリデーションなし (空でなければOK)
        if not text.strip():
            return False, "内容が空です"
        return True, None
    if fmt == "python":
        try:
            ast.parse(text)
            return True, None
        except SyntaxError as e:
            return False, f"Python構文エラー: {e.lineno}行目: {e.msg}"
    return False, f"未対応フォーマット: {fmt}"


def save_config(resource_type: str, resource_id: str, fmt: str, text: str) -> Path:
    """設定テキストをファイルに保存する。保存前にバリデーションする。"""
    if fmt not in ALLOWED_FORMATS:
        raise ValueError(f"config_format は {ALLOWED_FORMATS} のいずれかを指定してください")
    ok, err = validate_config(fmt, text)
    if not ok:
        raise ValueError(err)

    path = config_file_path(resource_type, resource_id, fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_config(path: str | Path):
    """設定ファイルを読み込む。

    json/yaml は dict/list に変換して返す。
    python はモジュールとしてロードし `CONFIG` 変数の値を返す(任意コード実行に注意)。
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {path}")

    suffix = path.suffix.lstrip(".")
    text = path.read_text(encoding="utf-8")

    if suffix == "json":
        return json.loads(text)
    if suffix == "yaml":
        return yaml.safe_load(text)
    if suffix == "md":
        # Markdown (YAMLフロントマター対応): フロントマターがあれば dict + "content" キーで返す
        if text.startswith("---"):
            try:
                fm_text, body = text.split("---", 2)[1:]
                frontmatter = yaml.safe_load(fm_text) or {}
                if isinstance(frontmatter, dict):
                    return {**frontmatter, "content": body.strip()}
            except (yaml.YAMLError, ValueError):
                pass  # フロントマター不正の場合は本文のみ返す
        return {"content": text}
    if suffix == "py":
        module_name = f"nada_config_{re.sub(r'[^0-9a-zA-Z]', '_', str(path))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Python設定ファイルをロードできません: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # 任意コード実行(呼び出し側で信頼性に注意)
        config = getattr(module, "CONFIG", None)
        if config is None:
            raise ValueError(f"Python設定ファイルに CONFIG 変数が定義されていません: {path}")
        return config
    raise ValueError(f"未対応の設定ファイル形式: {suffix}")


def delete_config(path: str | Path) -> bool:
    """設定ファイルを削除する。存在しなければ False。"""
    path = Path(path)
    if path.exists():
        path.unlink()
        return True
    return False
