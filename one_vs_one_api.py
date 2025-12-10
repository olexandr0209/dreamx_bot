# one_vs_one_api.py
import json
from aiohttp import web

from one_vs_one_logic import (
    join_one_vs_one,
    make_move,
    get_room_state,
)


def _json_error(message: str, status: int = 400):
    return web.json_response({"ok": False, "error": message}, status=status)


# POST /api/one_vs_one/join
# body: { "user_id": 123, "username": "alexandr_kr" }
async def api_one_vs_one_join(request: web.Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return _json_error("Invalid JSON")

    user_id = data.get("user_id")
    username = data.get("username")

    if not isinstance(user_id, int):
        return _json_error("user_id must be int")

    try:
        result = join_one_vs_one(user_id=user_id, username=username)
    except Exception as e:
        return _json_error(f"join_one_vs_one error: {e}", status=500)

    return web.json_response({"ok": True, "data": result})


# POST /api/one_vs_one/move
# body: { "room_id": 1, "user_id": 123, "round_index": 1, "game_index": 0, "choice": "rock" }
async def api_one_vs_one_move(request: web.Request):
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return _json_error("Invalid JSON")

    room_id = data.get("room_id")
    user_id = data.get("user_id")
    round_index = data.get("round_index", 1)
    game_index = data.get("game_index", 0)
    choice = data.get("choice")

    if not isinstance(room_id, int):
        return _json_error("room_id must be int")
    if not isinstance(user_id, int):
        return _json_error("user_id must be int")
    if not isinstance(round_index, int):
        return _json_error("round_index must be int")
    if not isinstance(game_index, int):
        return _json_error("game_index must be int")
    if not isinstance(choice, str):
        return _json_error("choice must be 'rock'|'paper'|'scissors'")

    try:
        result = make_move(
            room_id=room_id,
            user_id=user_id,
            round_index=round_index,
            game_index=game_index,
            choice=choice,
        )
    except ValueError as e:
        return _json_error(str(e))
    except Exception as e:
        return _json_error(f"make_move error: {e}", status=500)

    return web.json_response({"ok": True, "data": result})


# GET /api/one_vs_one/state?room_id=1&user_id=123
async def api_one_vs_one_state(request: web.Request):
    try:
        room_id = int(request.query.get("room_id", "0"))
    except ValueError:
        return _json_error("room_id must be int")

    if room_id <= 0:
        return _json_error("room_id is required")

    user_id_param = request.query.get("user_id")
    user_id: int | None = None
    if user_id_param is not None:
        try:
            user_id = int(user_id_param)
        except ValueError:
            return _json_error("user_id must be int")

    try:
        result = get_room_state(room_id=room_id, user_id=user_id)
    except Exception as e:
        return _json_error(f"get_room_state error: {e}", status=500)

    return web.json_response({"ok": True, "data": result})
