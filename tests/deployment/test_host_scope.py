from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.routers.auth import _resolve_host_game_type
from backend.runtime.host_scope import build_host_scope_map, resolve_host_scope
from backend.utils.model_registry import GameType


def test_host_scope_map_normalizes_exact_hosts():
    settings = SimpleNamespace(
        qf_frontend_url="https://quipflip.crowdcraftlabs.com",
        mm_frontend_url="https://mememint.crowdcraftlabs.com",
        ir_frontend_url="https://initialreaction.crowdcraftlabs.com",
        tl_frontend_url="https://thinklink.crowdcraftlabs.com",
    )

    host_map = build_host_scope_map(settings)

    qf_scope = resolve_host_scope("QUIPFLIP.CROWDCRAFTLABS.COM:443", host_map)
    assert qf_scope is not None
    assert qf_scope.game == GameType.QF
    assert qf_scope.api_prefix == "/qf"
    assert qf_scope.static_dir == "qf"

    tl_scope = resolve_host_scope("thinklink.crowdcraftlabs.com", host_map)
    assert tl_scope is not None
    assert tl_scope.game == GameType.TL


def test_auth_host_scope_helper_prefers_the_validated_host():
    request = SimpleNamespace(
        state=SimpleNamespace(host_scope=SimpleNamespace(game=GameType.QF)),
    )

    assert _resolve_host_game_type(request, None) == GameType.QF
    assert _resolve_host_game_type(request, GameType.QF) == GameType.QF

    with pytest.raises(HTTPException) as exc_info:
        _resolve_host_game_type(request, GameType.MM)

    assert exc_info.value.status_code == 404
