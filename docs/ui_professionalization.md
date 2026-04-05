# PhysioAI — UI Professionalization Guide

## Design Tokens

| Token | Value | Usage |
|---|---|---|
| Risk Low | `#22c55e` | Green — safe / low risk |
| Risk Medium | `#f59e0b` | Amber — monitor / moderate risk |
| Risk High | `#ef4444` | Red — action required / high risk |
| Conf. Low | `#94a3b8` | Slate — insufficient data |
| Surface 0 | `#0f172a` | Deepest background |
| Surface 1 | `#1e293b` | Card background |
| Surface 2 | `#273344` | Table row hover / skeleton mid |
| Text Primary | `#f1f5f9` | Main content |
| Text Secondary | `#94a3b8` | Labels, subtitles |
| Text Muted | `#64748b` | Captions, metadata |
| Text Disabled | `#475569` | Empty states |
| Brand Blue | `#3b82f6` | Primary buttons, metric highlights |

---

## Component Catalogue

### `RiskBadge`
```jsx
<RiskBadge band="high" pct={72.3} />
```
Renders a coloured pill with risk band label and optional percentage. Uses `RISK_COLORS` map.

---

### `ConfidenceBadge`
```jsx
<ConfidenceBadge band="medium" />
```
Compact indicator appended to risk display. Uses `CONF_COLORS` map.

---

### `KpiCard`
```jsx
<KpiCard label="High risk" value={3} color="#ef4444" sub="of 22 players" />
```
Headline metric tile shown in squad KPI row. `color` tints the value number.

---

### `Skeleton`
```jsx
<Skeleton h={20} w="60%" />
```
Shimmer loading placeholder. Animated via CSS keyframe `shimmer`.

```css
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

---

### `EmptyState`
```jsx
<EmptyState icon="📭" text="No squad data — add training loads first" />
```
Centred icon + message. Use `icon="✅"` for positive empty states (no flags).

---

### `Flash`
```jsx
<Flash msg={flash} />
```
Fixed-position toast (top-right). Auto-clears after 3500ms via `setTimeout`. Pass `""` to hide.

---

### `ShapFactors`
```jsx
<ShapFactors factors={[{ feature: "acwr_7d", shap: 0.18 }, ...]} />
```
Proportional horizontal bars, red for positive SHAP (increases risk), green for negative. Normalised to max absolute value.

---

### `RiskGauge`
```jsx
<RiskGauge prob={0.72} band="high" />
```
Animated progress bar + numeric value. Width animates via CSS `transition: width 0.5s ease`.

---

### `DecisionCard`
```jsx
<DecisionCard result={riskResult} />
```
The primary decision-support component. Contains:
- Header row: `RiskBadge` + `ConfidenceBadge` + optional 🚩 flag warning
- Limited history banner (amber) if `sufficient_history === false`
- Recommended action section
- Optional monitoring note (dark panel)
- Top SHAP driver footer

---

### `SquadRow`
```jsx
<SquadRow r={player} onSelect={id => setTab("risk")} />
```
Clickable table row. Clicking navigates to Risk tab with player pre-selected. Shows risk bar, flag icon, load spike indicator.

---

## Tab Navigation

### GlobalPanel
| Tab key | Label | Content |
|---|---|---|
| `squad` | Squad Overview | Sortable risk table of all global players |
| `predict` | Individual Risk | Player selector + timeseries + DecisionCard |

### ClubPanel
| Tab key | Label | Content |
|---|---|---|
| `squad` | 🏟 Squad | Club squad KPI + sortable risk table |
| `risk` | ⚡ Risk | Risk prediction form + DecisionCard |
| `flagged` | 🚩 Flagged | Unacknowledged high-risk + returning players |
| `injuries` | 🦴 Injuries | Injury form + table + returning sidebar |
| `loads` | 📊 Loads | Load form + line chart + table |
| `history` | 📈 History | Prediction trend sparkline + history table |

---

## Layout Primitives

| Class | Description |
|---|---|
| `.module` | Outer page container |
| `.module-header` | Header row with icon, title, subtitle |
| `.card` | White-on-dark content card |
| `.card-form` | Form card with reduced padding |
| `.two-col` | Flex row: left content block + right sidebar |
| `.risk-panel` | Right sidebar in two-col layout |
| `.tabs` | Horizontal tab bar |
| `.tab` | Individual tab button |
| `.tab.active` | Selected state |
| `.physio-active` | Blue underline for physio tabs |
| `.tab-small` | Compact variant (horizon toggles) |
| `.table-wrap` | Overflow-x scroll wrapper |
| `.btn-primary` | Blue action button |
| `.btn-danger` | Red action button (risk prediction) |
| `.badge.mild/.moderate/.severe` | Severity pill |
| `.empty` | Muted empty cell |

---

## Data Source Toggle

The root `PhysioAI` component renders a toggle in the module header:
- 🌍 **SoccerMon** — global anonymised dataset (TeamA / TeamB players)
- 🏠 **Club Seed** — local seeded club players

State: `dataSource` ∈ `["global", "club"]`

This controls which panel (`GlobalPanel` or `ClubPanel`) is mounted.
