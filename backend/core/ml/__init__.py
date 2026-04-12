"""Trainable ML helpers for signal->execution->outcome learning."""

from .dataset import TrainingDataset, TrainingRow, build_live_feature_dict, build_training_datasets, build_training_rows_from_entities
from .runtime import build_ml_runtime_status, evaluate_ml_overlay, list_training_runs, maybe_run_scheduled_training, train_ml_models
from .trainer import InsufficientTrainingDataError, TrainedModelArtifact, predict_probability, train_classifier

__all__ = [
    'TrainingDataset',
    'TrainingRow',
    'build_live_feature_dict',
    'build_training_datasets',
    'build_training_rows_from_entities',
    'build_ml_runtime_status',
    'evaluate_ml_overlay',
    'list_training_runs',
    'maybe_run_scheduled_training',
    'train_ml_models',
    'InsufficientTrainingDataError',
    'TrainedModelArtifact',
    'predict_probability',
    'train_classifier',
]
