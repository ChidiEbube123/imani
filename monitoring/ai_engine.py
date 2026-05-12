"""
GovTrust AI Analysis Engine
----------------------------
Simulates YOLOv3 construction-site detection for MVP.
In production: swap _mock_yolo_detect() with real YOLOv3 inference
using OpenCV + darknet or ultralytics.
"""

import random
import math
from django.conf import settings
from PIL import Image
import io


# ─────────────────────────────────────────────────────────────
# Construction element labels that a real YOLOv3 model would
# detect on a construction site.
# ─────────────────────────────────────────────────────────────
CONSTRUCTION_CLASSES = [
    'foundation_slab', 'column', 'beam', 'wall_block', 'roof_truss',
    'roof_sheet', 'window_frame', 'door_frame', 'scaffolding',
    'excavation', 'reinforcement_bar', 'concrete_mixer', 'crane',
    'worker', 'finished_floor', 'plastered_wall', 'painted_surface',
    'fence', 'road_surface', 'vegetation_cleared', 'drainage_pipe',
]

# Maps detected classes → construction stage
STAGE_MAP = {
    'foundation': ['excavation', 'foundation_slab', 'reinforcement_bar'],
    'structure':  ['column', 'beam', 'wall_block', 'scaffolding', 'concrete_mixer', 'crane'],
    'roofing':    ['roof_truss', 'roof_sheet'],
    'finishing':  ['window_frame', 'door_frame', 'finished_floor', 'plastered_wall', 'painted_surface'],
    'landscaping':['fence', 'road_surface', 'vegetation_cleared', 'drainage_pipe'],
}

STAGE_WEIGHTS = settings.COMPLETION_WEIGHTS  # from settings


def _mock_yolo_detect(image_path: str) -> list[dict]:
    """
    Mock YOLO detection — replace with real inference in production.

    Real implementation:
        net = cv2.dnn.readNet('yolov3.weights', 'yolov3.cfg')
        blob = cv2.dnn.blobFromImage(img, 1/255, (416,416), swapRB=True)
        net.setInput(blob)
        outs = net.forward(output_layers)
        ... parse bounding boxes & class scores
    """
    # Analyse image size as a proxy for content richness
    try:
        img = Image.open(image_path)
        width, height = img.size
        pixel_variance = _estimate_variance(img)
    except Exception:
        width, height, pixel_variance = 800, 600, 0.5

    # Seed random with image path for reproducibility
    rng = random.Random(hash(image_path) % (2**32))

    num_detections = rng.randint(3, 12)
    detections = []
    for _ in range(num_detections):
        label = rng.choice(CONSTRUCTION_CLASSES)
        confidence = rng.uniform(0.42, 0.97)
        if confidence < settings.YOLO_CONFIDENCE_THRESHOLD:
            continue
        x = rng.uniform(0, 0.8)
        y = rng.uniform(0, 0.8)
        w = rng.uniform(0.05, 0.3)
        h = rng.uniform(0.05, 0.3)
        detections.append({
            'label': label,
            'confidence': round(confidence, 4),
            'bbox': [round(x, 4), round(y, 4), round(w, 4), round(h, 4)],
        })
    return detections


def _estimate_variance(img: Image.Image) -> float:
    """Simple brightness variance proxy for image richness."""
    try:
        gray = img.convert('L').resize((64, 64))
        pixels = list(gray.getdata())
        mean = sum(pixels) / len(pixels)
        variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
        return min(variance / 10000, 1.0)
    except Exception:
        return 0.5


def _compute_stage_scores(detections: list[dict]) -> dict:
    """
    Given detections, compute per-stage completion percentage (0–100).
    Logic: for each stage, count detected elements / expected elements
    weighted by confidence.
    """
    stage_scores = {}
    detected_labels = {d['label']: d['confidence'] for d in detections}

    for stage, expected_labels in STAGE_MAP.items():
        hits = 0.0
        for lbl in expected_labels:
            if lbl in detected_labels:
                hits += detected_labels[lbl]
        # Normalise: max possible = len(expected_labels) * 1.0
        raw = hits / max(len(expected_labels), 1)
        # Sigmoid-smooth so it never snaps to 100 from one image
        score = 100 * (1 - math.exp(-2.5 * raw))
        stage_scores[stage] = round(score, 2)

    return stage_scores


def compute_overall_completion(stage_scores: dict) -> float:
    """Weighted sum of stage scores → overall completion %."""
    total = 0.0
    for stage, weight in STAGE_WEIGHTS.items():
        total += stage_scores.get(stage, 0.0) * weight
    return round(total, 2)


def analyse_evidence(evidence_instance) -> dict:
    """
    Main entry point called from views/tasks.
    Returns a dict ready to populate AIAnalysisResult.
    """
    image_path = evidence_instance.image.path
    detections = _mock_yolo_detect(image_path)

    stage_scores = _compute_stage_scores(detections)
    overall = compute_overall_completion(stage_scores)
    avg_conf = (
        sum(d['confidence'] for d in detections) / len(detections)
        if detections else 0.0
    )

    # Structured summary
    detected_elements = {}
    for d in detections:
        detected_elements.setdefault(d['label'], []).append(d['confidence'])

    notes_parts = []
    for stage, score in stage_scores.items():
        notes_parts.append(f"{stage.title()}: {score:.1f}%")

    return {
        'raw_detections': detections,
        'detected_elements': detected_elements,
        'stage_scores': stage_scores,
        'completion_score': overall,
        'confidence': round(avg_conf, 4),
        'analysis_notes': ' | '.join(notes_parts),
        'model_version': 'yolov3-construction-mvp-v1.0',
    }


def aggregate_project_completion(project) -> float:
    """
    Aggregate multiple evidence analyses for a project
    using exponential recency weighting.
    """
    from monitoring.models import AIAnalysisResult, MediaEvidence

    analyses = (
        AIAnalysisResult.objects
        .filter(evidence__project=project, evidence__status='analyzed')
        .order_by('-analyzed_at')
    )

    if not analyses.exists():
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0
    decay = 0.85  # older readings count less

    for i, analysis in enumerate(analyses):
        weight = (decay ** i) * analysis.confidence
        weighted_sum += analysis.completion_score * weight
        total_weight += weight

    return round(weighted_sum / total_weight, 2) if total_weight else 0.0
