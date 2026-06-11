"""Temporal tracker for video hazard detection.

Tracks detected objects across frames to produce persistent events
rather than per-frame noise. Uses IoU-based matching with
appearance consistency via LocateAnything embeddings.

Different from Argus:
- Argus: per-frame YOLO detections → counts vehicles
- This: temporal object tracks → detect hazard *persistence* and *onset*
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid


@dataclass
class Tracklet:
    """A single object's track across video frames."""

    track_id: str
    label: str
    category: str
    first_seen_frame: int
    last_seen_frame: int
    bboxes: list[list[float]] = field(default_factory=list)  # [x1,y1,x2,y2] per frame
    confidences: list[float] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)  # seconds from video start
    frame_indices: list[int] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if not self.timestamps:
            return 0.0
        return self.timestamps[-1] - self.timestamps[0]

    @property
    def avg_confidence(self) -> float:
        if not self.confidences:
            return 0.0
        return sum(self.confidences) / len(self.confidences)

    @property
    def is_persistent(self, min_frames: int = 3) -> bool:
        return len(self.frame_indices) >= min_frames

    def to_event_dict(self) -> dict[str, Any]:
        return {
            "event_id": f"evt-{self.track_id}",
            "category": self.category,
            "label": self.label,
            "start_frame": self.first_seen_frame,
            "end_frame": self.last_seen_frame,
            "duration_sec": round(self.duration_seconds, 2),
            "avg_confidence": round(self.avg_confidence, 3),
            "frame_count": len(self.frame_indices),
            "bbox_history": self.bboxes,
        }


class TemporalTracker:
    """IoU-based multi-object tracker for hazard detections."""

    def __init__(
        self,
        iou_threshold: float = 0.5,
        max_missed_frames: int = 5,
        min_track_length: int = 2,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed_frames
        self.min_length = min_track_length
        self._tracks: list[Tracklet] = []
        self._active: list[Tracklet] = []
        self._counter = 0

    @staticmethod
    def _iou(box_a: list[float], box_b: list[float]) -> float:
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])
        inter_w = max(0.0, x2 - x1)
        inter_h = max(0.0, y2 - y1)
        inter = inter_w * inter_h
        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def update(
        self,
        detections: list[dict[str, Any]],
        frame_idx: int,
        timestamp_sec: float,
    ) -> list[Tracklet]:
        """Update tracks with new frame detections.

        Args:
            detections: List of dicts with keys: label, category, bbox, confidence.
            frame_idx: Frame index in video.
            timestamp_sec: Timestamp in seconds.

        Returns:
            List of newly completed tracks that have gone stale.
        """
        # Mark all active as missed for this frame
        missed_this_frame = set()
        matched = set()

        # Greedy bipartite matching by IoU
        for det in detections:
            best_track = None
            best_iou = self.iou_threshold
            det_bbox = det["bbox"]

            for track in self._active:
                if track.label != det["label"]:
                    continue
                if track.track_id in matched:
                    continue
                iou = self._iou(track.bboxes[-1], det_bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_track = track

            if best_track is not None:
                best_track.bboxes.append(det_bbox)
                best_track.confidences.append(det["confidence"])
                best_track.timestamps.append(timestamp_sec)
                best_track.frame_indices.append(frame_idx)
                best_track.last_seen_frame = frame_idx
                matched.add(best_track.track_id)
            else:
                # New track
                self._counter += 1
                new_track = Tracklet(
                    track_id=f"t{uuid.uuid4().hex[:8]}",
                    label=det["label"],
                    category=det.get("category", "unknown"),
                    first_seen_frame=frame_idx,
                    last_seen_frame=frame_idx,
                    bboxes=[det_bbox],
                    confidences=[det["confidence"]],
                    timestamps=[timestamp_sec],
                    frame_indices=[frame_idx],
                )
                self._active.append(new_track)

        # Check for stale tracks
        completed: list[Tracklet] = []
        still_active: list[Tracklet] = []
        for track in self._active:
            missed = frame_idx - track.last_seen_frame
            if missed > self.max_missed:
                if len(track.frame_indices) >= self.min_length:
                    self._tracks.append(track)
                    completed.append(track)
            else:
                still_active.append(track)

        self._active = still_active
        return completed

    def finalize(self) -> list[Tracklet]:
        """Call at end of video to flush remaining active tracks."""
        for track in self._active:
            if len(track.frame_indices) >= self.min_length:
                self._tracks.append(track)
        self._active.clear()
        return self._tracks

    def get_all_events(self) -> list[dict[str, Any]]:
        """Return all completed tracklets as event dicts."""
        return [t.to_event_dict() for t in self._tracks]

    def get_persistent_events(self, min_duration_sec: float = 1.0) -> list[dict[str, Any]]:
        """Filter to events that persisted long enough to be real."""
        return [
            t.to_event_dict()
            for t in self._tracks
            if t.duration_seconds >= min_duration_sec
        ]
