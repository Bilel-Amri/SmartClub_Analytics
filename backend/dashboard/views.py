"""
dashboard/views.py
==================
GET /api/dashboard/summary/

Returns real aggregated data for the three dashboard charts:
  - position_distribution  → BarChart  (player count by position group)
  - player_status_mix      → PieChart  (Fit / At-Risk / Injured / Rehab)
  - monthly_injury_trend   → AreaChart (injury events per calendar month, last 12 months)

Plus bonus metrics:
  - top_scorers_xg         → list[{name, xg_proxy, position}] top 8 by xg_proxy
  - squad_load_avg         → last 30-day avg daily_load from GlobalDailyRecord (SoccerMon)
"""

from datetime import date, timedelta
from collections import defaultdict, Counter

from django.db.models import Count, Avg
from django.db.models.functions import TruncMonth
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from scout.models import Player, PlayerMatchStats
from physio.models import Injury, TrainingLoad, GlobalDailyRecord


# ── Position groupings ──────────────────────────────────────────────────────
POS_GROUP = {
    'GK':  'Goalkeepers',
    'CB':  'Defenders',
    'LB':  'Defenders',
    'RB':  'Defenders',
    'CDM': 'Midfielders',
    'CM':  'Midfielders',
    'CAM': 'Midfielders',
    'LW':  'Forwards',
    'RW':  'Forwards',
    'FW':  'Forwards',
}
CHART_COLORS = {
    'Forwards':    'var(--neon-pink)',
    'Midfielders': 'var(--neon-orange)',
    'Defenders':   'var(--neon-yellow)',
    'Goalkeepers': 'var(--neon-cyan)',
}


class DashboardSummaryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        # ── 1. Position distribution ─────────────────────────────────────
        pos_counts = Counter()
        for pos in Player.objects.values_list('position', flat=True):
            group = POS_GROUP.get(pos, 'Other')
            pos_counts[group] += 1

        position_distribution = [
            {'name': grp, 'count': pos_counts[grp], 'fill': CHART_COLORS.get(grp, '#888')}
            for grp in ['Forwards', 'Midfielders', 'Defenders', 'Goalkeepers']
            if pos_counts[grp] > 0
        ]

        # ── 2. Player status mix ─────────────────────────────────────────
        total_players = Player.objects.count()
        recent_cutoff = date.today() - timedelta(days=90)

        recently_injured_ids = set(
            Injury.objects.filter(date__gte=recent_cutoff)
                          .values_list('player_id', flat=True)
        )

        # Use avg RPE from recent training loads to flag "at risk"
        at_risk_ids = set(
            TrainingLoad.objects.filter(date__gte=recent_cutoff, rpe__gte=7.5)
                                .values_list('player_id', flat=True)
        ) - recently_injured_ids

        injured_count  = len(recently_injured_ids)
        at_risk_count  = len(at_risk_ids)
        fit_count      = max(0, total_players - injured_count - at_risk_count)

        player_status_mix = [
            {'name': 'Fit',         'value': fit_count,     'fill': 'var(--neon-cyan)'},
            {'name': 'At Risk',     'value': at_risk_count, 'fill': 'var(--neon-orange)'},
            {'name': 'Injured',     'value': injured_count, 'fill': 'var(--neon-pink)'},
        ]
        player_status_mix = [s for s in player_status_mix if s['value'] > 0]

        # ── 3. Monthly injury trend (last 12 months) ─────────────────────
        twelve_months_ago = date.today() - timedelta(days=365)
        monthly_qs = (
            Injury.objects
                  .filter(date__gte=twelve_months_ago)
                  .annotate(month=TruncMonth('date'))
                  .values('month')
                  .annotate(count=Count('id'))
                  .order_by('month')
        )
        monthly_injury_trend = [
            {'name': row['month'].strftime('%b %Y'), 'value': row['count']}
            for row in monthly_qs
        ]

        # ── 4. Top 8 players by xG proxy ────────────────────────────────
        top_scorers = []
        for stats in (PlayerMatchStats.objects
                                      .select_related('player')
                                      .order_by('-xg_proxy')[:8]):
            top_scorers.append({
                'name':     stats.player.full_name,
                'xg_proxy': round(float(stats.xg_proxy or 0), 2),
                'xa_proxy': round(float(stats.xa_proxy or 0), 2),
                'position': stats.player.position,
            })

        # ── 5. Squad average daily load (SoccerMon, last 30 days) ───────
        load_cutoff = date.today() - timedelta(days=30)
        squad_load_avg = None
        try:
            agg = GlobalDailyRecord.objects.filter(date__gte=load_cutoff).aggregate(avg=Avg('daily_load'))
            squad_load_avg = round(float(agg['avg']), 1) if agg['avg'] is not None else None
        except Exception:
            pass

        return Response({
            'position_distribution': position_distribution,
            'player_status_mix':     player_status_mix,
            'monthly_injury_trend':  monthly_injury_trend,
            'top_scorers_xg':        top_scorers,
            'squad_load_avg':        squad_load_avg,
            'total_players':         total_players,
        })
