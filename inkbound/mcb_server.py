"""MCB — Model Context Bridge. Run the Inkbound RPG engine from any MCP-capable harness.

MCB is a standard MCP server (stdio transport) exposing the Inkbound runtime as
tools, so OMP, Kodex, OpenCode, Claude Desktop, or any other MCP client can
drive the game with no extra adapter. It keeps one session per realm package;
sessions persist across restarts via the normal Inkbound save files.

Launch (any of these, MCP clients run the command):
  python -m inkbound.mcb_server [--realm PATH] [--save PATH] [--list]

Or, after `pip install -e .`, through the console script:
  inkbound-mcb [--realm PATH] [--save PATH]

`--list` prints the MCP config snippet for every detected harness.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from inkbound.cli import read_realm
from inkbound.runtime.engine import Engine

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "inkbound-mcb", "version": "1.0.0"}


def _require_loaded(fn):
    def wrapper(self, args):
        if self.engine is None:
            return "No realm loaded. Call realm_load first with the path to a realm package or fixture."
        return fn(self, args)
    return wrapper


class McbSession:
    """One Inkbound play session exposed over MCP."""

    def __init__(self, save_dir: str | None = None):
        self.engine: Engine | None = None
        self.realm_path: str | None = None
        self.save_dir = save_dir or "saves"
        self.save_path: str | None = None

    # -- tools -----------------------------------------------------------------

    def tool_realm_load(self, args: dict):
        realm = str(args.get("realm", "")).strip()
        if not realm:
            return "ERROR: 'realm' path is required."
        try:
            package = read_realm(Path(realm))
        except (ValueError, OSError, RuntimeError) as exc:
            return f"ERROR: cannot load realm {realm!r}: {exc}"
        self.realm_path = realm
        self.save_path = str(args.get("save") or Path(self.save_dir) / f"{package.spec.metadata.id}.json")
        save = Path(self.save_path)
        if save.exists():
            self.engine = Engine.load(package, save)
            result = f"Resumed '{package.spec.metadata.title}' from {save}."
        else:
            self.engine = Engine(package)
            result = f"Started new realm '{package.spec.metadata.title}'."
        result += "\n" + self.tool_status({})
        return result

    @_require_loaded
    def tool_status(self, args: dict):
        e = self.engine
        player = e.player
        hp = player.resources.get(e.health_id, 0)
        cap = player.caps.get(e.health_id, hp)
        loc = e.location_here()
        here = f"{loc.name} ({loc.kind})" if loc else f"map {player.map_id}"
        threats = e.threats()
        player_name = e.index[player.definition_id].name
        lines = [
            f"Realm: {e.spec.metadata.title} | Day {e.day} | Turn {e.state.turn} | Level {e.state.level} | XP {e.state.xp}",
            f"{player_name}: HP {hp}/{cap}, gold {e.state.gold}",
            f"At: {here} [position {player.x},{player.y}]",
            f"Active quests: {', '.join(e.state.quests_known) or 'none'}",
            f"Inventory: {json.dumps(e.state.inventory)}",
            f"Abilities: {', '.join(e.known_abilities())}",
            f"Threats: {len(threats)} in range",
        ]
        if e.state.active_dialogue_id:
            lines.append(f"IN DIALOGUE with {e.state.active_npc_id}; choices: {json.dumps(e.state.dialogue_choices)}")
        for m in e.state.messages[-6:]:
            lines.append(f"· {m}")
        return "\n".join(lines)

    @_require_loaded
    def tool_move(self, args: dict):
        moved = self.engine.move(int(args.get("dx", 0)), int(args.get("dy", 0)))
        return f"moved={moved}\n" + self.tool_status({})

    @_require_loaded
    def tool_interact(self, args: dict):
        ok = self.engine.interact()
        return f"interacted={ok}\n" + self.tool_status({})

    @_require_loaded
    def tool_talk(self, args: dict):
        e = self.engine
        npc_id = str(args.get("npc_id", "")).strip()
        if not npc_id:
            return "ERROR: 'npc_id' is required. Get IDs from status (dialogue line) or realm survey."
        ok = e.talk(npc_id)
        return f"talked={ok}\n" + self.tool_status({})

    @_require_loaded
    def tool_choose(self, args: dict):
        e = self.engine
        choice_id = str(args.get("choice_id", "")).strip()
        if not choice_id:
            return "ERROR: 'choice_id' is required (see status dialogue line)."
        ok = e.choose(choice_id)
        return f"chose={ok}\n" + self.tool_status({})

    @_require_loaded
    def tool_attack(self, args: dict):
        e = self.engine
        threats = e.threats()
        if not threats:
            return "No threats in range.\n" + self.tool_status({})
        target = args.get("target_id") or threats[0].id
        style = str(args.get("style", "normal"))
        if style not in ("normal", "quick", "heavy"):
            return "ERROR: style must be normal, quick or heavy."
        ok = e.use_ability(e.rules.default_ability_id, target_id=target, style=style)
        return f"attacked {target} ({style}) ok={ok}\n" + self.tool_status({})

    @_require_loaded
    def tool_ability(self, args: dict):
        e = self.engine
        ability_id = str(args.get("ability_id", "")).strip()
        target = args.get("target_id")
        style = str(args.get("style", "normal"))
        ok = e.use_ability(ability_id, target_id=target, style=style)
        return f"ability {ability_id} ok={ok}\n" + self.tool_status({})

    @_require_loaded
    def tool_use_item(self, args: dict):
        e = self.engine
        item_id = str(args.get("item_id", "")).strip()
        if not item_id:
            return "ERROR: 'item_id' is required."
        ok = e.use_item(item_id)
        return f"used {item_id} ok={ok}\n" + self.tool_status({})

    @_require_loaded
    def tool_buy(self, args: dict):
        ok = self.engine.buy(str(args.get("item_id", "")).strip())
        return f"bought ok={ok}\n" + self.tool_status({})

    @_require_loaded
    def tool_sell(self, args: dict):
        ok = self.engine.sell(str(args.get("item_id", "")).strip())
        return f"sold ok={ok}\n" + self.tool_status({})

    @_require_loaded
    def tool_craft(self, args: dict):
        ok = self.engine.craft(str(args.get("recipe_id", "")).strip())
        return f"crafted ok={ok}\n" + self.tool_status({})

    @_require_loaded
    def tool_rest(self, args: dict):
        self.engine.rest()
        return "Rested.\n" + self.tool_status({})

    @_require_loaded
    def tool_flee(self, args: dict):
        self.engine.flee()
        return "Fled.\n" + self.tool_status({})

    @_require_loaded
    def tool_save(self, args: dict):
        path = str(args.get("path") or self.save_path)
        self.engine.save(path)
        return f"Saved to {path}."

    @_require_loaded
    def tool_survey(self, args: dict):
        """Describe the current map: terrain symbols, NPCs, enemies, exits."""
        e = self.engine
        m = e.current_map
        grid = "\n".join("".join(row) for row in m.grid)
        npc_here = [(nid, list(map(int, pos))) for nid, pos in e.state.npc_positions.items()
                    if e.npc_map_id(e.index[nid]) == m.id]
        enemies = [{"id": a.id, "hp": a.resources.get(e.health_id, 0)} for a in e.state.actors.values()
                   if a.map_id == m.id]
        rows = [f"Map: {m.id} ({len(m.grid[0])}x{len(m.grid)})"]
        if e.player.map_id == m.id:
            rows.append(f"You are at {e.player.x},{e.player.y} (row=y, col=x).")
        rows.append(f"NPCs here: {json.dumps(npc_here)}")
        rows.append(f"Actors here: {json.dumps(enemies)}")
        return "\n".join(rows) + "\n" + grid

    @_require_loaded
    def tool_journal(self, args: dict):
        e = self.engine
        lines = ["== QUESTS =="]
        for q in e.spec.quests:
            if q.id in e.state.quests_known:
                status = "COMPLETE" if q.id in e.state.quests_done else "FAILED" if q.id in e.state.quests_failed else "ACTIVE" if q.id in e.active_quests() else "WAITING"
                lines.append(f"[{status}] {q.id}: {q.name} — {q.description}")
        lines.append("\n== ANNALS ==")
        lines.extend(e.state.annals)
        return "\n".join(lines)

    # -- discovery ---------------------------------------------------------------

    TOOLS = [
        ("realm_load", "Load or resume an Inkbound realm. Args: realm (path to fixture/package), optional save path.", None),
        ("status", "Full game state: HP, position, quests, inventory, dialogue, recent log.", None),
        ("survey", "ASCII map of current area with NPC and enemy positions.", None),
        ("move", "Move one tile. Args: dx, dy (e.g. dx=1 dy=0 moves right).", None),
        ("interact", "Enter/exit the location under the player (settlements, dungeons).", None),
        ("talk", "Start dialogue with an NPC. Args: npc_id.", None),
        ("choose", "Pick a dialogue choice. Args: choice_id (from status).", None),
        ("attack", "Attack nearest/selected threat with the default ability. Args: target_id optional, style: normal|quick|heavy.", None),
        ("ability", "Use a named ability. Args: ability_id, target_id optional, style optional.", None),
        ("use_item", "Use or equip an item. Args: item_id.", None),
        ("buy", "Buy at a settlement market. Args: item_id.", None),
        ("sell", "Sell at a settlement market. Args: item_id.", None),
        ("craft", "Craft a recipe. Args: recipe_id.", None),
        ("rest", "Rest to recover.", None),
        ("flee", "Flee combat.", None),
        ("save", "Save the session. Args: path optional.", None),
        ("journal", "Quest log and world annals.", None),
    ]

    def dispatch(self, name: str, args: dict):
        fn = getattr(self, f"tool_{name}", None)
        if fn is None:
            return f"Unknown tool: {name}"
        try:
            return fn(args)
        except (ValueError, KeyError, RuntimeError, TypeError) as exc:
            return f"ERROR: {type(exc).__name__}: {exc}"


TOOL_SCHEMAS = {
    "realm_load": {
        "type": "object",
        "properties": {
            "realm": {"type": "string", "description": "Path to a realm package directory or fixture JSON"},
            "save": {"type": "string", "description": "Optional save file path"},
        },
        "required": ["realm"],
    },
    "move": {"type": "object", "properties": {"dx": {"type": "integer", "default": 0}, "dy": {"type": "integer", "default": 0}}},
    "talk": {"type": "object", "properties": {"npc_id": {"type": "string"}}, "required": ["npc_id"]},
    "choose": {"type": "object", "properties": {"choice_id": {"type": "string"}}, "required": ["choice_id"]},
    "attack": {"type": "object", "properties": {"target_id": {"type": "string"}, "style": {"type": "string", "enum": ["normal", "quick", "heavy"]}}},
    "ability": {"type": "object", "properties": {"ability_id": {"type": "string"}, "target_id": {"type": "string"}, "style": {"type": "string", "enum": ["normal", "quick", "heavy"]}}, "required": ["ability_id"]},
    "use_item": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]},
    "buy": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]},
    "sell": {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]},
    "craft": {"type": "object", "properties": {"recipe_id": {"type": "string"}}, "required": ["recipe_id"]},
    "save": {"type": "object", "properties": {"path": {"type": "string"}}},
}


def tool_definitions():
    defs = []
    for name, desc, _ in McbSession.TOOLS:
        defs.append({"name": name, "description": desc, "inputSchema": TOOL_SCHEMAS.get(name, {"type": "object", "properties": {}})})
    return defs


def rpc_handle(session: McbSession, request: dict) -> dict | None:
    """Handle one JSON-RPC 2.0 request; returns a response dict or None for notifications."""
    method = request.get("method", "")
    rid = request.get("id")
    params = request.get("params") or {}

    def result(payload):
        return {"jsonrpc": "2.0", "id": rid, "result": payload}

    def error(code, message):
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

    try:
        if method == "initialize":
            return result({
                "protocolVersion": params.get("protocolVersion", MCP_PROTOCOL_VERSION),
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            })
        if method == "ping":
            return result({})
        if method == "notifications/initialized":
            return None  # notification: no reply
        if method == "tools/list":
            return result({"tools": tool_definitions()})
        if method == "tools/call":
            name = params["name"]
            args = params.get("arguments") or {}
            text = session.dispatch(name, args)
            return result({"content": [{"type": "text", "text": text}], "isError": text.startswith("ERROR") or text.startswith("Unknown tool")})
        return error(-32601, f"Method not found: {method}")
    except Exception as exc:  # never crash the stdio loop on a bad request
        return error(-32603, f"Internal error: {type(exc).__name__}: {exc}")


def serve(realm: str | None, save: str | None, save_dir: str):
    session = McbSession(save_dir=save_dir)
    if realm:
        print(session.dispatch("realm_load", {"realm": realm, "save": save} if save else {"realm": realm}), file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = rpc_handle(session, request)
        if response is not None:
            print(json.dumps(response), flush=True)


HARNESS_SNIPPETS = {
    "OMP": '''# ~/.omp/agent/mcp.json → mcpServers:
  "inkbound-mcb": {
    "command": "<venv python> -m inkbound.mcb_server",
    "cwd": "<repo path>"
  }''',
    "Kodex / Codex CLI": '''# ~/.codex/config.toml:
[mcp_servers.inkbound-mcb]
command = "<venv python>"
args = ["-m", "inkbound.mcb_server"]
# (cwd defaults to where Codex starts; pass the repo path in args if needed)''',
    "OpenCode": '''# ~/.config/opencode/opencode.json → mcp:
  "inkbound-mcb": {
    "type": "local",
    "command": ["<venv python>", "-m", "inkbound.mcb_server"],
    "enabled": true,
    "environment": {}
  }''',
    "Claude Desktop": '''# claude_desktop_config.json → mcpServers:
  "inkbound-mcb": {
    "command": "<venv python>",
    "args": ["-m", "inkbound.mcb_server", "--realm", "fixtures/fantasy.json"]
  }''',
}


def print_config(args):
    repo = Path(__file__).resolve().parents[1]
    py = str(Path(sys.executable))
    print("MCB server config snippets (repo:", str(repo), ")")
    print("Command for any client:", py, "-m inkbound.mcb_server --realm <realm path>")
    print()
    for harness, snippet in HARNESS_SNIPPETS.items():
        print(f"== {harness} ==")
        print(snippet.replace("<venv python>", py).replace("<repo path>", str(repo)))
        print()


def main():
    parser = argparse.ArgumentParser(description="Inkbound MCB — MCP server exposing the game to any harness")
    parser.add_argument("--realm", help="Realm package/fixture to auto-load at startup")
    parser.add_argument("--save", help="Save file to resume")
    parser.add_argument("--save-dir", default="saves")
    parser.add_argument("--list", action="store_true", help="Print MCP config snippets for common harnesses and exit")
    args = parser.parse_args()
    if args.list:
        print_config(args)
        return
    serve(args.realm, args.save, args.save_dir)


if __name__ == "__main__":
    main()
