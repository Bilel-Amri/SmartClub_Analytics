import json
import logging
from pathlib import Path
import joblib
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def _resolve_artifacts_dir() -> Path:
    return Path(__file__).resolve().parent / "model_bundle"

BASE = _resolve_artifacts_dir()

class PredictionBundleLoader:
    """Handles schema-safe loading of models and schemas with strict health checking."""
    def __init__(self, prefix: str):
        self.prefix = prefix
        self.model = None
        self.schema = {}
        self.ready_state = False
        self.last_error = None

    def load(self, schema_filename: str, model_filename: str):
        schema_path = BASE / schema_filename
        model_path = BASE / model_filename

        logger.info(f"[PhysioAI] Initializing {self.prefix} bundle...")
        print(f"[PhysioAI] Initializing {self.prefix} bundle...")
        
        if not schema_path.exists():
            self.last_error = f"Schema file not found: {schema_filename}"
            logger.error(f"[PhysioAI] {self.last_error}")
            print(f"[PhysioAI] {self.last_error}")
            return
            
        if not model_path.exists():
            self.last_error = f"Model file not found: {model_filename}"
            logger.error(f"[PhysioAI] {self.last_error}")
            print(f"[PhysioAI] {self.last_error}")
            return

        try:
            with open(schema_path, encoding="utf-8") as f:
                self.schema = json.load(f)
            
            bundle = joblib.load(model_path)
            
            if isinstance(bundle, dict):
                self.model = bundle.get('model', bundle)
                self.problem_mapping = bundle.get('problem_mapping', {})
                self.training_features = bundle.get('training_features', [])
                self.original_feature_order = bundle.get('original_feature_order', [])
                
                if self.prefix == "Risk":
                    print(f"[PhysioAI] {self.prefix} bundle loaded.")
                    print(f"[PhysioAI] Risk model class: {type(self.model).__name__}")
                    print(f"[PhysioAI] Bundle keys found: {list(bundle.keys())}")
                    print(f"[PhysioAI] training_features count: {len(self.training_features)}")
                    print(f"[PhysioAI] original_feature_order count: {len(self.original_feature_order)}")
                    print(f"[PhysioAI] problem_mapping count: {len(self.problem_mapping)}")
                elif self.prefix == "Absence":
                    print(f"[PhysioAI] Absence model class: {type(self.model).__name__}")
            else:
                self.model = bundle
                self.problem_mapping = {}
                self.training_features = []
                self.original_feature_order = []
            
            # Identify fields
            self.feature_order = self.schema.get("features", self.schema.get("input_features_ordered", []))
            self.categorical = self.schema.get("categorical_columns", ["problems"] if self.prefix == "Risk" else [])
            
            if "raw_required_columns_before_feature_engineering" in self.schema:
                self.required = self.schema["raw_required_columns_before_feature_engineering"]
                self.required_source = "schema"
                req_source = "Parsed exactly from schema contract"
            else:
                self.required_source = "hardcoded_fallback"
                req_source = "Hardcoded fallback (Limitation: Schema lacks requirements list)"
                if self.prefix == "Risk":
                    # Relaxed requirements for the frontend form to pass through smoothly
                    self.required = ["fatigue_value", "stress_value", "weekly_load_value"]
                else:
                    self.required = ["injury_type", "age"]

            print(f"\n[PhysioAI] ---- {self.prefix} Model Schema Contract ----")
            print(f"[PhysioAI] Required Fields Source: {req_source}")
            print(f"[PhysioAI] Required Fields: {self.required}")
            print(f"[PhysioAI] Categorical Fields: {self.categorical}")
            print(f"[PhysioAI] Feature Order ({len(self.feature_order)}): {self.feature_order}\n")
            
            self.ready_state = True
            logger.info(f"[PhysioAI] {self.prefix} model ready for inference.")
        except Exception as ex:
            self.last_error = str(ex)
            logger.error(f"[PhysioAI] Bundle validation failed for {self.prefix}: {ex}")
            print(f"[PhysioAI] Bundle validation failed for {self.prefix}: {ex}")

class RiskPredictionService:
    def __init__(self, loader: PredictionBundleLoader):
        self.loader = loader

    def predict(self, payload: dict) -> dict:
        if not self.loader.ready_state or self.loader.model is None:
            return {
                "success": False,
                "error_code": "MODEL_NOT_READY",
                "message": f"Risk model not ready: {self.loader.last_error}",
                "model_status": "error"
            }
        
        # Check required fields strictly
        required = self.loader.required
        missing_required = []
        for req in required:
            # allow aliases like _value 
            if req not in payload and f"{req}_value" not in payload:
                # exceptional case logic if needed
                if req == "sleepDetails" and "sleep_duration_value" in payload:
                    continue
                missing_required.append(req)
                
        if missing_required:
            return {
                "success": False,
                "error_code": "MISSING_REQUIRED_FIELDS",
                "message": "Required fields are missing for Risk inference.",
                "missing_fields": missing_required,
                "model_status": "loaded"
            }

        feature_order = self.loader.original_feature_order if self.loader.original_feature_order else self.loader.feature_order
        missing_fields = []
        applied_defaults = {}
        input_data = {}
        
        # Explicitly define fallback behavior for optional fields
        optional_defaults = {
            "team_performance": 5.0,
            "offensive_performance": 5.0,
            "defensive_performance": 5.0,
            "ctl28_value": 50.0,
            "ctl42_value": 50.0,
            "atl_value": 50.0,
            "acwr_value": 1.0,
            "monotony_value": 1.0,
            "strain_value": 300.0,
            "daily_load_value": 300.0,
            "weekly_load_value": 300.0,
            "readiness_value": 5.0,
            "soreness_value": 5.0,
            "stress_value": 5.0,
            "sleep_quality_value": 5.0,
            "sleep_duration_value": 8.0,
            "mood_value": 5.0,
            "fatigue_value": 5.0,
            "problems": "Unknown"
        }
        
        # Explicit frontend-to-schema mapping dictionary for Risk
        frontend_to_schema_mapping = {
            "sleepHours": "sleep_duration_value",
            "ctl28_value": "ctl28_value",
            "mood_value": "mood_value",
            "readiness_value": "readiness_value",
            "atl_value": "atl_value",
            "acwr_value": "acwr_value",
            "strain_value": "strain_value",
            "soreness_value": "soreness_value",
            "stress_value": "stress_value",
            "sleep_quality_value": "sleep_quality_value",
            "team_performance": "team_performance",
            "offensive_performance": "offensive_performance",
            "defensive_performance": "defensive_performance",
            "fatigue_value": "fatigue_value",
            "problems": "problems",
            "weekly_load_value": "weekly_load_value",
            "ctl42_value": "ctl42_value",
            "monotony_value": "monotony_value",
            "daily_load_value": "daily_load_value"
        }

        for feat in feature_order:
            val = None
            
            # Find frontend keys that map to this schema feature
            mapped_frontend_keys = [k for k, v in frontend_to_schema_mapping.items() if v == feat]
            if feat not in mapped_frontend_keys:
                mapped_frontend_keys.append(feat)

            for key in mapped_frontend_keys:
                if key in payload:
                    val = payload[key]
                    break
                elif f"{key}_value" in payload:
                    val = payload[f"{key}_value"]
                    break
                
            if val is not None:
                input_data[feat] = val
            else:
                missing_fields.append(feat)
                # Apply explicit safe default
                default_val = optional_defaults.get(feat, "Unknown" if feat in self.loader.categorical else 0.0)
                input_data[feat] = default_val
                applied_defaults[feat] = default_val

        # Encode 'problems' using the bundle's problem_mapping
        if self.loader.problem_mapping:
            input_problems = str(input_data.get("problems", "Unknown"))
            encoded_val = self.loader.problem_mapping.get(input_problems, -1)
            input_data["problems"] = encoded_val

        # Build final dataframe using training_features
        if self.loader.training_features:
            final_input = {f: input_data.get(f, 0.0) for f in self.loader.training_features}
            df_input = pd.DataFrame([final_input])
        else:
            df_input = pd.DataFrame([input_data])

        prob = float(self.loader.model.predict_proba(df_input)[0][1])

        from physio.vulnerability_formula import compute_vulnerability_score
        base_scores = compute_vulnerability_score(**payload)
        
        ml_weight = 0.4
        raw_prob_scaled = int(prob * 100)
        blended_score = max(0, min(100, int((base_scores["risk_score"] * (1 - ml_weight)) + (raw_prob_scaled * ml_weight))))
        
        if blended_score < 35:
            band = "low"
        elif blended_score < 60:
            band = "medium"
        else:
            band = "high"

        top_drivers = base_scores.get("top_drivers", [])
        if "fatigue_value" in payload and float(payload["fatigue_value"]) > 7:
            top_drivers.insert(0, {"label": "High current fatigue reported", "points": 15})
        if "stress_value" in payload and float(payload["stress_value"]) > 7:
            top_drivers.insert(0, {"label": "High current stress reported", "points": 12})
            
        driver_strings = [d["label"] if isinstance(d, dict) else d for d in top_drivers[:4]]

        training_decision = {
            "load": "reduce max-speed and acceleration" if band == "high" else "keep controlled progression",
            "session": "technical phases only" if band != "low" else "normal plan",
            "escalation": "Stop if hamstring discomfort reported"
        }

        # Log completion
        log_msg = f"Risk Prediction -> req_source: {self.loader.required_source}, missing: {len(missing_fields)}, defaults: {len(applied_defaults)}"
        logger.info(log_msg)
        print(f"[PhysioAI] {log_msg}")

        return {
            "success": True,
            "raw_probability": float(f"{prob:.4f}"),      # True model output
            "risk_index": blended_score,                  # Hybrid display score
            "risk_score": blended_score,                  # Alias for frontend compatibility (Hybrid display score)
            "risk_band": band,
            "key_risk_drivers": driver_strings,
            "risk_drivers": driver_strings,
            "decision": training_decision,
            "training_decision": training_decision,
            "similar_profiles": [], # Placeholder for historical case matching
            "explanation": f"Hybrid model assessment places player in {band} risk category. Raw model prob: {prob:.2%} | Formula base score: {base_scores['risk_score']}.",
            "required_fields_source": self.loader.required_source,
            "missing_fields": missing_fields,
            "applied_defaults": applied_defaults,
            "input_quality_status": "complete" if not missing_fields else "partial",
            "model_status": "loaded",
            "metadata_labels": {
                "raw_probability": "ML-based",
                "risk_index": "hybrid",
                "risk_score": "hybrid",
                "risk_band": "hybrid",
                "key_risk_drivers": "rule-based",
                "risk_drivers": "rule-based",
                "decision": "rule-based",
                "training_decision": "rule-based",
                "similar_profiles": "empty/not implemented"
            }
        }

class AbsencePredictionService:
    def __init__(self, loader: PredictionBundleLoader):
        self.loader = loader

    def predict(self, payload: dict) -> dict:
        if not self.loader.ready_state or self.loader.model is None:
            return {
                "success": False,
                "error_code": "MODEL_NOT_READY",
                "message": f"Absence model not ready: {self.loader.last_error}",
                "model_status": "error"
            }
        
        # Check required fields strictly
        required = self.loader.required
        missing_required = []
        for req in required:
            # Map legacy raw requirements internally
            check_key = req
            if req == "injury": check_key = "injury_type"
            elif req == "injury_from_parsed": check_key = "injury_type"
            elif req == "player_name": continue # Ignore string names not required
            elif req == "player_age": check_key = "age"
            elif req == "player_position": check_key = "position"
            elif req in ["season", "club", "league"]: continue # These are context/config, auto-filled below
            
            if check_key not in payload and req not in payload:
                missing_required.append(check_key)
                
        # Deduplicate missing required
        missing_required = list(set(missing_required))

        if missing_required:
            return {
                "success": False,
                "error_code": "MISSING_REQUIRED_FIELDS",
                "message": f"Required fields are missing for Absence inference: {', '.join(missing_required)}",
                "missing_fields": missing_required,
                "model_status": "loaded"
            }

        features_ordered = self.loader.feature_order
        categorical_cols = set(self.loader.categorical)
        
        inj_group_str = str(payload.get("injury_group", payload.get("injury_type", "Unknown"))).lower()
        injury_group_final = payload.get("injury_type", "Unknown")
        if any(x in inj_group_str for x in ["muscle", "strain", "hamstring"]):
            injury_group_final = "Muscle_Soft_Tissue"
        elif any(x in inj_group_str for x in ["knee", "ligament"]):
            injury_group_final = "Knee_Ligament"
        elif any(x in inj_group_str for x in ["illness", "virus"]):
            injury_group_final = "Illness_Virus"
        elif any(x in inj_group_str for x in ["ankle", "foot"]):
            injury_group_final = "Ankle_Foot"
        elif any(x in inj_group_str for x in ["impact", "contusion"]):
            injury_group_final = "Impact_General"

        payload["injury_group"] = injury_group_final
        payload["is_muscle_injury"] = 1 if injury_group_final == "Muscle_Soft_Tissue" else 0
        payload["is_knee_injury"] = 1 if injury_group_final == "Knee_Ligament" else 0
        payload["is_illness"] = 1 if injury_group_final == "Illness_Virus" else 0
        payload["is_ankle_foot"] = 1 if injury_group_final == "Ankle_Foot" else 0
        payload["is_impact_general"] = 1 if injury_group_final == "Impact_General" else 0
        payload["player_age"] = payload.get("age", payload.get("player_age", 25))
        payload["player_position"] = payload.get("position", payload.get("player_position", "Unknown"))
        payload["player_age_missing"] = 0 if payload.get("player_age") else 1
        
        import datetime
        today = datetime.date.today()
        payload["injury_year"] = today.year
        payload["injury_month"] = today.month
        payload["injury_day"] = today.day
        payload["injury_dow"] = today.weekday()
        payload["injury_weekofyear"] = today.isocalendar()[1]
        payload["injury_date_missing"] = 0

        month = payload["injury_month"]
        if 8 <= month <= 11:
            phase = "Early_Season"
        elif 12 <= month <= 2 or month == 1:
            phase = "Mid_Season"
        elif 3 <= month <= 5:
            phase = "Late_Season"
        else:
            phase = "Off_Season"
        payload["season_phase"] = phase
        payload["season"] = str(today.year)
        payload["club"] = payload.get("club", "Unknown") or "Unknown"
        payload["league"] = payload.get("league", "Unknown") or "Unknown"

        # Explicitly define fallback behavior for optional fields
        optional_defaults = {
            "player_age_missing": 0,
            "injury_date_missing": 0,
            "is_muscle_injury": 0,
            "is_knee_injury": 0,
            "is_illness": 0,
            "is_ankle_foot": 0,
            "is_impact_general": 0
        }

        missing_fields = []
        applied_defaults = {}
        input_data = {}
        for feat in features_ordered:
            if feat in payload:
                input_data[feat] = payload[feat]
            else:
                missing_fields.append(feat)
                default_val = optional_defaults.get(feat, "Unknown" if feat in categorical_cols else 0.0)
                input_data[feat] = default_val
                applied_defaults[feat] = default_val

        df_input = pd.DataFrame([{f: input_data[f] for f in features_ordered}])

        raw_pred = float(self.loader.model.predict(df_input)[0])

        if self.loader.schema.get("target_type", "") == "regression_log1p_capped_days" and raw_pred < 6.0:
            raw_pred = np.expm1(raw_pred)

        predicted_days = max(1, int(round(raw_pred)))
        days_cap = self.loader.schema.get("days_cap", 180)
        predicted_days = min(predicted_days, days_cap)

        if predicted_days <= 7:
            severity_bucket = "0_7"
            severity_label = "mild"
            conf = "high"
        elif predicted_days <= 21:
            severity_bucket = "8_21"
            severity_label = "moderate"
            conf = "medium"
        elif predicted_days <= 42:
            severity_bucket = "22_42"
            severity_label = "severe"
            conf = "medium"
        else:
            severity_bucket = "43_plus"
            severity_label = "long-term"
            conf = "low"
            
        days_min = max(1, predicted_days - max(2, int(predicted_days * 0.15)))
        days_max = predicted_days + max(3, int(predicted_days * 0.25))

        rec_actions = {
            "participation": "Out of full training" if severity_label in ["moderate", "severe", "long-term"] else "Modify training",
            "medical": "Confirm diagnosis with physio assessment",
            "coach_notification": "Inform coach of expected absence",
            "escalation": "Reassess in 48 hours"
        }

        # Log completion
        log_msg = f"Absence Prediction -> req_source: {self.loader.required_source}, missing: {len(missing_fields)}, defaults: {len(applied_defaults)}"
        logger.info(log_msg)
        print(f"[PhysioAI] {log_msg}")

        return {
            "success": True,
            "raw_predicted_days": float(f"{raw_pred:.2f}"),
            "predicted_days": predicted_days,
            "predicted_range": f"{days_min}-{days_max} days",
            "severity_bucket": severity_bucket,
            "severity_label": severity_label,
            "confidence": conf,
            "explanation": f"Based on regression model. Raw ML output: {raw_pred:.2f} days. Rules mapped to {severity_label} severity.",
            "recommended_actions": rec_actions,
            "similar_profiles": [], # Placeholder for historical case matching
            "required_fields_source": self.loader.required_source,
            "missing_fields": missing_fields,
            "applied_defaults": applied_defaults,
            "input_quality_status": "complete" if not missing_fields else "partial",
            "model_status": "loaded",
            "metadata_labels": {
                "raw_predicted_days": "ML-based",
                "predicted_days": "hybrid",
                "predicted_range": "rule-based",
                "severity_bucket": "rule-based",
                "severity_label": "rule-based",
                "confidence": "rule-based",
                "recommended_actions": "rule-based",
                "similar_profiles": "empty/not implemented"
            }
        }

class MainPredictionService:
    def __init__(self):
        self.risk_loader = PredictionBundleLoader("Risk")
        self.absence_loader = PredictionBundleLoader("Absence")
        
        self.risk_loader.load("risk_schema.json", "model_risk.pkl")
        self.absence_loader.load("absence_days_schema.json", "model_absence_days.pkl")
        
        self.risk = RiskPredictionService(self.risk_loader)
        self.absence = AbsencePredictionService(self.absence_loader)
        
        self.ready_state = self.risk_loader.ready_state or self.absence_loader.ready_state

prediction_service = MainPredictionService()
 
