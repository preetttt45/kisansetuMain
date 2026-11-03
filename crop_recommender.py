
import os
import pandas as pd
import joblib

from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score


# --------------------------------------------------
# 1. FILE PATHS AND MODEL CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATASET_PATH = BASE_DIR / "dataset" / "Crop_recommendation.csv"

MODEL_DIR = BASE_DIR / "models"

MODEL_PATH = MODEL_DIR / "crop_recommendation_model.pkl"


# Features used by the ML model
FEATURE_COLUMNS = [
    "N",
    "P",
    "K",
    "temperature",
    "humidity",
    "ph",
    "rainfall"
]

TARGET_COLUMN = "label"


# --------------------------------------------------
# 2. LOAD AND VALIDATE DATASET
# --------------------------------------------------

def load_dataset():

    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            "Crop recommendation dataset not found. "
            "Place Crop_recommendation.csv inside dataset folder."
        )

    df = pd.read_csv(DATASET_PATH)

    required_columns = FEATURE_COLUMNS + [TARGET_COLUMN]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Dataset is missing columns: {missing_columns}"
        )

    # Convert input columns to numeric values
    for col in FEATURE_COLUMNS:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        )

    # Remove incomplete or invalid rows
    df = df.dropna(
        subset=required_columns
    )

    df[TARGET_COLUMN] = (
        df[TARGET_COLUMN].astype(str).str.strip()
    )

    df = df[
        (df[TARGET_COLUMN] != "") &
        (df[FEATURE_COLUMNS].ge(0).all(axis=1))
    ]

    if df.empty:
        raise ValueError(
            "Dataset does not contain valid training records."
        )

    return df


# --------------------------------------------------
# 3. GET VALID INPUT RANGES FROM DATASET
# --------------------------------------------------

def get_feature_ranges():

    df = load_dataset()

    ranges = {}

    for feature in FEATURE_COLUMNS:

        ranges[feature] = {
            "min": float(df[feature].min()),
            "max": float(df[feature].max())
        }

    return ranges


# --------------------------------------------------
# 4. TRAIN RANDOM FOREST CLASSIFIER
# --------------------------------------------------

def train_model():

    df = load_dataset()

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    # Split dataset into training and testing data
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y
    )

    # Create Random Forest model
    model = RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1
    )

    # Train using training data
    model.fit(X_train, y_train)

    # Evaluate on unseen test data
    y_pred = model.predict(X_test)

    accuracy = accuracy_score(
        y_test, y_pred
    )

    print("--------------------------------")
    print("CROP RECOMMENDATION MODEL")
    print("--------------------------------")
    print(f"Dataset records: {len(df)}")
    print(f"Crop categories: {y.nunique()}")
    print(f"Test accuracy: {accuracy * 100:.2f}%")
    print("--------------------------------")

    # Retrain using the complete dataset
    model.fit(X, y)

    # Save the trained model
    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    model_data = {
        "model": model,
        "accuracy": accuracy,
        "features": FEATURE_COLUMNS
    }

    joblib.dump(
        model_data,
        MODEL_PATH
    )

    print("Trained model saved successfully.")

    return model_data


# --------------------------------------------------
# 5. LOAD EXISTING MODEL OR TRAIN A NEW MODEL
# --------------------------------------------------

def get_model():

    if MODEL_PATH.exists():

        try:
            model_data = joblib.load(MODEL_PATH)

            if model_data.get("features") == FEATURE_COLUMNS:
                return model_data

        except Exception:
            print("Existing model could not be loaded.")

    return train_model()


# --------------------------------------------------
# 6. PREDICT TOP THREE SUITABLE CROPS
# --------------------------------------------------

def recommend_crops(input_values):

    # Load trained model
    model_data = get_model()

    model = model_data["model"]

    # Convert farmer inputs into model format
    input_df = pd.DataFrame(
        [input_values],
        columns=FEATURE_COLUMNS
    )

    # Get prediction scores for all crop classes
    probabilities = model.predict_proba(
        input_df
    )[0]

    crop_names = model.classes_

    # Get indices of top three scores
    top_indices = probabilities.argsort()[::-1][:3]

    recommendations = []

    for index in top_indices:

        recommendations.append({
            "crop": str(crop_names[index]),
            "score": round(
                float(probabilities[index]) * 100,
                2
            )
        })

    return recommendations, round(
        model_data["accuracy"] * 100, 2
    )
