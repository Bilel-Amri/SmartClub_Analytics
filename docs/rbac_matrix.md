# PhysioAI — RBAC Permission Matrix

## Roles

| Role | Description |
|---|---|
| `admin` | Full system access including imports and audit log |
| `physio` | Full physio module access — clinical staff |
| `coach` | Read-only on physio data — tactical staff |
| `scout` | No physio access |
| `nutritionist` | No physio access |

---

## Permission Classes (`backend/physio/permissions.py`)

| Class | Who can access | Used on |
|---|---|---|
| `IsAdminOrPhysio` | admin, physio | Write-capable endpoints |
| `IsCoachOrAbove` | admin, physio, coach | Read-only endpoints |
| `IsPhysioReadOnly` | POST: admin+physio / GET: coach+ | Mixed CRUD views |
| `IsAdminOnly` | admin | CSV import, audit log |

---

## Endpoint Matrix

| Endpoint | Method | admin | physio | coach | scout | nutritionist |
|---|---|:---:|:---:|:---:|:---:|:---:|
| `injuries/` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `injuries/` | POST | ✅ | ✅ | ❌ | ❌ | ❌ |
| `injuries/<id>/` | GET/PUT/DELETE | ✅ | ✅ | ❌ | ❌ | ❌ |
| `training-loads/` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `training-loads/` | POST | ✅ | ✅ | ❌ | ❌ | ❌ |
| `training-loads/<id>/` | GET/PUT/DELETE | ✅ | ✅ | ❌ | ❌ | ❌ |
| `injury-risk/<id>/` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `duration-predict/` | POST | ✅ | ✅ | ❌ | ❌ | ❌ |
| `overview/today` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `flagged` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `returning` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `acknowledge/<id>/` | POST | ✅ | ✅ | ❌ | ❌ | ❌ |
| `player/<id>/predictions/` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `model-metadata` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `audit-log/` | GET | ✅ | ❌ | ❌ | ❌ | ❌ |
| `import/injuries/` | POST | ✅ | ❌ | ❌ | ❌ | ❌ |
| `import/loads/` | POST | ✅ | ❌ | ❌ | ❌ | ❌ |
| `global/summary` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `global/players` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `global/metrics/<id>/` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `global/risk/<id>/` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `global/shap/<id>/` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `global/timeseries/<id>/` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |
| `global/squad-overview` | GET | ✅ | ✅ | ✅ | ❌ | ❌ |

---

## Audit Actions Logged

All physio API actions that write data are logged to `AuditLog`.

| Action code | Trigger |
|---|---|
| `injury_created` | POST `injuries/` |
| `injury_updated` | PUT `injuries/<id>/` |
| `injury_deleted` | DELETE `injuries/<id>/` |
| `load_created` | POST `training-loads/` |
| `risk_predicted` | GET `injury-risk/<id>/` or `global/risk/<id>/` |
| `flag_acknowledged` | POST `acknowledge/<id>/` |
| `csv_import` | POST `import/injuries/` or `import/loads/` |
| `model_queried` | GET `model-metadata` |

---

## JWT Token Claims

The role is extracted from the `groups` claim on the JWT or from the user's Django group membership.

```python
def has_permission(self, request, view):
    return (
        request.user.is_authenticated
        and hasattr(request.user, "groups")
        and request.user.groups.filter(name__in=["physio", "admin"]).exists()
    )
```

For users without an explicit group, `is_staff=True` is treated as `admin`.

---

## Adding a New Role

1. Create Django group via admin or migration
2. Add group name to the relevant permission class `allowed_groups` list in `permissions.py`
3. Update this matrix
