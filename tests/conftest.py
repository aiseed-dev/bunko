"""pytest 共通フィクスチャ。

原則（CLAUDE.md）: テストは**完全オフライン**で回る。ネットワーク取得を
モックで遮断し、同梱の公開作品（走れメロス・パブリックドメイン）だけで
検索→パース→変換の全経路を担保する。
"""
import urllib.request

import pytest

from pybunko import Work

DATA_DIR = __import__("pathlib").Path(__file__).parent / "data"

# 走れメロス（太宰治, パブリックドメイン）── 同梱の注記付きテキストzip。
# text_url は www.aozora.gr.jp 形式にしておくと mirror_url が
# DATA_DIR/1567_ruby_4948.zip を指し、ネットワーク無しでキャッシュとして読める。
_MEROSU_TEXT_URL = (
    "https://www.aozora.gr.jp/cards/000035/files/1567_ruby_4948.zip"
)


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    """外部へのurlopenを遮断（オフライン原則）。localhost宛のテスト用サーバは許可。"""
    real_urlopen = urllib.request.urlopen

    def _guarded(url, *args, **kwargs):
        target = url.full_url if hasattr(url, "full_url") else str(url)
        if "127.0.0.1" in target or "localhost" in target:
            return real_urlopen(url, *args, **kwargs)
        raise AssertionError(
            "テストが外部ネットワークにアクセスしようとした（オフライン原則違反）"
        )
    monkeypatch.setattr(urllib.request, "urlopen", _guarded)


@pytest.fixture
def merosu_work() -> Work:
    """同梱キャッシュから読む走れメロスの Work。ネットワーク不要。"""
    return Work(
        work_id="1567",
        title="走れメロス",
        title_yomi="はしれめろす",
        author="太宰治",
        author_yomi="だざいおさむ",
        card_url="https://www.aozora.gr.jp/cards/000035/card1567.html",
        text_url=_MEROSU_TEXT_URL,
        copyrighted=False,
        _cache_dir=DATA_DIR,
    )


@pytest.fixture
def merosu_doc(merosu_work):
    """走れメロスのパース済み Document。"""
    return merosu_work.document()
