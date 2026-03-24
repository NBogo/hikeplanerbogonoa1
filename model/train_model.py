import os
import pickle
import datetime
from pathlib import Path

from dotenv import load_dotenv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sn
from pymongo import MongoClient

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path, override=True)
mongo_uri = os.getenv("MONGO_DB_CONNECTION_STRING")
if not mongo_uri:
    raise SystemExit("Missing MongoDB URI. Set MONGO_DB_CONNECTION_STRING in .env or in the environment.")

client = MongoClient(mongo_uri)
db = client["tracks"]
collection = db["tracks"]

projection = {"gpx": 0, "url": 0, "bounds": 0, "name": 0}
track = collection.find_one(projection=projection)
if not track:
    raise SystemExit("No tracks found in MongoDB.")

print("\n*** Loading Tracks from MongoDB ***")
chunks = []
batch = []
chunk_size = 2000
cursor = collection.find(projection=projection)
total_loaded = 0
for idx, doc in enumerate(cursor, start=1):
    batch.append(doc)
    total_loaded = idx
    if idx % chunk_size == 0:
        chunks.append(pd.DataFrame(batch))
        print(f"Loaded {idx} tracks...")
        batch.clear()
if batch:
    chunks.append(pd.DataFrame(batch))
    print(f"Loaded {total_loaded} tracks...")

df = pd.concat(chunks, ignore_index=True).set_index("_id")
df['avg_speed'] = df['length_3d'] / df['moving_time']
df['difficulty_num'] = df['difficulty'].map(lambda x: int(x[1])).astype('int32')
df.dropna()
df = df[df['avg_speed'] < 2]
df = df[df['min_elevation'] > 0]
df = df[df['length_2d'] < 100000]
print(f"{len(df)} tracks processed.")

# Correlation heatmap
corr = df.corr(numeric_only=True)
print("\n*** Correlation Matrix ***")
print(corr)
plt.figure(figsize=(10, 8))
sn.heatmap(corr, annot=True, fmt=".2f", annot_kws={"size": 7})
static_dir = Path(__file__).resolve().parent.parent / "frontend" / "static" / "images"
static_dir.mkdir(parents=True, exist_ok=True)
plt.tight_layout()
plt.savefig(static_dir / "heatmap.png", dpi=150)
plt.close()

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split, GridSearchCV

y = df.reset_index()['moving_time']
x = df.reset_index()[['downhill', 'uphill', 'length_3d', 'max_elevation']]
x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.20, random_state=42)

print(f"\n{'*** Model Comparison ***':<40} {'R2':>8} {'MSE':>14} {'RMSE':>10}")

# 1. Linear Regression (Baseline)
lr = LinearRegression()
lr.fit(x_train, y_train)
y_pred_lr = lr.predict(x_test)
r2_lr = r2_score(y_test, y_pred_lr)
mse_lr = mean_squared_error(y_test, y_pred_lr)
print(f"{'Linear Regression (Baseline)':<40} {r2_lr:>8.4f} {mse_lr:>14.2f} {mse_lr**0.5:>10.2f}")

# 2. GradientBoostingRegressor (Default)
gbr_default = GradientBoostingRegressor(n_estimators=50, random_state=9000)
gbr_default.fit(x_train, y_train)
y_pred_gbr_default = gbr_default.predict(x_test)
r2_gbr_default = r2_score(y_test, y_pred_gbr_default)
mse_gbr_default = mean_squared_error(y_test, y_pred_gbr_default)
print(f"{'GradientBoosting (Default)':<40} {r2_gbr_default:>8.4f} {mse_gbr_default:>14.2f} {mse_gbr_default**0.5:>10.2f}")

# 3. GradientBoostingRegressor mit GridSearchCV (Hyperparameter-Tuning)
print("\n*** Hyperparameter-Tuning GradientBoostingRegressor (GridSearchCV) ***")
param_grid_gbr = {
    'n_estimators': [50, 100, 200],
    'learning_rate': [0.05, 0.1, 0.2],
    'max_depth': [3, 4, 5],
}
grid_gbr = GridSearchCV(
    GradientBoostingRegressor(random_state=9000),
    param_grid_gbr,
    cv=3,
    scoring='r2',
    n_jobs=-1,
    verbose=1,
)
grid_gbr.fit(x_train, y_train)
best_gbr = grid_gbr.best_estimator_
print(f"Best params GBR: {grid_gbr.best_params_}")
y_pred_gbr_tuned = best_gbr.predict(x_test)
r2_gbr_tuned = r2_score(y_test, y_pred_gbr_tuned)
mse_gbr_tuned = mean_squared_error(y_test, y_pred_gbr_tuned)
print(f"{'GradientBoosting (Tuned)':<40} {r2_gbr_tuned:>8.4f} {mse_gbr_tuned:>14.2f} {mse_gbr_tuned**0.5:>10.2f}")

# 4. Random Forest mit GridSearchCV
print("\n*** Hyperparameter-Tuning RandomForestRegressor (GridSearchCV) ***")
param_grid_rf = {
    'n_estimators': [50, 100, 200],
    'max_depth': [None, 10, 20],
    'min_samples_split': [2, 5],
}
grid_rf = GridSearchCV(
    RandomForestRegressor(random_state=42),
    param_grid_rf,
    cv=3,
    scoring='r2',
    n_jobs=-1,
    verbose=1,
)
grid_rf.fit(x_train, y_train)
best_rf = grid_rf.best_estimator_
print(f"Best params RF: {grid_rf.best_params_}")
y_pred_rf = best_rf.predict(x_test)
r2_rf = r2_score(y_test, y_pred_rf)
mse_rf = mean_squared_error(y_test, y_pred_rf)
print(f"{'RandomForest (Tuned)':<40} {r2_rf:>8.4f} {mse_rf:>14.2f} {mse_rf**0.5:>10.2f}")

# 5. Modellvergleich Plot
print("\n*** Modellvergleich Plot ***")
models = ['Linear\nRegression', 'GBR\n(Default)', 'GBR\n(Tuned)', 'Random\nForest']
r2_scores = [r2_lr, r2_gbr_default, r2_gbr_tuned, r2_rf]
colors = ['#6c757d', '#fd7e14', '#0d6efd', '#198754']

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
bars = axes[0].bar(models, r2_scores, color=colors, edgecolor='white', linewidth=1.5)
axes[0].set_title('R² Score Vergleich', fontsize=13, fontweight='bold')
axes[0].set_ylabel('R² Score')
axes[0].set_ylim(0, 1)
for bar, score in zip(bars, r2_scores):
    axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                 f'{score:.4f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

rmse_scores = [mse_lr**0.5, mse_gbr_default**0.5, mse_gbr_tuned**0.5, mse_rf**0.5]
bars2 = axes[1].bar(models, rmse_scores, color=colors, edgecolor='white', linewidth=1.5)
axes[1].set_title('RMSE Vergleich (tiefer = besser)', fontsize=13, fontweight='bold')
axes[1].set_ylabel('RMSE (Sekunden)')
for bar, score in zip(bars2, rmse_scores):
    axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50,
                 f'{score:.0f}s', ha='center', va='bottom', fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig(static_dir / "model_comparison.png", dpi=150)
plt.close()
print("Modellvergleich gespeichert: frontend/static/images/model_comparison.png")

# Bestes Modell bestimmen
best_model_name = max(
    [('GBR Tuned', r2_gbr_tuned, best_gbr), ('Random Forest', r2_rf, best_rf)],
    key=lambda x: x[1]
)
print(f"\nBestes Modell: {best_model_name[0]} (R²={best_model_name[1]:.4f})")
gbr = best_model_name[2]

# Sample Values
print("\n*** Sample Values ***")
samples = [
    {"downhill": 300, "uphill": 700, "length_3d": 10000, "max_elevation": 1200},
    {"downhill": 600, "uphill": 900, "length_3d": 15000, "max_elevation": 2100},
    {"downhill": 200, "uphill": 400, "length_3d": 7000, "max_elevation": 1400},
    {"downhill": 1200, "uphill": 1300, "length_3d": 22000, "max_elevation": 2800},
    {"downhill": 100, "uphill": 250, "length_3d": 5000, "max_elevation": 1100},
]

def din33466(uphill, downhill, distance):
    km = distance / 1000.0
    vertical = downhill / 500.0 + uphill / 300.0
    horizontal = km / 4.0
    return 3600.0 * (min(vertical, horizontal) / 2 + max(vertical, horizontal))

def sac(uphill, distance):
    km = distance / 1000.0
    return 3600.0 * (uphill/400.0 + km/4.0)

print(f"{'downhill':>8}  {'uphill':>6}  {'length_3d':>9}  {'max_elev':>8}  "
      f"{'DIN33466':>8}  {'SAC':>8}  {'Linear':>8}  {'GBR':>8}  {'RF':>8}")
for sample in samples:
    demodf = pd.DataFrame([sample], columns=["downhill", "uphill", "length_3d", "max_elevation"])
    time_lr = lr.predict(demodf)[0]
    time_gbr = gbr.predict(demodf)[0]
    time_rf = best_rf.predict(demodf)[0]
    din = datetime.timedelta(seconds=din33466(sample["uphill"], sample["downhill"], sample["length_3d"]))
    sac_time = datetime.timedelta(seconds=sac(sample["uphill"], sample["length_3d"]))
    print(
        f"{sample['downhill']:>8}  {sample['uphill']:>6}  "
        f"{sample['length_3d']:>9}  {sample['max_elevation']:>8}  "
        f"{str(din).rsplit(':', 1)[0]:>8}  {str(sac_time).rsplit(':', 1)[0]:>8}  "
        f"{str(datetime.timedelta(seconds=time_lr)).rsplit(':', 1)[0]:>8}  "
        f"{str(datetime.timedelta(seconds=time_gbr)).rsplit(':', 1)[0]:>8}  "
        f"{str(datetime.timedelta(seconds=time_rf)).rsplit(':', 1)[0]:>8}"
    )

# Save models
with open('GradientBoostingRegressor.pkl', 'wb') as fid:
    pickle.dump(gbr, fid)
with open('LinearRegression.pkl', 'wb') as fid:
    pickle.dump(lr, fid)
with open('RandomForest.pkl', 'wb') as fid:
    pickle.dump(best_rf, fid)

print("\nModelle gespeichert: GradientBoostingRegressor.pkl, LinearRegression.pkl, RandomForest.pkl")

# Verify
with open('GradientBoostingRegressor.pkl', 'rb') as fid:
    gbr_loaded = pickle.load(fid)
print("Verifikation GBR OK")