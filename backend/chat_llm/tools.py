from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Tool schemas  (OpenAI / Groq function-calling format)
# ──────────────────────────────────────────────

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_all_players",
            "description": (
                "Returns the complete list of ALL players in the squad. "
                "Call this tool when the user asks to: 'list players', "
                "'show all players', 'give me the players', 'who is in the squad', "
                "'show the squad', 'all players', 'give me all the players', "
                "'who do you have', 'players list', or any similar request. "
                "This tool always returns data successfully. "
                "No parameters are required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max players to return. Default is 31.",
                        "default": 31,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "squad_risk",
            "description": (
                "Fetches the top-N players most at risk of injury in the squad. "
                "Returns player names, positions, and injury risk scores. "
                "Use this when the user asks about squad-wide injury risks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "n": {
                        "type": "integer",
                        "description": "Number of at-risk players to return (default 5, max 20).",
                        "default": 5,
                    },
                    "position": {
                        "type": "string",
                        "description": "Filter by position: 'GK', 'DEF', 'MID', 'FWD'. Omit for all.",
                        "enum": ["GK", "DEF", "MID", "FWD"],
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "physio_risk",
            "description": (
                "Calculates the injury risk score for a specific player. "
                "Returns ACWR, fatigue index, and risk level (low/medium/high/critical). "
                "Use this when the user asks about a specific player's injury risk."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "player_id": {
                        "type": "integer",
                        "description": "The database ID of the player.",
                    },
                },
                "required": ["player_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "player_search",
            "description": (
                "Searches the database for players by name. "
                "Returns a list of matching players with their IDs and positions. "
                "ALWAYS call this first if you have a player name but no player_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Full or partial player name to search for.",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "physio_timeseries",
            "description": (
                "Returns a time-series of ACWR (Acute:Chronic Workload Ratio) "
                "and training load data for a player over the last N days. "
                "Use for trend analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "player_id": {
                        "type": "integer",
                        "description": "The database ID of the player.",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of past days to retrieve (default 28, max 90).",
                        "default": 28,
                    },
                },
                "required": ["player_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nutri_generate_plan",
            "description": (
                "Generates a personalised nutritional plan for a player based on "
                "their weight, position, and training intensity. Returns daily "
                "macro targets (calories, protein, carbs, fats)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "player_id": {
                        "type": "integer",
                        "description": "The database ID of the player.",
                    },
                    "training_intensity": {
                        "type": "string",
                        "description": "Expected training intensity for the day.",
                        "enum": ["rest", "light", "moderate", "heavy", "match"],
                        "default": "moderate",
                    },
                },
                "required": ["player_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "nutri_meal_calc",
            "description": (
                "Breaks down a specific meal into its nutritional components "
                "(calories, protein, carbs, fats, micronutrients)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "meal_description": {
                        "type": "string",
                        "description": "Description of the meal (e.g. '200g grilled chicken with rice').",
                    },
                },
                "required": ["meal_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "food_search",
            "description": (
                "Searches the food database for nutritional information about a food item."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Food item to search for (e.g. 'banana', 'olive oil').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# ──────────────────────────────────────────────
# Tool implementations
# ──────────────────────────────────────────────

def _tool_squad_risk(n: int = 5, position: str | None = None, **kwargs) -> dict:
    try:
        from players.models import Player      # adjust import to your app
        from physio.services import risk_score # adjust import to your app

        n = min(max(1, int(n)), 20)
        qs = Player.objects.all()
        if position:
            qs = qs.filter(position=position)

        results = []
        for player in qs[:50]:   # limit query scope
            score_data = risk_score(player.id)
            results.append({
                "player_id":   player.id,
                "name":        player.full_name,
                "position":    player.position,
                "risk_score":  score_data.get("score", 0),
                "risk_level":  score_data.get("level", "unknown"),
            })

        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return {"players": results[:n], "total_queried": len(results)}

    except ImportError:
        # Return mock data if models aren't available (dev/test)
        return _mock_squad_risk(n, position)
    except Exception as exc:
        logger.exception("squad_risk failed")
        return {"error": True, "message": str(exc)}


def _tool_physio_risk(player_id: int, **kwargs) -> dict:
    try:
        from physio.services import detailed_risk_report
        return detailed_risk_report(player_id)
    except ImportError:
        return _mock_physio_risk(player_id)
    except Exception as exc:
        logger.exception("physio_risk failed for player %s", player_id)
        return {"error": True, "message": str(exc)}


def _tool_player_search(name: str, **kwargs) -> dict:
    try:
        from players.models import Player
        matches = Player.objects.filter(full_name__icontains=name)[:10]
        return {
            "players": [
                {"player_id": p.id, "name": p.full_name, "position": p.position}
                for p in matches
            ]
        }
    except ImportError:
        return _mock_player_search(name)
    except Exception as exc:
        logger.exception("player_search failed for '%s'", name)
        return {"error": True, "message": str(exc)}


def _tool_physio_timeseries(player_id: int, days: int = 28, **kwargs) -> dict:
    try:
        from physio.services import workload_timeseries
        days = min(max(1, int(days)), 90)
        return workload_timeseries(player_id, days)
    except ImportError:
        return _mock_timeseries(player_id, days)
    except Exception as exc:
        logger.exception("physio_timeseries failed for player %s", player_id)
        return {"error": True, "message": str(exc)}


def _tool_nutri_generate_plan(player_id: int, training_intensity: str = "moderate", **kwargs) -> dict:
    try:
        from nutrition.services import generate_nutrition_plan
        return generate_nutrition_plan(player_id, training_intensity)
    except ImportError:
        return _mock_nutrition_plan(player_id, training_intensity)
    except Exception as exc:
        logger.exception("nutri_generate_plan failed for player %s", player_id)
        return {"error": True, "message": str(exc)}


def _tool_nutri_meal_calc(meal_description: str, **kwargs) -> dict:
    try:
        from nutrition.services import calculate_meal
        return calculate_meal(meal_description)
    except ImportError:
        return {
            "error": True,
            "tool_failed": True,
            "service": "nutrition",
            "message": "TOOL_FAILURE: nutrition service is unavailable. "
                       "Do not provide any alternative information. "
                       "Tell the user the service is temporarily unavailable "
                       "and suggest they try injury risk or player search instead.",
        }
    except Exception as exc:
        logger.exception("nutri_meal_calc failed")
        return {"error": True, "message": str(exc)}


def _tool_food_search(query: str, limit: int = 5, **kwargs) -> dict:
    try:
        from nutrition.services import search_food_database
        limit = min(max(1, int(limit)), 20)
        return search_food_database(query, limit)
    except ImportError:
        return {
            "error": True,
            "tool_failed": True,
            "service": "nutrition",
            "message": "TOOL_FAILURE: nutrition service is unavailable. "
                       "Do not provide any alternative information. "
                       "Tell the user the service is temporarily unavailable "
                       "and suggest they try injury risk or player search instead.",
        }
    except Exception as exc:
        logger.exception("food_search failed for '%s'", query)
        return {"error": True, "message": str(exc)}


# ──────────────────────────────────────────────
# Tool dispatcher
# ──────────────────────────────────────────────

def _tool_list_all_players(limit: int = 31, **kwargs) -> dict:
    try:
        from players.models import Player
        players = Player.objects.all()[:limit]
        return {
            "players": [
                {"player_id": p.id, "name": p.full_name, "position": p.position}
                for p in players
            ]
        }
    except ImportError:
        return _mock_list_all_players(limit)
    except Exception as exc:
        logger.exception("list_all_players failed")
        return {"error": True, "message": str(exc)}

_TOOL_REGISTRY: dict[str, callable] = {
    "list_all_players":  _tool_list_all_players,
    "squad_risk":          _tool_squad_risk,
    "physio_risk":         _tool_physio_risk,
    "player_search":       _tool_player_search,
    "physio_timeseries":   _tool_physio_timeseries,
    "nutri_generate_plan": _tool_nutri_generate_plan,
    "nutri_meal_calc":     _tool_nutri_meal_calc,
    "food_search":         _tool_food_search,
}


def execute_tool(tool_name: str, args: dict) -> Any:
    """
    Dispatch a tool call. Raises KeyError for unknown tools.
    Individual tools handle their own exceptions internally.
    """
    fn = _TOOL_REGISTRY.get(tool_name)
    if fn is None:
        logger.error("Unknown tool requested: '%s'", tool_name)
        return {
            "error":   True,
            "message": f"Unknown tool '{tool_name}'. Available tools: {list(_TOOL_REGISTRY.keys())}",
        }
    return fn(**(args or {}))


# ─────────────────────────────────────────────────────────────
# MASTER MOCK SQUAD  (used by ALL mock functions below)
# ─────────────────────────────────────────────────────────────

MOCK_SQUAD = [
    # ── GOALKEEPERS (3) ───────────────────────────────────────
    {
        "player_id": 1,  "name": "Moez Ben Cherifa",  "position": "GK",
        "sub_position": "Goalkeeper",
        "age": 28, "number": 1,  "nationality": "Tunisian",
        "height_cm": 190, "weight_kg": 84,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 2,  "name": "Aymen Dahmane",     "position": "GK",
        "sub_position": "Goalkeeper",
        "age": 24, "number": 16, "nationality": "Algerian",
        "height_cm": 188, "weight_kg": 82,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 3,  "name": "Bilel Ifa",         "position": "GK",
        "sub_position": "Goalkeeper",
        "age": 21, "number": 30, "nationality": "Tunisian",
        "height_cm": 185, "weight_kg": 79,
        "preferred_foot": "Left",  "status": "available",
    },

    # ── DEFENDERS (8) ─────────────────────────────────────────
    # Centre-backs (4)
    {
        "player_id": 4,  "name": "Hamza Mathlouthi",  "position": "DEF",
        "sub_position": "Centre-Back",
        "age": 29, "number": 5,  "nationality": "Tunisian",
        "height_cm": 187, "weight_kg": 83,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 5,  "name": "Yassine Meriah",    "position": "DEF",
        "sub_position": "Centre-Back",
        "age": 31, "number": 6,  "nationality": "Tunisian",
        "height_cm": 184, "weight_kg": 80,
        "preferred_foot": "Right", "status": "injured",
    },
    {
        "player_id": 6,  "name": "Nader Ghandri",     "position": "DEF",
        "sub_position": "Centre-Back",
        "age": 33, "number": 3,  "nationality": "Tunisian",
        "height_cm": 189, "weight_kg": 86,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 7,  "name": "Montassar Talbi",   "position": "DEF",
        "sub_position": "Centre-Back",
        "age": 25, "number": 15, "nationality": "Tunisian",
        "height_cm": 186, "weight_kg": 81,
        "preferred_foot": "Left",  "status": "available",
    },
    # Left-backs (2)
    {
        "player_id": 8,  "name": "Ali Maaloul",       "position": "DEF",
        "sub_position": "Left-Back",
        "age": 34, "number": 12, "nationality": "Tunisian",
        "height_cm": 178, "weight_kg": 75,
        "preferred_foot": "Left",  "status": "available",
    },
    {
        "player_id": 9,  "name": "Oussama Haddadi",   "position": "DEF",
        "sub_position": "Left-Back",
        "age": 30, "number": 23, "nationality": "Tunisian",
        "height_cm": 180, "weight_kg": 76,
        "preferred_foot": "Left",  "status": "suspended",
    },
    # Right-backs (2)
    {
        "player_id": 10, "name": "Wajdi Kechrida",    "position": "DEF",
        "sub_position": "Right-Back",
        "age": 28, "number": 2,  "nationality": "Tunisian",
        "height_cm": 177, "weight_kg": 73,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 11, "name": "Mohamed Dhaoui",    "position": "DEF",
        "sub_position": "Right-Back",
        "age": 22, "number": 22, "nationality": "Tunisian",
        "height_cm": 179, "weight_kg": 74,
        "preferred_foot": "Right", "status": "available",
    },

    # ── MIDFIELDERS (10) ──────────────────────────────────────
    # Defensive midfielders / CDM (3)
    {
        "player_id": 12, "name": "Ellyes Skhiri",     "position": "MID",
        "sub_position": "Defensive Mid",
        "age": 29, "number": 8,  "nationality": "Tunisian",
        "height_cm": 183, "weight_kg": 78,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 13, "name": "Saad Bguir",        "position": "MID",
        "sub_position": "Defensive Mid",
        "age": 26, "number": 6,  "nationality": "Tunisian",
        "height_cm": 181, "weight_kg": 77,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 14, "name": "Anis Ben Slimane",  "position": "MID",
        "sub_position": "Defensive Mid",
        "age": 23, "number": 28, "nationality": "Tunisian",
        "height_cm": 182, "weight_kg": 76,
        "preferred_foot": "Right", "status": "available",
    },
    # Central midfielders / CM (4)
    {
        "player_id": 15, "name": "Ghaylen Chaalali",  "position": "MID",
        "sub_position": "Central Mid",
        "age": 30, "number": 7,  "nationality": "Tunisian",
        "height_cm": 179, "weight_kg": 74,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 16, "name": "Ferjani Sassi",     "position": "MID",
        "sub_position": "Central Mid",
        "age": 32, "number": 17, "nationality": "Tunisian",
        "height_cm": 181, "weight_kg": 76,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 17, "name": "Naim Sliti",        "position": "MID",
        "sub_position": "Central Mid",
        "age": 31, "number": 19, "nationality": "Tunisian",
        "height_cm": 176, "weight_kg": 71,
        "preferred_foot": "Left",  "status": "injured",
    },
    {
        "player_id": 18, "name": "Mohamed Ali Ben Romdhane", "position": "MID",
        "sub_position": "Central Mid",
        "age": 24, "number": 24, "nationality": "Tunisian",
        "height_cm": 180, "weight_kg": 75,
        "preferred_foot": "Right", "status": "available",
    },
    # Attacking midfielders / CAM (3)
    {
        "player_id": 19, "name": "Hannibal Mejbri",   "position": "MID",
        "sub_position": "Attacking Mid",
        "age": 21, "number": 14, "nationality": "Tunisian",
        "height_cm": 178, "weight_kg": 72,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 20, "name": "Ahmed Ben Ali",     "position": "MID",
        "sub_position": "Attacking Mid",
        "age": 27, "number": 10, "nationality": "Tunisian",
        "height_cm": 177, "weight_kg": 70,
        "preferred_foot": "Left",  "status": "available",
    },
    {
        "player_id": 21, "name": "Taha Yassine Khenissi", "position": "MID",
        "sub_position": "Attacking Mid",
        "age": 35, "number": 20, "nationality": "Tunisian",
        "height_cm": 176, "weight_kg": 71,
        "preferred_foot": "Right", "status": "available",
    },

    # ── FORWARDS (8) ──────────────────────────────────────────
    # Strikers / ST (2)
    {
        "player_id": 22, "name": "Youssef Msakni",    "position": "FWD",
        "sub_position": "Striker",
        "age": 33, "number": 11, "nationality": "Tunisian",
        "height_cm": 175, "weight_kg": 69,
        "preferred_foot": "Left",  "status": "available",
    },
    {
        "player_id": 23, "name": "Seifeddine Jaziri",  "position": "FWD",
        "sub_position": "Striker",
        "age": 32, "number": 9,  "nationality": "Tunisian",
        "height_cm": 182, "weight_kg": 78,
        "preferred_foot": "Right", "status": "available",
    },
    # Left wingers / LW (3)
    {
        "player_id": 24, "name": "Wahbi Khazri",      "position": "FWD",
        "sub_position": "Left Winger",
        "age": 33, "number": 13, "nationality": "Tunisian",
        "height_cm": 178, "weight_kg": 73,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 25, "name": "Hamza Ben Achour",  "position": "FWD",
        "sub_position": "Left Winger",
        "age": 25, "number": 21, "nationality": "Tunisian",
        "height_cm": 174, "weight_kg": 68,
        "preferred_foot": "Left",  "status": "available",
    },
    {
        "player_id": 26, "name": "Chaim El Djebali",  "position": "FWD",
        "sub_position": "Left Winger",
        "age": 22, "number": 29, "nationality": "Tunisian",
        "height_cm": 173, "weight_kg": 67,
        "preferred_foot": "Left",  "status": "available",
    },
    # Right wingers / RW (3)
    {
        "player_id": 27, "name": "Taha Khenissi",     "position": "FWD",
        "sub_position": "Right Winger",
        "age": 28, "number": 18, "nationality": "Tunisian",
        "height_cm": 176, "weight_kg": 70,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 28, "name": "Anis Slimane",      "position": "FWD",
        "sub_position": "Right Winger",
        "age": 23, "number": 25, "nationality": "Tunisian",
        "height_cm": 175, "weight_kg": 69,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 29, "name": "Mortadha Ben Ouanes", "position": "FWD",
        "sub_position": "Right Winger",
        "age": 26, "number": 27, "nationality": "Tunisian",
        "height_cm": 177, "weight_kg": 71,
        "preferred_foot": "Right", "status": "available",
    },

    # ── UTILITY / MULTI-POSITION (2) ──────────────────────────
    {
        "player_id": 30, "name": "Mohamed Amine Tougai", "position": "MID",
        "sub_position": "Utility (MID/DEF)",
        "age": 27, "number": 26, "nationality": "Tunisian",
        "height_cm": 180, "weight_kg": 75,
        "preferred_foot": "Right", "status": "available",
    },
    {
        "player_id": 31, "name": "Bassem Srarfi",     "position": "FWD",
        "sub_position": "Utility (FWD/MID)",
        "age": 28, "number": 31, "nationality": "Tunisian",
        "height_cm": 176, "weight_kg": 72,
        "preferred_foot": "Left",  "status": "available",
    },
]


# ─────────────────────────────────────────────────────────────
# MOCK FUNCTION IMPLEMENTATIONS
# (replace the old ones at the bottom of tools.py)
# ─────────────────────────────────────────────────────────────



def _mock_list_all_players(limit: int = 31) -> dict:
    players = MOCK_SQUAD[:limit]
    return {
        "players": players,
        "total": len(players),
        "squad_summary": {
            "GK":  len([p for p in players if p["position"] == "GK"]),
            "DEF": len([p for p in players if p["position"] == "DEF"]),
            "MID": len([p for p in players if p["position"] == "MID"]),
            "FWD": len([p for p in players if p["position"] == "FWD"]),
        },
        "_mock": True,
    }


def _mock_squad_risk(n: int = 5, position: str | None = None) -> dict:
    players = MOCK_SQUAD
    if position:
        players = [p for p in players if p["position"] == position]

    # Generate deterministic-ish risk scores based on player_id
    risk_levels = ["low", "medium", "high", "critical"]
    results = []
    for p in players:
        # Seed with player_id for consistency across calls
        random.seed(p["player_id"] * 7)
        score = round(random.uniform(0.10, 0.95), 2)
        level = (
            "critical" if score >= 0.85 else
            "high"     if score >= 0.65 else
            "medium"   if score >= 0.40 else
            "low"
        )
        results.append({
            "player_id":    p["player_id"],
            "name":         p["name"],
            "position":     p["position"],
            "sub_position": p["sub_position"],
            "risk_score":   score,
            "risk_level":   level,
            "status":       p["status"],
        })

    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return {
        "players":       results[:n],
        "total_queried": len(results),
        "_mock":         True,
    }


def _mock_physio_risk(player_id: int) -> dict:
    player = next(
        (p for p in MOCK_SQUAD if p["player_id"] == player_id), None
    )

    # If not found but ID looks valid (1-50 range), find closest
    if not player and 1 <= player_id <= 50:
        # Return first available player as fallback
        player = MOCK_SQUAD[0]

    if not player:
        return {
            "error":   True,
            "tool_failed": True,
            "message": (
                f"TOOL_FAILURE: Player ID {player_id} not found. "
                f"You must call player_search first to get a valid player_id. "
                f"Valid player IDs are 1 through 31."
            ),
        }

    random.seed(player_id * 13)
    acwr  = round(random.uniform(0.70, 1.60), 2)
    score = round(random.uniform(0.10, 0.95), 2)
    level = (
        "critical" if score >= 0.85 else
        "high"     if score >= 0.65 else
        "medium"   if score >= 0.40 else
        "low"
    )
    return {
        "player_id":      player_id,
        "name":           player["name"],
        "position":       player["position"],
        "sub_position":   player["sub_position"],
        "jersey_number":  player["number"],
        "age":            player["age"],
        "nationality":    player["nationality"],
        "height_cm":      player["height_cm"],
        "weight_kg":      player["weight_kg"],
        "preferred_foot": player["preferred_foot"],
        "acwr":           acwr,
        "fatigue_index":  round(random.uniform(0.20, 0.90), 2),
        "risk_score":     score,
        "risk_level":     level,
        "recommendation": (
            "Reduce training load by 30% for 3 days and monitor."
            if level in ("high", "critical")
            else "Continue normal training. Monitor weekly."
        ),
        "status":         player["status"],
        "_mock":          True,
    }


def _mock_player_search(name: str) -> dict:
    name_lower = name.lower().strip()

    # Try exact sub-string match first
    matches = [
        p for p in MOCK_SQUAD
        if name_lower in p["name"].lower()
    ]

    # If nothing, try matching any single word in the query
    if not matches:
        words = name_lower.split()
        matches = [
            p for p in MOCK_SQUAD
            if any(w in p["name"].lower() for w in words if len(w) > 2)
        ]

    # Still nothing → return top 3 as suggestions
    if not matches:
        return {
            "players": MOCK_SQUAD[:3],
            "note":    f"No match for '{name}'. Showing first 3 players as suggestions.",
            "_mock":   True,
        }

    return {
        "players": [
            {
                "player_id":    p["player_id"],
                "name":         p["name"],
                "position":     p["position"],
                "sub_position": p["sub_position"],
                "age":          p["age"],
                "number":       p["number"],
                "nationality":  p["nationality"],
                "status":       p["status"],
            }
            for p in matches
        ],
        "_mock": True,
    }


def _mock_timeseries(player_id: int, days: int) -> dict:
    player = next((p for p in MOCK_SQUAD if p["player_id"] == player_id), None)
    name   = player["name"] if player else f"Player #{player_id}"

    random.seed(player_id)
    base_load = random.randint(350, 650)

    series = []
    for i in range(min(days, 30)):
        random.seed(player_id + i * 100)
        daily_load = base_load + random.randint(-120, 120)
        acwr       = round(0.85 + random.random() * 0.65, 2)
        series.append({
            "day":   i + 1,
            "load":  max(0, daily_load),
            "acwr":  acwr,
            "zone":  (
                "danger"  if acwr > 1.4 else
                "warning" if acwr > 1.2 else
                "optimal" if acwr > 0.8 else
                "low"
            ),
        })

    return {
        "player_id":      player_id,
        "name":           name,
        "jersey_number":  player["number"] if player else None,
        "age":            player["age"] if player else None,
        "nationality":    player["nationality"] if player else None,
        "height_cm":      player["height_cm"] if player else None,
        "weight_kg":      player["weight_kg"] if player else None,
        "preferred_foot": player["preferred_foot"] if player else None,
        "sub_position":   player["sub_position"] if player else None,
        "days":           days,
        "series":         series,
        "_mock":          True,
    }


def _mock_nutrition_plan(player_id: int, intensity: str) -> dict:
    player = next((p for p in MOCK_SQUAD if p["player_id"] == player_id), None)
    if not player:
        return {"error": True, "message": f"Player ID {player_id} not found."}

    weight = player["weight_kg"]
    plans = {
        "rest":     {"calories": round(weight * 28), "protein_g": round(weight * 1.6), "carbs_g": round(weight * 3.0), "fats_g": round(weight * 0.9)},
        "light":    {"calories": round(weight * 32), "protein_g": round(weight * 1.8), "carbs_g": round(weight * 3.8), "fats_g": round(weight * 1.0)},
        "moderate": {"calories": round(weight * 38), "protein_g": round(weight * 2.0), "carbs_g": round(weight * 4.5), "fats_g": round(weight * 1.1)},
        "heavy":    {"calories": round(weight * 44), "protein_g": round(weight * 2.2), "carbs_g": round(weight * 5.5), "fats_g": round(weight * 1.2)},
        "match":    {"calories": round(weight * 48), "protein_g": round(weight * 2.4), "carbs_g": round(weight * 6.0), "fats_g": round(weight * 1.2)},
    }
    macros = plans.get(intensity, plans["moderate"])

    return {
        "player_id":      player_id,
        "name":           player["name"],
        "position":       player["position"],
        "sub_position":   player["sub_position"],
        "jersey_number":  player["number"],
        "age":            player["age"],
        "nationality":    player["nationality"],
        "height_cm":      player["height_cm"],
        "weight_kg":      player["weight_kg"],
        "preferred_foot": player["preferred_foot"],
        "status":         player["status"],
        "intensity":      intensity,
        "macros":         macros,
        "_mock":          True,
    }