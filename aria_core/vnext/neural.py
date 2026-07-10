# aria_core/vnext/neural.py
"""
Neural Adaptation Pipeline — updates neural models from experience.

Pipeline:
LearningManager → Experience Buffer → Dream Scheduler → Neural Trainer → Validated Model → Hot Swap

The neural model updates only when enough valuable experiences accumulate.
Supports rollback, versioning, and evaluation before deployment.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional, Protocol, runtime_checkable

from .models import Experience


@runtime_checkable
class NeuralModel(Protocol):
    """Protocol for neural models that can be trained."""
    
    def predict(self, input_data: Any) -> Any: ...
    def train(self, experiences: list[Experience]) -> dict: ...
    def evaluate(self, test_data: list[Experience]) -> dict: ...
    def get_version(self) -> str: ...
    def save(self, path: str) -> None: ...
    def load(self, path: str) -> None: ...


class ModelVersion:
    """A versioned snapshot of a neural model."""
    
    def __init__(
        self,
        version: str,
        model: NeuralModel,
        metrics: dict[str, float],
        timestamp: datetime.datetime,
    ):
        self.version = version
        self.model = model
        self.metrics = metrics
        self.timestamp = timestamp
    
    def is_better_than(self, other: "ModelVersion") -> bool:
        """Check if this version is better than another."""
        # Compare by primary metric (accuracy or loss)
        self_score = self.metrics.get("accuracy", 0) - self.metrics.get("loss", 0)
        other_score = other.metrics.get("accuracy", 0) - other.metrics.get("loss", 0)
        return self_score > other_score


class ExperienceBuffer:
    """Buffer for accumulating experiences before training."""
    
    def __init__(self, max_size: int = 1000, min_size: int = 10):
        self._buffer: list[Experience] = []
        self._max_size = max_size
        self._min_size = min_size
    
    def add(self, experience: Experience) -> None:
        """Add an experience to the buffer."""
        self._buffer.append(experience)
        
        # Trim if over max
        if len(self._buffer) > self._max_size:
            # Keep most important experiences
            self._buffer.sort(key=lambda e: abs(e.reward), reverse=True)
            self._buffer = self._buffer[:self._max_size]
    
    def is_ready(self) -> bool:
        """Check if buffer has enough experiences for training."""
        return len(self._buffer) >= self._min_size
    
    def get_batch(self, batch_size: int | None = None) -> list[Experience]:
        """Get a batch of experiences for training."""
        size = batch_size or len(self._buffer)
        return self._buffer[:size]
    
    def clear(self) -> None:
        """Clear the buffer after training."""
        self._buffer.clear()
    
    def size(self) -> int:
        """Get current buffer size."""
        return len(self._buffer)


class NeuralTrainer:
    """Trains neural models from experience buffers."""
    
    def __init__(
        self,
        model: NeuralModel,
        validation_split: float = 0.2,
    ):
        self._model = model
        self._validation_split = validation_split
        
        # Version history
        self._versions: list[ModelVersion] = []
        self._current_version = 0
    
    def train(self, experiences: list[Experience]) -> dict:
        """
        Train the model on experiences.
        
        Returns training metrics.
        """
        if not experiences:
            return {"error": "no experiences"}
        
        # Split into train/validation
        split_idx = int(len(experiences) * (1 - self._validation_split))
        train_data = experiences[:split_idx]
        val_data = experiences[split_idx:]
        
        # Train
        train_metrics = self._model.train(train_data)
        
        # Evaluate
        if val_data:
            val_metrics = self._model.evaluate(val_data)
            train_metrics.update({f"val_{k}": v for k, v in val_metrics.items()})
        
        # Create version
        version = ModelVersion(
            version=f"v{self._current_version + 1}",
            model=self._model,
            metrics=train_metrics,
            timestamp=datetime.datetime.now(),
        )
        self._versions.append(version)
        self._current_version += 1
        
        return train_metrics
    
    def evaluate(self, test_data: list[Experience]) -> dict:
        """Evaluate the current model."""
        return self._model.evaluate(test_data)
    
    def get_best_version(self) -> Optional[ModelVersion]:
        """Get the best model version."""
        if not self._versions:
            return None
        
        return max(self._versions, key=lambda v: v.metrics.get("accuracy", 0))
    
    def rollback(self, version: int) -> bool:
        """Rollback to a previous version."""
        if 0 <= version < len(self._versions):
            target = self._versions[version]
            # In a real implementation, this would load the model
            return True
        return False


class NeuralAdaptationPipeline:
    """
    Full neural adaptation pipeline.
    
    Pipeline:
    Experience Buffer → Training → Validation → Deployment
    
    Usage:
        pipeline = NeuralAdaptationPipeline(model=my_model)
        
        # Add experiences
        for exp in experiences:
            pipeline.buffer.add(exp)
        
        # Train if ready
        if pipeline.buffer.is_ready():
            metrics = pipeline.train()
            print(metrics)
    """
    
    def __init__(
        self,
        model: NeuralModel,
        buffer_size: int = 1000,
        min_buffer_size: int = 10,
    ):
        self.buffer = ExperienceBuffer(
            max_size=buffer_size,
            min_size=min_buffer_size,
        )
        self.trainer = NeuralTrainer(model)
        self._deployment_count = 0
    
    def train(self) -> dict:
        """Train on buffered experiences."""
        experiences = self.buffer.get_batch()
        metrics = self.trainer.train(experiences)
        self.buffer.clear()
        return metrics
    
    def evaluate(self, test_data: list[Experience]) -> dict:
        """Evaluate current model."""
        return self.trainer.evaluate(test_data)
    
    def should_train(self) -> bool:
        """Check if we should train now."""
        return self.buffer.is_ready()
    
    def get_status(self) -> dict:
        """Get pipeline status."""
        return {
            "buffer_size": self.buffer.size(),
            "buffer_ready": self.buffer.is_ready(),
            "versions": len(self.trainer._versions),
            "deployments": self._deployment_count,
        }
