from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from core.ml.dataset import TrainingDataset


@dataclass
class TrainedModelArtifact:
    target: str
    model_type: str
    vectorizer: DictVectorizer
    model: LogisticRegression
    feature_names: list[str]
    metrics: dict[str, Any]
    params: dict[str, Any]


class InsufficientTrainingDataError(RuntimeError):
    pass



def _class_balance(labels: list[int]) -> dict[str, int]:
    return {
        'negative': sum(1 for label in labels if int(label) == 0),
        'positive': sum(1 for label in labels if int(label) == 1),
    }



def train_classifier(dataset: TrainingDataset, *, min_rows: int = 80, validation_fraction: float = 0.25, random_state: int = 42) -> TrainedModelArtifact:
    rows = list(dataset.rows)
    if len(rows) < max(20, int(min_rows or 80)):
        raise InsufficientTrainingDataError(f'{dataset.target}: not enough rows ({len(rows)} < {max(20, int(min_rows or 80))})')

    labels = [int(row.label) for row in rows]
    balance = _class_balance(labels)
    if balance['negative'] == 0 or balance['positive'] == 0:
        raise InsufficientTrainingDataError(f'{dataset.target}: training labels contain only one class {balance}')

    feature_dicts = [dict(row.features) for row in rows]
    vectorizer = DictVectorizer(sparse=True)
    X = vectorizer.fit_transform(feature_dicts)
    y = labels

    model = LogisticRegression(
        max_iter=700,
        class_weight='balanced',
        solver='liblinear',
        random_state=int(random_state),
    )

    test_size = min(0.4, max(0.15, float(validation_fraction or 0.25)))
    minority_count = min(balance['negative'], balance['positive'])
    params = {
        'validation_fraction': test_size,
        'random_state': int(random_state),
        'solver': 'liblinear',
        'max_iter': 700,
        'class_weight': 'balanced',
    }

    if minority_count < 2:
        model.fit(X, y)
        train_pred = model.predict(X)
        train_proba = model.predict_proba(X)[:, 1]
        metrics = {
            'rows_total': len(rows),
            'rows_train': int(X.shape[0]),
            'rows_validation': 0,
            'label_balance': balance,
            'validation_mode': 'train_only_rare_class_fallback',
            'accuracy': round(float(accuracy_score(y, train_pred)), 6),
            'precision': round(float(precision_score(y, train_pred, zero_division=0)), 6),
            'recall': round(float(recall_score(y, train_pred, zero_division=0)), 6),
            'f1': round(float(f1_score(y, train_pred, zero_division=0)), 6),
            'roc_auc': round(float(roc_auc_score(y, train_proba)), 6),
            'avg_train_probability': round(float(train_proba.mean()), 6),
            'avg_validation_probability': None,
        }
        params['validation_fraction'] = 0.0
        params['rare_class_fallback'] = True
        return TrainedModelArtifact(
            target=dataset.target,
            model_type='logistic_regression',
            vectorizer=vectorizer,
            model=model,
            feature_names=list(vectorizer.feature_names_),
            metrics=metrics,
            params=params,
        )

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=test_size,
        stratify=y,
        random_state=int(random_state),
    )

    model.fit(X_train, y_train)

    val_pred = model.predict(X_val)
    val_proba = model.predict_proba(X_val)[:, 1]
    train_proba = model.predict_proba(X_train)[:, 1]

    metrics = {
        'rows_total': len(rows),
        'rows_train': int(X_train.shape[0]),
        'rows_validation': int(X_val.shape[0]),
        'label_balance': balance,
        'validation_mode': 'holdout_stratified',
        'accuracy': round(float(accuracy_score(y_val, val_pred)), 6),
        'precision': round(float(precision_score(y_val, val_pred, zero_division=0)), 6),
        'recall': round(float(recall_score(y_val, val_pred, zero_division=0)), 6),
        'f1': round(float(f1_score(y_val, val_pred, zero_division=0)), 6),
        'roc_auc': round(float(roc_auc_score(y_val, val_proba)), 6),
        'avg_train_probability': round(float(train_proba.mean()), 6),
        'avg_validation_probability': round(float(val_proba.mean()), 6),
    }
    return TrainedModelArtifact(
        target=dataset.target,
        model_type='logistic_regression',
        vectorizer=vectorizer,
        model=model,
        feature_names=list(vectorizer.feature_names_),
        metrics=metrics,
        params=params,
    )



def predict_probability(artifact: TrainedModelArtifact | dict[str, Any], features: dict[str, Any]) -> float:
    vectorizer = artifact.vectorizer if isinstance(artifact, TrainedModelArtifact) else artifact['vectorizer']
    model = artifact.model if isinstance(artifact, TrainedModelArtifact) else artifact['model']
    X = vectorizer.transform([dict(features)])
    proba = model.predict_proba(X)[0][1]
    return float(proba)
