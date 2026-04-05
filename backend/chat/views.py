"""
Chatbot view — queries the database directly via Django ORM.
No HTTP self-calls (those broke auth). All data fetched in-process.
"""
from __future__ import annotations
from rest_framework.views import APIView
from rest_framework.response import Response


def _resolve_player(name_fragment: str):
    """
    Return (player_obj, full_name) or (None, None) by partial name match.
    Tries progressively shorter word-windows so 'Custom Player 2' beats
    'Custom Player 1' even though both contain 'Custom'.
    """
    from scout.models import Player
    STOP = {
        'injury', 'risk', 'for', 'of', 'the', 'show', 'me', 'get',
        'what', 'is', 'training', 'load', 'nutrition', 'plan', 'supplement',
        'info', 'player', 'players', 'tell', 'about', 'recent', 'latest',
        'wellness', 'contract', 'salary', 'squad', 'meal', 'log', 'session',
        'team', 'and', 'or', 'give', 'with', 'top', 'best', 'similar',
        'like', 'compare', 'his', 'her', 'their', 'this', 'that',
    }
    # Keep words not in STOP; always keep pure digits
    words = name_fragment.split()
    kept = [w for w in words if w.lower() not in STOP and (w.isdigit() or len(w) > 1)]
    if not kept:
        return None, None

    all_players = list(Player.objects.all())

    # Try longest windows first — returns as soon as exactly 1 match found
    for size in range(len(kept), 0, -1):
        for start in range(len(kept) - size + 1):
            chunk = ' '.join(kept[start:start + size])
            matches = [p for p in all_players if chunk.lower() in p.full_name.lower()]
            if len(matches) == 1:
                return matches[0], matches[0].full_name

    return None, None


def _all_players():
    from scout.models import Player
    return list(Player.objects.all().values('id', 'full_name', 'position', 'age',
                                            'weight_kg', 'height_cm', 'current_club'))


ROUTE_RULES = [
    (['hi', 'hey', 'hello', 'hii', 'helo', 'hola', 'salut', 'bonjour',
      'good morning', 'good afternoon', 'good evening', 'yo', 'sup',
      'howdy', 'greetings', "what's up", 'whats up'],                           'greeting'),
    (['help', 'what can you', 'what do you', 'commands'],                        'help'),
    (['squad overview', 'squad fitness', 'team overview', 'team risk',
      'team fitness', 'all risks', 'squad risk'],                                 'squad'),
    (['shortlist', 'recruit', 'find player'],                                     'shortlist'),
    (['top', 'best', 'who are'],                                                  'shortlist'),
    (['similar', 'compare'],                                                      'similar'),
    (['injury risk', 'risk score', 'risk for', 'will be injured'],               'injury_risk'),
    (['wellness', 'fatigue', 'readiness', 'soreness', 'mood score'],             'wellness'),
    (['meal log', 'actual intake', 'food log', 'what i ate', 'logged meals'],    'meal_log'),
    (['nutrition', 'meal plan', 'diet', 'macros', 'daily plan'],                 'nutri_plan'),
    (['supplement'],                                                               'supplements'),
    (['contract', 'salary', 'wage', 'transfer fee'],                             'contract'),
    (['injur', 'injured', 'hurt', 'sprain', 'strain'],                           'injuries'),
    (['training load', 'training session', 'rpe', 'sprint', 'session', 'load'],  'training_load'),
    (['show all', 'list all', 'show player', 'list player',
      'all players', 'player info', 'who is', 'tell me about'],                  'player_info'),
]


def route_query(msg: str) -> str:
    ml = msg.lower().strip()
    # Build a set of individual words for exact word matching
    words = set(ml.split())
    for keywords, intent in ROUTE_RULES:
        for kw in keywords:
            # Short single words (≤4 chars): require exact word match to avoid
            # substring false positives (e.g. "hi" inside "this", "yo" inside "your")
            if len(kw) <= 4 and ' ' not in kw:
                if kw in words:
                    return intent
            else:
                if kw in ml:
                    return intent
    return 'unknown'


def handle_chat(message: str) -> str:
    intent = route_query(message)

    # ── GREETING ────────────────────────────────────────────────────────────────
    if intent == 'greeting':
        from scout.models import Player
        count = Player.objects.count()
        player_hint = (
            f"I have **{count} player(s)** in the database."
            if count else "No players added yet — add them via PhysioAI or Scout."
        )
        return (
            "Hello! 👋 Welcome to **SmartClub AI Assistant**.\n\n"
            f"{player_hint}\n\n"
            "Here are some things you can ask me:\n"
            "• *squad overview* — see all players + risk\n"
            "• *injury risk for [name]* — ML prediction\n"
            "• *nutrition plan for [name]* — macro targets\n"
            "• *training load for [name]* — recent sessions\n"
            "• *help* — full command list"
        )

    if intent == 'help':
        return (
            "**SmartClub Assistant — available commands:**\n"
            "• *squad overview* — all players + risk at a glance\n"
            "• *top strikers* / *top midfielders* — players by position\n"
            "• *player info [name]* — age, weight, height, club\n"
            "• *contract for [name]* — salary, transfer fee, dates\n"
            "• *injury risk for [name]* — ML-based 7-day risk prediction\n"
            "• *recent injuries* — injury records\n"
            "• *training load for [name]* — recent sessions\n"
            "• *wellness for [name]* — sleep & RPE trend\n"
            "• *nutrition plan for [name]* — macro targets\n"
            "• *meal log for [name]* — actual vs target intake\n"
            "• *supplements for [name]* — WADA compliance tracker"
        )

    # ── SQUAD OVERVIEW ─────────────────────────────────────────────────────────
    if intent == 'squad':
        from scout.models import Player
        from physio.models import InjuryRiskPrediction
        players = list(Player.objects.all())
        if not players:
            return "No players in the database yet."
        lines = [f"**Squad Overview** ({len(players)} players):"]
        for p in players:
            pred = InjuryRiskPrediction.objects.filter(player=p).order_by('-predicted_at').first()
            if pred:
                pct = round(pred.risk_probability * 100, 1)
                band = pred.risk_band.upper()
                risk_str = f"Risk: {pct}% ({band})"
            else:
                risk_str = "Risk: not assessed"
            lines.append(f"• {p.full_name} ({p.position or '?'}) — {risk_str}")
        return '\n'.join(lines)

    # ── SHORTLIST / TOP PLAYERS ────────────────────────────────────────────────
    if intent == 'shortlist':
        from scout.models import Player
        pos_filter = None
        pos_map = {'goalkeeper': 'GK', 'defender': 'CB', 'midfielder': 'CM',
                   'forward': 'FW', 'striker': 'ST', 'winger': 'RW'}
        ml = message.lower()
        for alias, code in pos_map.items():
            if alias in ml:
                pos_filter = code
                break
        for code in ['GK', 'CB', 'RB', 'LB', 'CM', 'CDM', 'CAM', 'RW', 'LW', 'ST']:
            if code.lower() in ml.split():
                pos_filter = code
                break
        qs = Player.objects.all()
        if pos_filter:
            qs = qs.filter(position=pos_filter)
        players = list(qs.values('full_name', 'position', 'age', 'current_club')[:8])
        if not players:
            return f"No players found{' at position ' + pos_filter if pos_filter else ''} in the database."
        lines = [f"**Players{' — ' + pos_filter if pos_filter else ''}** ({len(players)} found):"]
        for i, p in enumerate(players, 1):
            age_str = f", age {p['age']}" if p['age'] else ""
            club_str = f" | {p['current_club']}" if p['current_club'] else ""
            lines.append(f"{i}. {p['full_name']} ({p['position'] or '?'}{age_str}){club_str}")
        return '\n'.join(lines)

    # ── SIMILAR PLAYERS ────────────────────────────────────────────────────────
    if intent == 'similar':
        player, pname = _resolve_player(message)
        if not player:
            return "I couldn't find that player. Please provide their name."
        from scout.models import Player
        similar = list(Player.objects.filter(position=player.position).exclude(pk=player.pk)[:5])
        if not similar:
            return f"No similar players found to {pname}."
        lines = [f"**Players similar to {pname}** (same position: {player.position}):"]
        for p in similar:
            lines.append(f"• {p.full_name} | Age {p.age or '?'} | {p.current_club or 'Unknown club'}")
        return '\n'.join(lines)

    # ── INJURY RISK ────────────────────────────────────────────────────────────
    if intent == 'injury_risk':
        player, pname = _resolve_player(message)
        if not player:
            return "Please mention the player's name to get their injury risk, e.g. *injury risk for Mohamed*."
        from physio.models import InjuryRiskPrediction
        pred = InjuryRiskPrediction.objects.filter(player=player).order_by('-predicted_at').first()
        if not pred:
            return (f"No risk prediction found for **{pname}**.\n"
                    "Go to PhysioAI → Risk tab → select the player → click Predict Risk.")
        pct = round(pred.risk_probability * 100, 1)
        factors = pred.shap_factors or []
        top = ', '.join(str(f.get('feature', '')).replace('_', ' ') for f in factors[:3]) or 'N/A'
        return (
            f"**Injury risk for {pname}** ({pred.horizon_days}-day horizon):\n"
            f"• Risk: **{pct}%** — {pred.risk_band.upper()}\n"
            f"• Confidence: {pred.confidence_band}\n"
            f"• Top drivers: {top}\n"
            f"• Action: {pred.recommended_action or '—'}\n"
            f"• Predicted: {pred.predicted_at.strftime('%d %b %Y %H:%M')}"
        )

    # ── WELLNESS ───────────────────────────────────────────────────────────────
    if intent == 'wellness':
        from physio.models import TrainingLoad
        player, pname = _resolve_player(message)
        qs = TrainingLoad.objects.select_related('player').order_by('-date')
        if player:
            qs = qs.filter(player=player)
        records = list(qs[:7])
        if not records:
            return (f"No wellness data found{' for ' + pname if pname else ''}. "
                    "Add training sessions in PhysioAI → Loads tab.")
        label = f"**{pname}**" if player else "**squad**"
        lines = [f"**Wellness summary — {label}** (last {len(records)} sessions):"]
        for r in records:
            sleep = f"Sleep {r.sleep_quality:.1f}/10" if r.sleep_quality else "Sleep N/A"
            rpe   = f"RPE {r.rpe:.1f}" if r.rpe else "RPE N/A"
            dist  = f"{r.total_distance_km} km" if r.total_distance_km else ""
            detail = " | ".join(x for x in [sleep, rpe, dist] if x)
            lines.append(f"• {r.player.full_name} — {r.date.strftime('%d %b')} → {detail}")
        return '\n'.join(lines)

    # ── INJURIES ───────────────────────────────────────────────────────────────
    if intent == 'injuries':
        from physio.models import Injury
        player, pname = _resolve_player(message)
        qs = Injury.objects.select_related('player').order_by('-date')
        if player:
            qs = qs.filter(player=player)
        records = list(qs[:8])
        if not records:
            label = pname if player else 'any player'
            return f"No injury records found for {label}."
        label = f"**{pname}**" if player else "**all players**"
        lines = [f"**Recent injuries — {label}** ({len(records)} records):"]
        for inj in records:
            days = f"{inj.days_absent}d absent" if inj.days_absent else "duration unknown"
            lines.append(
                f"• {inj.player.full_name} — {inj.injury_type} "
                f"({inj.severity}, {days}) on {inj.date.strftime('%d %b %Y')}"
            )
        return '\n'.join(lines)

    # ── TRAINING LOAD ──────────────────────────────────────────────────────────
    if intent == 'training_load':
        from physio.models import TrainingLoad
        player, pname = _resolve_player(message)
        qs = TrainingLoad.objects.select_related('player').order_by('-date')
        if player:
            qs = qs.filter(player=player)
        records = list(qs[:7])
        if not records:
            msg = f"No training load records found{' for ' + pname if pname else ''}."
            return msg + "\nAdd sessions in PhysioAI → Loads tab."
        label = f"**{pname}**" if player else "**squad**"
        lines = [f"**Recent training loads — {label}**:"]
        for l in records:
            dist_str = f"{l.total_distance_km} km" if l.total_distance_km else ""
            rpe_str = f"RPE {l.rpe}" if l.rpe else ""
            sleep_str = f"Sleep {l.sleep_quality}/10" if l.sleep_quality else ""
            detail = " | ".join(x for x in [dist_str, rpe_str, sleep_str] if x)
            lines.append(f"• {l.player.full_name} — {l.date.strftime('%d %b')} → {detail or 'no data'}")
        return '\n'.join(lines)

    # ── NUTRITION PLAN ─────────────────────────────────────────────────────────
    if intent == 'nutri_plan':
        from nutri.models import DailyPlan
        player, pname = _resolve_player(message)
        if not player:
            return "Please mention the player's name, e.g. *nutrition plan for Mohamed*."
        plan = DailyPlan.objects.filter(player=player).order_by('-date').first()
        if not plan:
            return f"No nutrition plan found for **{pname}**. Go to NutriAI → Generate Plan."
        return (
            f"**Latest nutrition plan for {pname}**:\n"
            f"• Date: {plan.date} ({plan.day_type} / {plan.goal})\n"
            f"• Calories: **{plan.calories} kcal**\n"
            f"• Protein: {plan.protein_g}g | Carbs: {plan.carbs_g}g | Fat: {plan.fat_g}g\n"
            f"• Notes: {plan.notes or '—'}"
        )

    # ── MEAL LOG ──────────────────────────────────────────────────────────────
    if intent == 'meal_log':
        from nutri.models import DailyPlan, MealLog
        player, pname = _resolve_player(message)
        if not player:
            return "Please mention the player's name, e.g. *meal log for Mohamed*."
        plan = DailyPlan.objects.filter(player=player).order_by('-date').first()
        if not plan:
            return f"No nutrition plan found for **{pname}**. Generate one in NutriAI first."
        logs = list(MealLog.objects.filter(plan=plan).order_by('meal_time'))
        target_str = (
            f"Target: **{plan.calories:.0f} kcal** | "
            f"P {plan.protein_g:.0f}g | C {plan.carbs_g:.0f}g | F {plan.fat_g:.0f}g"
        )
        if not logs:
            return (
                f"**{pname} — {plan.date}** ({plan.day_type}/{plan.goal}):\n"
                f"{target_str}\n"
                "No meals logged yet for this plan."
            )
        act_cal = sum(l.calories for l in logs)
        act_pro = sum(l.protein_g for l in logs)
        act_carb = sum(l.carbs_g for l in logs)
        act_fat = sum(l.fat_g for l in logs)
        lines = [
            f"**{pname} — {plan.date}** ({plan.day_type}/{plan.goal}):",
            target_str,
            f"Actual:  **{act_cal:.0f} kcal** | P {act_pro:.0f}g | C {act_carb:.0f}g | F {act_fat:.0f}g",
            f"Gap:     **{plan.calories - act_cal:+.0f} kcal**",
            "",
            "**Meal entries:**",
        ]
        for l in logs:
            lines.append(f"• {l.meal_time}: {l.food.name} {l.grams:.0f}g → {l.calories:.0f} kcal")
        return '\n'.join(lines)

    # ── SUPPLEMENTS ────────────────────────────────────────────────────────────
    if intent == 'supplements':
        from nutri.models import Supplement
        player, pname = _resolve_player(message)
        qs = Supplement.objects.select_related('player').order_by('-date')
        if player:
            qs = qs.filter(player=player)
        records = list(qs[:6])
        if not records:
            return f"No supplement records found{' for ' + pname if pname else ''}."
        lines = [f"**Supplements{' for ' + pname if pname else ''}** ({len(records)} records):"]
        uncert = []
        for s in records:
            cert = "Certified" if s.batch_tested else "NOT certified"
            dose = f"{s.dose_mg:.0f}mg" if s.dose_mg else ""
            lines.append(f"• {s.player.full_name} — {s.name} {dose} | {cert}")
            if not s.batch_tested:
                uncert.append(s)
        if uncert:
            lines.append(f"\nWADA alert: {len(uncert)} supplement(s) lack Informed Sport certification!")
        return '\n'.join(lines)

    # ── CONTRACT ──────────────────────────────────────────────────────────────
    if intent == 'contract':
        from scout.models import Player, Contract
        player, pname = _resolve_player(message)
        if not player:
            # List all contracts
            contracts = list(Contract.objects.select_related('player').all()[:10])
            if not contracts:
                return "No contract data found in the database."
            lines = [f"**All contracts** ({len(contracts)} records):"]
            for c in contracts:
                sal = f"EUR {float(c.salary_yearly):,.0f}/yr" if c.salary_yearly else "—"
                fee = f"EUR {float(c.transfer_fee):,.0f}" if c.transfer_fee else "—"
                end = c.end_date.strftime('%b %Y') if c.end_date else "open-ended"
                lines.append(f"• {c.player.full_name} — Salary: {sal} | Fee: {fee} | Expires: {end}")
            return '\n'.join(lines)
        try:
            c = player.contract
            sal = f"EUR {float(c.salary_yearly):,.0f}/yr" if c.salary_yearly else '—'
            fee = f"EUR {float(c.transfer_fee):,.0f}" if c.transfer_fee else '—'
            start = c.start_date.strftime('%d %b %Y') if c.start_date else '—'
            end   = c.end_date.strftime('%d %b %Y') if c.end_date else 'open-ended'
            return (
                f"**Contract — {pname}:**\n"
                f"• Salary: {sal}\n"
                f"• Transfer fee: {fee}\n"
                f"• Duration: {start} → {end}"
            )
        except Exception:
            return f"No contract data found for **{pname}**."

    # ── PLAYER INFO ────────────────────────────────────────────────────────────
    if intent == 'player_info':
        player, pname = _resolve_player(message)
        if not player:
            players = _all_players()
            if not players:
                return "No players in the database yet. Add them via Scout or PhysioAI."
            lines = [f"**Players in the system** ({len(players)} total):"]
            for p in players[:10]:
                age = f" age {p['age']}" if p['age'] else ""
                lines.append(f"• {p['full_name']} ({p['position'] or '?'}){age}")
            return '\n'.join(lines)
        lines = [f"**{player.full_name}**"]
        lines.append(f"• Position: {player.position or '—'} | Age: {player.age or '—'}")
        lines.append(f"• Height: {player.height_cm or '—'} cm | Weight: {player.weight_kg or '—'} kg")
        lines.append(f"• Club: {player.current_club or '—'} | Nationality: {player.nationality or '—'}")
        try:
            c = player.contract
            sal = f"EUR {float(c.salary_yearly):,.0f}" if c.salary_yearly else '—'
            fee = f"EUR {float(c.transfer_fee):,.0f}" if c.transfer_fee else '—'
            lines.append(f"• Salary: {sal}/yr | Transfer fee: {fee}")
        except Exception:
            lines.append("• No contract data available.")
        return '\n'.join(lines)

    # ── UNKNOWN ────────────────────────────────────────────────────────────────
    # Nothing matched — give a friendly hint
    short = message.strip().lower()
    if len(short) <= 10 and not any(c.isspace() for c in short):
        # Single short word like 'hy', 'ok', 'test', 'yo'
        return (
            "Hi there! 👋 I didn't quite understand that.\n"
            "Try typing *help* to see everything I can do, "
            "or start with *squad overview*."
        )
    return (
        "I didn't understand that. Here are some examples:\n"
        "• *squad overview*\n"
        "• *injury risk for [player name]*\n"
        "• *nutrition plan for [player name]*\n"
        "• *recent injuries*\n"
        "• *help* — full command list"
    )


class ChatView(APIView):
    def post(self, request):
        message = request.data.get('message', '').strip()
        if not message:
            return Response({'error': 'message is required'}, status=400)
        try:
            reply = handle_chat(message)
        except Exception as e:
            import traceback
            reply = f"Internal error: {str(e)}\n\n{traceback.format_exc()}"
        return Response({'reply': reply})
