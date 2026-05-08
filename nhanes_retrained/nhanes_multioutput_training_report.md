# NHANES Multi-Output Diabetes Model Training

## Summary

This run retrained two separate model artifacts using `nhanes/nhanes_diabetes_pregnancy_training.csv`.
The models predict three binary outputs:

- `diabetes_label`: 0=normal/no diabetes, 1=diabetes
- `cardiovascular_complication`: 0=no cardiovascular complication history, 1=heart failure/coronary heart disease/angina/heart attack history
- `stroke_complication`: 0=no stroke history, 1=stroke history

## Data

- Source training file: `nhanes/nhanes_diabetes_pregnancy_training.csv`
- Rows used: `7956`
- Feature count: `34`
- Train rows for validation: `6364`
- Test rows for validation: `1592`

Target distribution:

- `diabetes_label`: 0=6248, 1=1708
- `cardiovascular_complication`: 0=7204, 1=752
- `stroke_complication`: 0=7544, 1=412

## Feature Columns

```text
sex
age_years
race_ethnicity
race_ethnicity_asian
INDFMPIR
is_currently_pregnant
ever_pregnant
self_report_current_pregnancy
number_pregnancies
gestational_diabetes_history
number_deliveries
number_live_birth_deliveries
had_baby_9lb_or_more
weight_kg
height_cm
bmi
waist_cm
hip_cm
hba1c_percent
fasting_glucose_mg_dl
fasting_glucose_mmol_l
insulin_uU_ml
insulin_pmol_l
fasting_hours
fasting_minutes
total_cholesterol_mg_dl
total_cholesterol_mmol_l
high_blood_pressure_history
high_bp_twice_or_more
taking_bp_prescription
now_taking_bp_prescription
systolic_bp_mean
diastolic_bp_mean
pulse_mean
```

## Algorithms Evaluated

Each repo variant evaluated three algorithms. XGBoost was included in both sets as required.

- `dunghoang`: XGBoost, Random Forest, Extra Trees.
- `tiennguyen`: XGBoost, Random Forest, Logistic Regression with StandardScaler.

The selected artifact for each repo is the model with the highest average macro-F1 across the three targets. Average ROC-AUC is used only as a tie-breaker.

## Results

### dunghoang

| Algorithm | Avg macro-F1 | Avg ROC-AUC | Exact-match accuracy | Selected |
|---|---:|---:|---:|---|
| extra_trees | 0.6978 | 0.8722 | 0.7833 | yes |
| random_forest | 0.6621 | 0.8690 | 0.8317 |  |
| xgboost | 0.6468 | 0.8767 | 0.8411 |  |

| Target | F1 macro | Accuracy | ROC-AUC |
|---|---:|---:|---:|
| diabetes_label | 0.8944 | 0.9278 | 0.9686 |
| cardiovascular_complication | 0.6605 | 0.8675 | 0.8465 |
| stroke_complication | 0.5385 | 0.9309 | 0.8016 |

### tiennguyen

| Algorithm | Avg macro-F1 | Avg ROC-AUC | Exact-match accuracy | Selected |
|---|---:|---:|---:|---|
| logistic_regression | 0.6598 | 0.8737 | 0.6005 | yes |
| random_forest | 0.6537 | 0.8665 | 0.8392 |  |
| xgboost | 0.6468 | 0.8767 | 0.8411 |  |

| Target | F1 macro | Accuracy | ROC-AUC |
|---|---:|---:|---:|
| diabetes_label | 0.8676 | 0.9026 | 0.9658 |
| cardiovascular_complication | 0.6009 | 0.7368 | 0.8447 |
| stroke_complication | 0.5109 | 0.6928 | 0.8105 |

## Saved Artifacts

Because Windows cannot store two files with the exact same name in one directory, the two model files were named by source repo:

- `dunghoang`: `trained_models/nhanes_retrained/dunghoang_model.pkl`
- `tiennguyen`: `trained_models/nhanes_retrained/tiennguyen_model.pkl`

Each artifact is a scikit-learn `Pipeline` saved with `joblib`. It has these extra attributes:

- `feature_columns_`
- `target_columns_`
- `target_labels_`
- `selected_algorithm_`
- `validation_metrics_`

Prediction output order is:

```text
diabetes_label
cardiovascular_complication
stroke_complication
```

