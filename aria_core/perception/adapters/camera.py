# aria_core/perception/adapters/camera.py
"""
Camera Adapter — visual perception.

Provides:
- Object detection
- Scene classification
- Text recognition (OCR)
- Face detection
- Visual landmarks

Uses provider-independent interface.
"""

from __future__ import annotations

import datetime
from typing import Optional, Protocol, runtime_checkable

from ..models import (
    PerceptionFrame,
    GeoLocation,
    EnvironmentType,
    PerceivedObject,
    ObjectType,
    PerceivedAgent,
)


@runtime_checkable
class VisionProvider(Protocol):
    """Protocol for computer vision providers."""
    
    def detect_objects(self, image: bytes) -> list[dict]: ...
    def classify_scene(self, image: bytes) -> str: ...
    def detect_faces(self, image: bytes) -> list[dict]: ...
    def read_text(self, image: bytes) -> list[str]: ...


class CameraAdapter:
    """
    Adapter for visual perception from camera.
    
    Usage:
        adapter = CameraAdapter()
        adapter.process_image(image_bytes)
        
        frame = adapter.get_current_perception()
        # Frame contains detected objects, scenes, faces
    """
    
    def __init__(self, provider: Optional[VisionProvider] = None):
        self._source_name = "camera"
        self._provider = provider
        self._last_image: Optional[bytes] = None
        self._detected_objects: list[dict] = []
        self._scene_type: str = "unknown"
        self._detected_faces: list[dict] = []
        self._detected_text: list[str] = []
        self._available: bool = True
        self._last_processed: Optional[datetime.datetime] = None
    
    def process_image(self, image: bytes) -> None:
        """Process a camera image."""
        self._last_image = image
        self._last_processed = datetime.datetime.now()
        
        if self._provider:
            try:
                self._detected_objects = self._provider.detect_objects(image)
                self._scene_type = self._provider.classify_scene(image)
                self._detected_faces = self._provider.detect_faces(image)
                self._detected_text = self._provider.read_text(image)
            except Exception:
                pass
    
    def get_current_perception(self) -> PerceptionFrame:
        """Get perception frame from camera data."""
        if self._last_image is None:
            return PerceptionFrame(
                source=self._source_name,
                environment_type=EnvironmentType.UNKNOWN,
                overall_confidence=0.0,
                completeness=0.0,
            )
        
        # Convert detected objects to PerceivedObject
        objects = []
        for obj in self._detected_objects:
            objects.append(PerceivedObject(
                object_type=self._classify_object(obj.get("label", "")),
                name=obj.get("label", "unknown"),
                properties={
                    "confidence": obj.get("confidence", 0.5),
                    "bbox": obj.get("bbox", []),
                },
                confidence=obj.get("confidence", 0.5),
            ))
        
        # Convert detected faces to PerceivedAgent
        agents = []
        for face in self._detected_faces:
            agents.append(PerceivedAgent(
                name=face.get("name", "unknown"),
                agent_type="human",
                state={
                    "emotion": face.get("emotion", "neutral"),
                    "age_estimate": face.get("age", 0),
                },
                confidence=face.get("confidence", 0.5),
            ))
        
        # Determine environment from scene
        env_type = self._scene_to_environment(self._scene_type)
        
        return PerceptionFrame(
            timestamp=datetime.datetime.now(),
            source=self._source_name,
            environment_type=env_type,
            objects=objects,
            agents=agents,
            overall_confidence=self._calculate_confidence(),
            completeness=0.7,
            raw_data={
                "scene_type": self._scene_type,
                "object_count": len(self._detected_objects),
                "face_count": len(self._detected_faces),
                "text_detected": self._detected_text,
            },
        )
    
    def get_location(self) -> Optional[GeoLocation]:
        """Camera doesn't provide location directly."""
        return None
    
    def is_available(self) -> bool:
        """Check if camera is available."""
        return self._available
    
    def get_confidence(self) -> float:
        """Get confidence in camera perception."""
        return self._calculate_confidence()
    
    def get_source_name(self) -> str:
        """Return source name."""
        return self._source_name
    
    def get_detected_text(self) -> list[str]:
        """Get text detected in last image."""
        return self._detected_text
    
    def get_scene_type(self) -> str:
        """Get scene classification."""
        return self._scene_type
    
    def _calculate_confidence(self) -> float:
        """Calculate overall confidence."""
        if not self._provider:
            return 0.3
        
        if not self._detected_objects and not self._detected_faces:
            return 0.4
        
        return 0.7
    
    def _classify_object(self, label: str) -> ObjectType:
        """Classify detected object label to ObjectType."""
        label_lower = label.lower()
        
        if any(w in label_lower for w in ["person", "face", "human"]):
            return ObjectType.AGENT
        elif any(w in label_lower for w in ["car", "vehicle", "truck"]):
            return ObjectType.VEHICLE
        elif any(w in label_lower for w in ["building", "house", "structure"]):
            return ObjectType.BUILDING
        elif any(w in label_lower for w in ["tree", "plant", "flower"]):
            return ObjectType.TERRAIN
        elif any(w in label_lower for w in ["animal", "dog", "cat"]):
            return ObjectType.ANIMAL
        else:
            return ObjectType.UNKNOWN
    
    def _scene_to_environment(self, scene: str) -> EnvironmentType:
        """Convert scene type to environment type."""
        scene_lower = scene.lower()
        
        if any(w in scene_lower for w in ["indoor", "room", "office", "home"]):
            return EnvironmentType.INDOOR
        elif any(w in scene_lower for w in ["outdoor", "street", "park", "nature"]):
            return EnvironmentType.OUTDOOR
        else:
            return EnvironmentType.UNKNOWN
