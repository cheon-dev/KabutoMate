# Machine Learning Documentation — Mushroom Yield Prediction

> **Project:** KabutoMate Mushroom Farm Dashboard
> **Model documented:** Random Forest yield prediction
> **Notebook:** `mushroom_yield_prediction.ipynb`
> **Backend integration:** `core/yield_model.py`, `core/views.py`, `templates/production.html`
> **Prepared:** November 16, 2026

This document follows the required subsection structure:

| Subsection | Required evidence |
|---|---|
| A. Dataset | One screenshot or table showing the actual dataset |
| B. Feature Selection | A table describing the seven input features |
| C. Data Preparation | One diagram showing the 13 records divided into 10 training and 3 testing samples |
| D. Model Selection | Written explanation of the two algorithms; no image required |
| E. Model Training | One workflow diagram showing the training process |
| F. Model Evaluation | A table explaining MAE, MSE, RMSE, and R²; no result chart yet |
| G. Model Integration | One diagram showing how the trained model connects to the Django backend |

---

## A. Dataset

The dataset is built from harvested mushroom batches stored in the Django database through the `ProductionBatch` model. The notebook queries only records where:

- `status = 'HARVESTED'`
- `yield_kg` is not null
- `harvest_date` is not null
- `start_date` is not null

The 13-record snapshot used in the notebook produced the following sample.

**Table 1. Sample rows from the 13-record harvested-batch dataset**

| # | product_id | start_month | growth_days | cost (₱) | prev_yield_1 (kg) | prev_avg_3 (kg) | farm_avg_5 (kg) | yield_kg |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 11 | 4 | 290.00 | — | — | — | 3.9 |
| 2 | 5 | 11 | 6 | 200.00 | — | — | 3.90 | 3.8 |
| 3 | 5 | 11 | 6 | 180.00 | 3.8 | 3.8 | 3.85 | 3.7 |
| 4 | 1 | 11 | 11 | 200.00 | — | — | 3.80 | 4.0 |
| 5 | 1 | 11 | 11 | 150.00 | 4.0 | 4.0 | 3.85 | 3.0 |

*Table 1. Sample of the 13-record harvested-batch dataset used for yield-model training.*

### Dataset summary

| Property | Value |
|---|---|
| Number of records | 13 harvested batches |
| Number of input features | 7 |
| Target variable | `yield_kg` |
| Yield mean | 3.86 kg |
| Yield standard deviation | 0.33 kg |
| Yield range | 3.0–4.5 kg |
| Product ID range | 1–7 |
| Growth-days range | 1–21 days |
| Cost range | ₱50–₱300 |

### Missing values

The previous-yield features are naturally unavailable for the first harvest of each product. In the 13-record snapshot:

- `same_product_prev_yield_1`: 9 non-null values
- `same_product_prev_avg_3`: 9 non-null values
- `farm_prev_avg_5`: 12 non-null values

These gaps are handled with **median imputation**, fitted on the training set only.

### How to capture the full table

```python
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

print(f"Number of records: {len(data)}")
print(data.to_string(index=False))

# Optional: export for Word/Excel
data.to_csv("yield_dataset_13_records.csv", index=False)
```

Take a screenshot of the notebook output, or paste the exported CSV into Word as a table.

---

## B. Feature Selection

**Table 2. Seven input features used by the yield-prediction models**

| Feature | Type | Description | Reason for inclusion |
|---|---|---|---|
| `product_id` | Categorical / integer | Identifier of the mushroom product | Different products have different yield behaviour |
| `start_month` | Integer (1–12) | Month the batch was started | Captures seasonal and temperature effects |
| `growth_days` | Integer | Days from start date to harvest date | Cycle length can affect yield |
| `cost` | Float (₱) | Production cost of the batch | Proxy for input intensity and production scale |
| `same_product_prev_yield_1` | Float (kg) | Most recent yield of the same product | Short-term product-specific trend |
| `same_product_prev_avg_3` | Float (kg) | Average of the last 3 yields of the same product | Smoothed product-specific history |
| `farm_prev_avg_5` | Float (kg) | Average of the last 5 farm-wide yields | Overall recent farm performance |

**Target variable:** `yield_kg` — harvested mushroom weight in kilograms.

The three rolling-yield features are computed chronologically, so each row uses only information that was available before that harvest. This prevents data leakage.

*Table 2. Seven input features used by the yield-prediction models.*

---

## C. Data Preparation

The 13 records were divided into **10 training samples (80%)** and **3 testing samples (20%)** using `train_test_split(test_size=0.2, random_state=42)`.

![Figure 1. Dataset split for model training and testing](ml_diagrams/figure_1_data_split.png)

*Figure 1. Dataset split used for model training and testing.*

### What happens in each set

| Set | Records | Purpose |
|---|---:|---|
| Training set | 10 | Fit the median imputer and train both regression models |
| Testing set | 3 | Hold-out evaluation only; never used during fitting |

**Key points to state in the paper:**

- Split ratio: **80% training / 20% testing**
- Result: **10 training records, 3 testing records**
- `random_state=42` makes the split reproducible.
- Median imputation is fitted on the training set and then applied to the test set, so no test information leaks into training.

---

## D. Model Selection

Two regression algorithms were trained and compared on the same data.

### D.1 Linear Regression

Linear Regression models the harvested yield as a weighted sum of the seven features:

\[
\hat{y} = \beta_0 + \beta_1 x_1 + \beta_2 x_2 + \dots + \beta_7 x_7
\]

**Role:** baseline model.

**Strengths:**

- Simple and fast to train.
- Coefficients are directly interpretable.
- Shows the direction and strength of each feature's relationship with yield.

**Limitation:**

- Assumes a linear, additive relationship, which may not hold for biological harvest data.

### D.2 Random Forest Regression

Random Forest is an ensemble of decision trees. The notebook uses:

- **100 trees** (`n_estimators=100`)
- **Maximum depth 10** (`max_depth=10`)
- **Random state 42** for reproducibility

Each tree is trained on a bootstrap sample of the training data and considers a random subset of features at each split. The forest averages the trees' predictions.

**Strengths:**

- Captures non-linear relationships and feature interactions.
- Handles mixed feature scales without standardization.
- Provides feature-importance scores.
- More resistant to overfitting than a single decision tree.

**Limitation:**

- Less interpretable than a single linear equation.

### D.3 Why both were trained

The two algorithms were compared to establish a simple baseline and then test whether a more flexible model improves accuracy. Both used the same 10 training records, the same median-imputation strategy, and the same 3 held-out records. The Random Forest produced the lower error and was selected for saving and integration.

*Table 3. Comparison of the two candidate algorithms.*

---

## E. Model Training

![Figure 2. Model-training workflow for mushroom yield prediction](ml_diagrams/figure_2_training_workflow.png)

*Figure 2. Model-training workflow for mushroom yield prediction.*

### Training steps

1. **Query the database.** Load harvested `ProductionBatch` records with valid yield and dates.
2. **Sort chronologically.** Order by harvest date, start date, and ID.
3. **Build historical features.** Compute the previous yield, previous 3-yield average, and previous 5-yield farm average.
4. **Create the feature matrix.** `X` has 13 rows and 7 columns; `y` is `yield_kg`.
5. **Split the data.** 80/20 train–test split with `random_state=42` → 10 training and 3 testing records.
6. **Impute missing values.** Fit `SimpleImputer(strategy="median")` on the training set.
7. **Train Linear Regression.** Fit the baseline model.
8. **Train Random Forest.** Fit 100 trees with `max_depth=10`.
9. **Evaluate both models.** Compute MAE, MSE, RMSE, and R² on the 3 test records.
10. **Save the better model.** The Random Forest is serialized to `mushroom_yield_model.pkl`.

### Training code reference

```python
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np
import pickle

feature_columns = [
    "product_id",
    "start_month",
    "growth_days",
    "cost",
    "same_product_prev_yield_1",
    "same_product_prev_avg_3",
    "farm_prev_avg_5",
]

X = data[feature_columns]
y = data["yield_kg"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

imputer = SimpleImputer(strategy="median")
X_train_imputed = imputer.fit_transform(X_train)
X_test_imputed = imputer.transform(X_test)

lr_model = LinearRegression()
lr_model.fit(X_train_imputed, y_train)

rf_model = RandomForestRegressor(
    n_estimators=100, max_depth=10, random_state=42
)
rf_model.fit(X_train_imputed, y_train)

with open("mushroom_yield_model.pkl", "wb") as file:
    pickle.dump(rf_model, file)
```

---

## F. Model Evaluation

**Table 4. Evaluation metrics used for the yield-prediction models**

| Metric | Formula | What it measures | Unit | Better |
|---|---|---|---|---|
| **MAE** — Mean Absolute Error | \(\frac{1}{n}\sum \lvert y_i - \hat{y}_i \rvert\) | Average absolute difference between actual and predicted yield | kg | Lower |
| **MSE** — Mean Squared Error | \(\frac{1}{n}\sum (y_i - \hat{y}_i)^2\) | Average squared error; penalizes large misses more heavily | kg² | Lower |
| **RMSE** — Root Mean Squared Error | \(\sqrt{\text{MSE}}\) | Typical prediction error in the same unit as yield; sensitive to large errors | kg | Lower |
| **R²** — Coefficient of Determination | \(1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}\) | Proportion of yield variance explained by the model | unitless | Higher (1 = perfect) |

*Table 4. Evaluation metrics used for the yield-prediction models.*

### How to explain each metric

- **MAE** is the most intuitive metric: “On average, the prediction is off by X kilograms.”
- **MSE** squares the errors, so one large mistake affects it much more than several small ones. Its unit is kg², which is not directly interpretable, but it is useful for comparing models.
- **RMSE** converts MSE back to kilograms, so it reads like a typical error size while still penalizing large mistakes.
- **R²** compares the model against simply predicting the mean yield. A value of 1 is perfect, 0 means the model is no better than the mean, and a negative value means it is worse than the mean on that test set.

### Current notebook results

| Model | MSE | RMSE | MAE | R² |
|---|---:|---:|---:|---:|
| Linear Regression | 0.6832 | 0.8266 kg | 0.7480 kg | −7.5401 |
| Random Forest | 0.1797 | 0.4239 kg | 0.2640 kg | −1.2463 |

*Table 5. Results from the 13-record notebook run.*

**Interpretation:**

Random Forest produced the lower MSE, RMSE, and MAE, so it was selected. Both R² values are negative because the test set contains only **3 records**; with so few samples, one unusual harvest can make the model perform worse than the test-set mean. This makes R² unstable and overly pessimistic in this experiment. MAE and RMSE are therefore the more informative metrics here, and the small test size should be stated as a limitation.

> **Note:** no result chart is included in this section, as required. Table 5 is optional evidence; the minimum requirement is Table 4, which explains the metrics.

---

## G. Model Integration

![Figure 3. Integration of the trained yield model with the Django backend](ml_diagrams/figure_3_django_integration.png)

*Figure 3. Integration of the trained yield model with the Django backend.*

### Active production estimate flow

1. **Offline training.** Run all cells in `predictive_maintenance_training.ipynb` using the v3 Kabutomate harvest dataset.
2. **Model artifact.** The notebook saves `predictive_harvest_weight_v3_model.pkl` in the Django project root. Its inputs are `Growing_Days`, `Humidity_pct`, `Temperature_C`, and `Air_Quality_CO2_ppm`; its output is `Weight_g`.
3. **Loader and validation.** `core/harvest_weight_model.py` loads the v3 artifact, checks its feature/target schema, and refuses inputs outside the observed range for any model feature.
4. **API view.** `core/views.py` uses the selected growing days and the latest sensor reading with MQ-135 data for `POST /api/production/predict/` and new production batches.
5. **Frontend.** `templates/production.html` asks for 2, 3, or 4 expected growing days, displays the sensor values used with the prediction in grams, and saves the equivalent in kilograms.

The website's `SensorReading.air_quality_ppm` value is provided by the MQ-135. The production predictor maps it to the dataset's `Air_Quality_CO2_ppm` feature as requested; it is an MQ-135 air-quality reading, not a true CO₂ measurement. Predictions are unavailable when there is no recorded MQ-135 reading.

The separate historical model (`mushroom_yield_model.pkl`, trained with `python manage.py train_yield_model`) is no longer used for new production-page estimates.

### Relevant code path

```text
predictive_harvest_weight_v3_model.pkl
        ↓
core/harvest_weight_model.py :: load_harvest_weight_model()
        ↓
core/harvest_weight_model.py :: predict_harvest_weight_grams()
        ↓
core/views.py :: production_predict_api()
        ↓
POST /api/production/predict/ (Growing_Days + latest sensor conditions)
        ↓
templates/production.html (JavaScript fetch)
        ↓
Predicted weight displayed in grams; saved in kilograms
```

The management command `python manage.py train_yield_model` continues to train the separate historical model and does not replace either artifact.

---

## Consistency Notes Before Submission

These points should be checked so the paper matches the code.

### 1. Notebook features vs. deployed features

The notebook uses **7 features**:

```text
product_id, start_month, growth_days, cost,
same_product_prev_yield_1, same_product_prev_avg_3, farm_prev_avg_5
```

The deployed `core/yield_model.py` currently uses **4 features**:

```text
product_id, same_product_prev_yield_1,
same_product_prev_avg_3, farm_prev_avg_5
```

If the paper claims that the **7-feature notebook model** is the deployed model, that is not currently true. Choose one of these approaches:

- **Recommended for the current paper:** present the notebook as the model-selection experiment and state that the deployed pipeline is retrained with the four features available at prediction time, or
- Align `FEATURE_COLUMNS` and `_build_feature_row()` in `core/yield_model.py` with the seven notebook features before claiming full integration.

### 2. Dataset size changed

The notebook output documents a **13-record snapshot**. The live database now contains **15 harvested batches**, so rerunning the notebook today will produce a different split and different metrics.

For the paper, use the saved notebook output or the exported 13-record CSV so that Tables 1 and 5 and Figure 1 stay consistent.

### 3. Do not mix metrics from different runs

The current `mushroom_yield_model.pkl` was retrained later on a different dataset (81 rows, 4 features) and has different metrics. Use the 13-record notebook values in Section F, or retrain once and report that single consistent run.

---

## How to Insert These into Word or Google Docs

| Item | Recommended format |
|---|---|
| Tables 1, 2, 4, 5 | Native Word/Google Docs tables |
| Figure 1 | Insert `ml_diagrams/figure_1_data_split.png` |
| Figure 2 | Insert `ml_diagrams/figure_2_training_workflow.png` |
| Figure 3 | Insert `ml_diagrams/figure_3_django_integration.png` |
| Captions | Use the italic caption lines under each table/figure |

The PNG diagrams are exported at high resolution for print. Number them consistently with the rest of the chapter (for example, Figure 3.1, Figure 3.2, Figure 3.3).

---

## File Map

| File | Purpose |
|---|---|
| `ML_DOCUMENTATION.md` | This document |
| `ml_diagrams/figure_1_data_split.png` | 13 records → 10 training / 3 testing |
| `ml_diagrams/figure_2_training_workflow.png` | End-to-end training workflow |
| `ml_diagrams/figure_3_django_integration.png` | Model-to-Django integration |

---

*End of machine learning documentation.*
