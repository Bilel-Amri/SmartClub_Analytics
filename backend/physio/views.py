"""
Physio endpoints with ML integration shell only.

This module intentionally does NOT include training, preprocessing,
feature engineering, or embedded model inference logic.
"""

import csv
import io
import json
from datetime import timedelta
from pathlib import Path

from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from scout.models import Player
from .prediction_service import prediction_service

from .models import (
    AuditLog,
    FlagAcknowledgment,
    GlobalDailyRecord,
    GlobalInjuryEvent,
    GlobalPlayer,
    Injury,
    InjuryRiskPrediction,
    TrainingLoad,
)
from .permissions import IsAdminOnly, IsAdminOrPhysio, IsCoachOrAbove, IsPhysioReadOnly
from .serializers import InjurySerializer, TrainingLoadSerializer

# Folder for user-provided model assets.
MODEL_BUNDLE_DIR = Path(__file__).resolve().parent / "model_bundle"

# Ordered feature contract for integration.
FEATURE_SCHEMA = [
    {"name": "age", "dtype": "int", "required": True, "nullable": False, "allowed_values": {"min": 14, "max": 50}, "missing_rule": "reject"},
    {"name": "previous_injury_count", "dtype": "int", "required": True, "nullable": False, "allowed_values": {"min": 0}, "missing_rule": "reject"},
    {"name": "position", "dtype": "str", "required": True, "nullable": False, "allowed_values": None, "missing_rule": "reject"},
    {"name": "injury_type", "dtype": "str", "required": True, "nullable": False, "allowed_values": None, "missing_rule": "reject"},
    {"name": "is_recurring", "dtype": "int", "required": False, "nullable": True, "allowed_values": {"min": 0, "max": 1}, "missing_rule": "default_0"},
]

REQUIRED_MODEL_FILES = [
    "manifest.json",
]

OPTIONAL_MODEL_FILES = [
    "model_severity.pkl",
    "model.pkl",
    "model.joblib",
    "severity_schema.json",
    "vulnerability_config.json",
    "api_contracts.json",
    "class_mapping.json",
    "preprocessor.pkl",
    "preprocessor.joblib",
    "requirements-ml.txt",
]


def _load_feature_schema():
    schema_path = None
    for candidate in [MODEL_BUNDLE_DIR / "feature_schema.json", MODEL_BUNDLE_DIR / "severity_schema.json"]:
        if candidate.exists():
            schema_path = candidate
            break
    if schema_path is None:
        return FEATURE_SCHEMA
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("all_features"), list):
            return [{"name": n, "dtype": "float", "required": True, "nullable": False, "allowed_values": None, "missing_rule": "reject"} for n in data["all_features"]]
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return FEATURE_SCHEMA


def _cast_value(raw, dtype):
    if raw is None:
        return None
    if dtype == "int":
        return int(raw)
    if dtype == "float":
        return float(raw)
    if dtype == "bool":
        if isinstance(raw, bool):
            return raw
        txt = str(raw).strip().lower()
        return txt in ("1", "true", "yes", "y")
    return str(raw)


def _validate_and_normalize_features(features, schema):
    normalized = {}
    errors = []

    for col in schema:
        name = col.get("name")
        dtype = col.get("dtype", "float")
        required = bool(col.get("required", False))
        missing_rule = col.get("missing_rule", "allow_null")
        allowed = col.get("allowed_values")

        raw = features.get(name)
        is_missing = raw is None or raw == ""

        if is_missing:
            if required and missing_rule == "reject":
                errors.append(f"Missing required feature: {name}")
                continue
            if missing_rule == "default_0":
                normalized[name] = 0
            else:
                normalized[name] = None
            continue

        try:
            val = _cast_value(raw, dtype)
        except Exception:
            errors.append(f"Invalid type for {name}; expected {dtype}")
            continue

        if isinstance(allowed, dict):
            min_v = allowed.get("min")
            max_v = allowed.get("max")
            if min_v is not None and val < min_v:
                errors.append(f"{name} must be >= {min_v}")
            if max_v is not None and val > max_v:
                errors.append(f"{name} must be <= {max_v}")
        elif isinstance(allowed, list) and allowed and val not in allowed:
            errors.append(f"{name} must be one of: {allowed}")

        normalized[name] = val

    return normalized, errors


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _audit(request, action, resource_type="", resource_id=None, detail=None):
    try:
        AuditLog.objects.create(
            user=request.user if request.user and request.user.is_authenticated else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
            ip_address=_client_ip(request),
        )
    except Exception:
        pass


def _model_bundle_status():
    present = []
    missing = []
    for f in REQUIRED_MODEL_FILES:
        if (MODEL_BUNDLE_DIR / f).exists():
            present.append(f)
        else:
            missing.append(f)

    has_model_binary = (
        (MODEL_BUNDLE_DIR / "model_severity.pkl").exists()
        or (MODEL_BUNDLE_DIR / "model.pkl").exists()
        or (MODEL_BUNDLE_DIR / "model.joblib").exists()
    )
    if has_model_binary:
        present.append("model binary")
    else:
        missing.append("model_severity.pkl or model.pkl or model.joblib")

    has_schema = (MODEL_BUNDLE_DIR / "severity_schema.json").exists() or (MODEL_BUNDLE_DIR / "feature_schema.json").exists()
    if has_schema:
        present.append("schema file")
    else:
        missing.append("severity_schema.json or feature_schema.json")

    return {
        "configured": len(missing) == 0,
        "model_bundle_dir": str(MODEL_BUNDLE_DIR),
        "required_files": REQUIRED_MODEL_FILES,
        "optional_files": OPTIONAL_MODEL_FILES,
        "present": present,
        "missing": missing,
    }


def _integration_error_response():
    return Response(
        {
            "detail": "ML model is not configured yet. Add your own exported model bundle.",
            "integration": _model_bundle_status(),
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _risk_band(prob):
    if prob is None:
        return "unknown"
    if prob >= 0.6:
        return "high"
    if prob >= 0.35:
        return "medium"
    return "low"


def _base_prediction_payload(probability, model_version="external-model"):
    probability = float(probability)
    band = _risk_band(probability)
    return {
        "risk_probability": probability,
        "risk_pct": round(probability * 100.0, 2),
        "risk_band": band,
        "confidence_band": "medium",
        "recommended_action": "Review with your configured model protocol.",
        "monitoring_note": "Prediction generated by external user model.",
        "flag_for_physio_review": band == "high",
        "sufficient_history": True,
        "data_quality_score": 1.0,
        "top_factor": "",
        "shap_factors": [],
        "model_version": model_version,
    }


def _extract_features_from_latest_load(player):
    latest_injury = player.injuries.order_by("-date").first()

    return {
        "age": int(player.age or 25),
        "previous_injury_count": int(player.injuries.count()),
        "position": str(player.position or "Unknown"),
        "injury_type": str(latest_injury.injury_type if latest_injury else "Other"),
        "is_recurring": int(1 if latest_injury and latest_injury.recurrence_flag else 0),
    }


def _predict_with_user_model(features, _horizon):
    needed = ["age", "previous_injury_count", "position", "injury_type"]
    for k in needed:
        if features.get(k) in (None, ""):
            raise NotImplementedError(f"Missing feature for prediction_service: {k}")

    payload = {
        "age": int(features["age"]),
        "position": str(features["position"]),
        "previous_injuries": int(features["previous_injury_count"]),
        "injuries_last_2_seasons": int(features["previous_injury_count"]),
        "primary_zone": str(features["injury_type"]),
        "training_load_band": "medium",
        "days_since_last_intense": 2,
        "recurrence_same_zone": bool(int(features.get("is_recurring", 0) or 0)),
        "fatigue_value": 5.0,
        "stress_value": 5.0,
        "weekly_load_value": 300.0,
        "problems": str(features["injury_type"]),
    }
    result = prediction_service.risk.predict(payload)
    if not result.get("success"):
        raise NotImplementedError(result.get("message", "Risk model not ready"))

    p_long = float(result.get("raw_probability", result.get("risk_index", 0) / 100.0))
    model_version = "prediction_service_risk"
    return {
        "risk_probability": p_long,
        "predicted_class": result.get("risk_band", "medium"),
        "class_probabilities": {"short": round(1.0 - p_long, 6), "long": round(p_long, 6)},
        "top_factors": [
            {"feature": d, "value": 0.0}
            for d in result.get("key_risk_drivers", [])
        ],
        "model_version": model_version,
    }


def _run_prediction(request, features, horizon_days, player=None, persist=False):
    schema = _load_feature_schema()
    normalized, errors = _validate_and_normalize_features(features, schema)
    if errors:
        return None, Response({"detail": "Invalid features", "errors": errors, "feature_schema": schema}, status=400)

    try:
        raw = _predict_with_user_model(normalized, horizon_days)
    except NotImplementedError as ex:
        return None, Response(
            {
                "detail": str(ex),
                "integration": _model_bundle_status(),
                "feature_schema": schema,
            },
            status=503,
        )
    except Exception as ex:
        return None, Response({"detail": f"Inference error: {ex}"}, status=500)

    probability = raw.get("risk_probability")
    if probability is None:
        return None, Response({"detail": "Model response missing risk_probability"}, status=500)

    payload = _base_prediction_payload(probability, model_version=raw.get("model_version", "external-model"))
    payload.update(
        {
            "horizon_days": horizon_days,
            "class_probabilities": raw.get("class_probabilities", {}),
            "predicted_class": raw.get("predicted_class"),
            "features_snapshot": normalized,
            "shap_factors": raw.get("top_factors", []),
        }
    )

    if player is not None:
        payload["player_id"] = player.id
        payload["player_name"] = player.full_name

    if persist and player is not None:
        rec = InjuryRiskPrediction.objects.create(
            player=player,
            horizon_days=horizon_days,
            risk_probability=payload["risk_probability"],
            risk_band=payload["risk_band"] if payload["risk_band"] in ("low", "medium", "high") else "low",
            confidence_band=payload["confidence_band"],
            shap_factors=payload["shap_factors"],
            recommended_action=payload["recommended_action"],
            monitoring_note=payload["monitoring_note"],
            flag_for_physio_review=payload["flag_for_physio_review"],
            sufficient_history=payload["sufficient_history"],
            data_quality_score=payload["data_quality_score"],
            top_factor=payload["top_factor"],
            model_version=payload["model_version"],
        )
        _audit(request, "prediction_requested", "player", player.id, {"prediction_id": rec.id, "horizon": horizon_days})

    return payload, None


class InjuryListCreateView(generics.ListCreateAPIView):
    queryset = Injury.objects.select_related("player").all().order_by("-date")
    serializer_class = InjurySerializer
    permission_classes = [IsPhysioReadOnly]

    def perform_create(self, serializer):
        obj = serializer.save()
        _audit(self.request, "injury_created", "injury", obj.id, {"player_id": obj.player_id})


class InjuryDetailView(generics.RetrieveDestroyAPIView):
    queryset = Injury.objects.select_related("player").all()
    serializer_class = InjurySerializer
    permission_classes = [IsPhysioReadOnly]

    def perform_destroy(self, instance):
        _audit(self.request, "injury_deleted", "injury", instance.id, {"player_id": instance.player_id})
        instance.delete()


class TrainingLoadListCreateView(generics.ListCreateAPIView):
    queryset = TrainingLoad.objects.select_related("player").all().order_by("-date")
    serializer_class = TrainingLoadSerializer
    permission_classes = [IsPhysioReadOnly]

    def perform_create(self, serializer):
        obj = serializer.save()
        _audit(self.request, "load_created", "training_load", obj.id, {"player_id": obj.player_id})


class TrainingLoadDetailView(generics.RetrieveDestroyAPIView):
    queryset = TrainingLoad.objects.select_related("player").all()
    serializer_class = TrainingLoadSerializer
    permission_classes = [IsPhysioReadOnly]

    def perform_destroy(self, instance):
        _audit(self.request, "load_deleted", "training_load", instance.id, {"player_id": instance.player_id})
        instance.delete()


class QuickWellnessView(views.APIView):
    permission_classes = [IsAdminOrPhysio]

    def post(self, request):
        player_id = request.data.get("player")
        if not player_id:
            return Response({"detail": "player is required"}, status=400)

        try:
            player = Player.objects.get(id=player_id)
        except Player.DoesNotExist:
            return Response({"detail": "Player not found"}, status=404)

        log_date = request.data.get("date") or timezone.now().date()
        load, _ = TrainingLoad.objects.get_or_create(
            player=player,
            date=log_date,
            defaults={
                "total_distance_km": 0.0,
                "sprints": 0,
                "accelerations": 0,
                "minutes_played": 0,
            },
        )

        for fld in ["sleep_quality", "soreness", "readiness", "rpe"]:
            if request.data.get(fld) is not None:
                setattr(load, fld, request.data.get(fld))
        load.save()

        _audit(request, "load_created", "training_load", load.id, {"quick_wellness": True, "player_id": player.id})
        return Response({"status": "ok", "training_load_id": load.id})


class InjuryRiskView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request, player_id):
        try:
            player = Player.objects.get(id=player_id)
        except Player.DoesNotExist:
            return Response({"detail": "Player not found"}, status=404)

        bundle = _model_bundle_status()
        if not bundle["configured"]:
            return _integration_error_response()

        features = _extract_features_from_latest_load(player)
        if not features:
            return Response({"detail": "No training load found for player."}, status=400)

        horizon = int(request.query_params.get("horizon", 7))
        payload, error = _run_prediction(request, features, horizon, player=player, persist=True)
        if error:
            return error
        return Response(payload)


class InjuriesSummaryView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        total = Injury.objects.count()
        last_30d = Injury.objects.filter(date__gte=timezone.now().date() - timedelta(days=30)).count()
        by_severity = {
            "mild": Injury.objects.filter(severity="mild").count(),
            "moderate": Injury.objects.filter(severity="moderate").count(),
            "severe": Injury.objects.filter(severity="severe").count(),
        }
        return Response({"total": total, "last_30d": last_30d, "by_severity": by_severity})


class RiskPredictView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def post(self, request):
        bundle = _model_bundle_status()
        if not bundle["configured"]:
            return _integration_error_response()

        horizon = int(request.data.get("horizon_days") or request.data.get("horizon") or 7)
        player = None
        features = request.data.get("features")

        if features is None:
            player_id = request.data.get("player_id")
            if not player_id:
                return Response(
                    {"detail": "Provide either features object or player_id."},
                    status=400,
                )
            try:
                player = Player.objects.get(id=player_id)
            except Player.DoesNotExist:
                return Response({"detail": "Player not found"}, status=404)
            features = _extract_features_from_latest_load(player)
            if not features:
                return Response({"detail": "No training load found for player."}, status=400)

        payload, error = _run_prediction(request, features, horizon, player=player, persist=False)
        if error:
            return error

        _audit(request, "prediction_requested", "risk_predict", None, {"horizon": horizon, "player_id": getattr(player, "id", None)})
        return Response(payload)


class DurationPredictView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request, injury_id):
        return Response(
            {
                "detail": "Duration model is not configured. Plug in your own model implementation.",
                "integration": _model_bundle_status(),
            },
            status=503,
        )


class SquadOverviewTodayView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        players = Player.objects.all().order_by("full_name")
        rows = []
        high = 0
        medium = 0
        spikes = 0
        recent_inj = 0
        recent_cutoff = timezone.now().date() - timedelta(days=28)

        for p in players:
            pred = p.risk_predictions.order_by("-predicted_at").first()
            latest_load = p.training_loads.order_by("-date").first()
            risk_band = pred.risk_band if pred else "unknown"
            risk_prob = pred.risk_probability if pred else None
            risk_pct = round(risk_prob * 100.0, 2) if risk_prob is not None else None
            top_factor = pred.top_factor if pred else ""

            if risk_band == "high":
                high += 1
            elif risk_band == "medium":
                medium += 1

            if p.injuries.filter(date__gte=recent_cutoff).exists():
                recent_inj += 1

            rows.append(
                {
                    "player_id": p.id,
                    "player_name": p.full_name,
                    "position": p.position,
                    "risk_band": risk_band,
                    "risk_probability": risk_prob,
                    "risk_pct": risk_pct,
                    "top_factor": top_factor,
                    "flag_for_physio_review": bool(pred.flag_for_physio_review) if pred else False,
                    "load_spike": False,
                    "latest_training_date": latest_load.date.isoformat() if latest_load else None,
                }
            )

        return Response(
            {
                "player_count": len(rows),
                "high_risk_count": high,
                "medium_risk_count": medium,
                "load_spike_count": spikes,
                "recently_injured_count": recent_inj,
                "squad": rows,
            }
        )


class FlaggedPlayersView(views.APIView):
    permission_classes = [IsAdminOrPhysio]

    def get(self, request):
        latest = InjuryRiskPrediction.objects.filter(flag_for_physio_review=True).order_by("player_id", "-predicted_at")
        seen = set()
        rows = []

        for p in latest:
            if p.player_id in seen:
                continue
            seen.add(p.player_id)
            unresolved = not FlagAcknowledgment.objects.filter(player_id=p.player_id, is_resolved=True).exists()
            if not unresolved:
                continue
            rows.append(
                {
                    "player_id": p.player_id,
                    "player_name": p.player.full_name,
                    "risk_band": p.risk_band,
                    "risk_probability": p.risk_probability,
                    "risk_pct": round(p.risk_probability * 100.0, 2),
                    "top_factor": p.top_factor,
                    "predicted_at": p.predicted_at,
                }
            )

        return Response({"players": rows, "count": len(rows)})


class AcknowledgeFlagView(views.APIView):
    permission_classes = [IsAdminOrPhysio]

    def post(self, request, player_id):
        try:
            player = Player.objects.get(id=player_id)
        except Player.DoesNotExist:
            return Response({"detail": "Player not found"}, status=404)

        note = request.data.get("note", "")
        ack = FlagAcknowledgment.objects.create(
            player=player,
            acknowledged_by=request.user if request.user.is_authenticated else None,
            acknowledged_at=timezone.now(),
            note=note,
            is_resolved=True,
        )
        _audit(request, "flag_acknowledged", "player", player_id, {"ack_id": ack.id, "note": note})
        return Response({"status": "acknowledged", "player_id": player_id})


class ReturningPlayersView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        today = timezone.now().date()
        horizon = today + timedelta(days=14)
        rows = []

        for inj in Injury.objects.select_related("player").all().order_by("-date"):
            expected = inj.date + timedelta(days=inj.days_absent)
            if today <= expected <= horizon:
                rows.append(
                    {
                        "player_id": inj.player_id,
                        "player_name": inj.player.full_name,
                        "injury_type": inj.injury_type,
                        "severity": inj.severity,
                        "expected_return": expected,
                        "days_remaining": (expected - today).days,
                        "recurrence_flag": inj.recurrence_flag,
                    }
                )

        return Response({"returning_count": len(rows), "players": rows})


class PredictionHistoryView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request, player_id):
        limit = int(request.query_params.get("limit", 15))
        rows = InjuryRiskPrediction.objects.filter(player_id=player_id).order_by("-predicted_at")[:limit]
        data = [
            {
                "id": r.id,
                "predicted_at": r.predicted_at,
                "horizon_days": r.horizon_days,
                "risk_probability": r.risk_probability,
                "risk_band": r.risk_band,
                "confidence_band": r.confidence_band,
                "top_factor": r.top_factor,
                "model_version": r.model_version,
            }
            for r in rows
        ]
        return Response({"player_id": player_id, "history": data})


class ModelMetadataView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        metadata = {}
        manifest = MODEL_BUNDLE_DIR / "manifest.json"
        if manifest.exists():
            try:
                metadata = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                metadata = {"manifest_error": "Invalid JSON"}

        return Response(
            {
                "status": _model_bundle_status(),
                "feature_schema": _load_feature_schema(),
                "output_contract": {
                    "risk_probability": "float (0..1)",
                    "predicted_class": "string",
                    "class_probabilities": "object: label -> float",
                    "top_factors": "array[{feature:string, value:number}]",
                    "model_version": "string",
                },
                "manifest": metadata,
            }
        )


class ModelPerformanceView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        risk_schema = getattr(prediction_service.risk_loader, "schema", {}) or {}
        absence_schema = getattr(prediction_service.absence_loader, "schema", {}) or {}
        ready = bool(getattr(prediction_service, "ready_state", False))
        features = list(getattr(prediction_service.risk_loader, "feature_order", []) or [])
        error = None
        if not ready:
            error = (
                getattr(prediction_service.risk_loader, "last_error", None)
                or getattr(prediction_service.absence_loader, "last_error", None)
            )

        return Response(
            {
                "auroc": risk_schema.get("roc_auc"),
                "cv_auc": risk_schema.get("cv_auc_mean"),
                "pr_auc": risk_schema.get("pr_auc"),
                "brier": risk_schema.get("brier"),
                "recall_top5": risk_schema.get("recall_top5"),
                "model_name": "CatBoost (risk + absence)",
                "model_version": risk_schema.get("version") or absence_schema.get("version") or "prediction_service_v2",
                "dataset_rows": risk_schema.get("dataset_rows") or absence_schema.get("dataset_rows"),
                "ready": ready,
                "features": features,
                "error": error,
            }
        )


class AuditLogListView(views.APIView):
    permission_classes = [IsAdminOnly]

    def get(self, request):
        limit = int(request.query_params.get("limit", 100))
        rows = AuditLog.objects.select_related("user").all()[:limit]
        data = [
            {
                "id": r.id,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "detail": r.detail,
                "ip_address": r.ip_address,
                "created_at": r.created_at,
                "user": r.user.username if r.user else None,
            }
            for r in rows
        ]
        return Response({"count": len(data), "results": data})


class InjuryCSVImportView(views.APIView):
    permission_classes = [IsAdminOnly]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"detail": "CSV file is required under key 'file'."}, status=400)

        reader = csv.DictReader(io.StringIO(file_obj.read().decode("utf-8")))
        created = 0
        errors = []
        for row in reader:
            try:
                player_id = int(row.get("player") or row.get("player_id"))
                Injury.objects.create(
                    player_id=player_id,
                    injury_type=row.get("injury_type", "unknown"),
                    date=row.get("date"),
                    severity=row.get("severity") or "mild",
                    days_absent=int(row.get("days_absent") or 0),
                    matches_missed=int(row.get("matches_missed") or 0),
                    recurrence_flag=str(row.get("recurrence_flag", "false")).lower() == "true",
                )
                created += 1
            except Exception as ex:
                errors.append(str(ex))

        _audit(request, "csv_import", "injury", None, {"created": created, "errors": len(errors)})
        return Response({"created": created, "errors": errors[:20]})


class LoadCSVImportView(views.APIView):
    permission_classes = [IsAdminOnly]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"detail": "CSV file is required under key 'file'."}, status=400)

        reader = csv.DictReader(io.StringIO(file_obj.read().decode("utf-8")))
        created = 0
        errors = []
        for row in reader:
            try:
                player_id = int(row.get("player") or row.get("player_id"))
                TrainingLoad.objects.create(
                    player_id=player_id,
                    date=row.get("date"),
                    total_distance_km=float(row.get("total_distance_km") or 0),
                    sprints=int(row.get("sprints") or 0),
                    accelerations=int(row.get("accelerations") or 0),
                    rpe=float(row.get("rpe")) if row.get("rpe") not in (None, "") else None,
                    sleep_quality=float(row.get("sleep_quality")) if row.get("sleep_quality") not in (None, "") else None,
                    soreness=float(row.get("soreness")) if row.get("soreness") not in (None, "") else None,
                    readiness=float(row.get("readiness")) if row.get("readiness") not in (None, "") else None,
                    minutes_played=int(row.get("minutes_played") or 0),
                )
                created += 1
            except Exception as ex:
                errors.append(str(ex))

        _audit(request, "csv_import", "training_load", None, {"created": created, "errors": len(errors)})
        return Response({"created": created, "errors": errors[:20]})


class PhysioSimulationView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def post(self, request):
        _audit(request, "simulation_run", "simulation", None, {"requested": True})
        return Response(
            {
                "detail": "Simulator is disabled until your custom model adapter is plugged in.",
                "integration": _model_bundle_status(),
                "feature_schema": _load_feature_schema(),
            },
            status=503,
        )


class GlobalSummaryView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        return Response(
            {
                "players": GlobalPlayer.objects.count(),
                "daily_records": GlobalDailyRecord.objects.count(),
                "injury_events": GlobalInjuryEvent.objects.count(),
                "model_7d": {
                    "status": "not_configured",
                    "test_metrics": {
                        "auroc": None,
                        "pr_auc": None,
                        "brier": None,
                        "recall_top5": None,
                    },
                },
            }
        )


class GlobalPlayersView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        rows = GlobalPlayer.objects.all().order_by("team", "external_id")
        return Response([{"id": p.id, "external_id": p.external_id, "team": p.team} for p in rows])


class GlobalMetricsView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        metrics = {
            "players": GlobalPlayer.objects.count(),
            "daily_records": GlobalDailyRecord.objects.count(),
            "injury_events": GlobalInjuryEvent.objects.count(),
            "last_record_date": GlobalDailyRecord.objects.order_by("-date").values_list("date", flat=True).first(),
        }
        return Response(metrics)


class GlobalRiskView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request, player_id):
        return _integration_error_response()


class GlobalSHAPView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request, player_id):
        return _integration_error_response()


class GlobalTimeSeriesView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request, player_id):
        metrics_raw = request.query_params.get("metrics", "acwr,daily_load,soreness,readiness")
        metrics = [m.strip() for m in metrics_raw.split(",") if m.strip()]
        limit = int(request.query_params.get("limit", 120))

        qs = GlobalDailyRecord.objects.filter(player_id=player_id).order_by("-date")[:limit]
        recs = list(reversed(list(qs)))
        injuries = set(
            GlobalInjuryEvent.objects.filter(player_id=player_id).values_list("injury_start", flat=True)
        )

        series = []
        for r in recs:
            row = {"date": r.date.isoformat(), "injury": r.date in injuries}
            for m in metrics:
                row[m] = getattr(r, m, None)
            series.append(row)

        return Response({"player_id": player_id, "series": series, "metrics": metrics})


class GlobalSquadOverviewView(views.APIView):
    permission_classes = [IsCoachOrAbove]

    def get(self, request):
        rows = []
        for p in GlobalPlayer.objects.all().order_by("team", "external_id"):
            rows.append(
                {
                    "player_id": p.id,
                    "external_id": p.external_id,
                    "team": p.team,
                    "risk_band": "unknown",
                    "risk_pct": None,
                    "risk_probability": None,
                    "top_factor": "",
                    "flag_for_physio_review": False,
                }
            )

        return Response(
            {
                "player_count": len(rows),
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "squad": rows,
                "model_version": "not_configured",
            }
        )

