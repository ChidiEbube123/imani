# GovTrust — Government Project Monitoring Platform

## Architecture Overview

```
govtrust/
├── projects/          # Project & contractor CRUD
├── monitoring/        # Evidence upload + AI analysis engine
├── payments/          # Milestone-triggered payment logic
├── blockchain_ledger/ # Pure-Python SHA-256 proof-of-work chain
├── templates/         # Django HTML templates
└── media/             # Uploaded evidence images
```
#mm
## Quick Start

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Admin: http://localhost:8000/admin  →  admin / govtrust2024

## Core Flow

1. Register Contractor → Create Project (auto-creates 5 milestones)
2. Upload Evidence (satellite/camera/crowdsourced image)
3. AI Engine (ai_engine.py) runs mock-YOLO detection → computes stage scores → overall completion %
4. Result recorded on blockchain (blockchain_ledger/chain.py)
5. If milestone crossed → Payment auto-created → Admin approves → Released + blockchain TX hash stored

## Replacing Mock YOLO with Real YOLOv3

In `monitoring/ai_engine.py`, replace `_mock_yolo_detect()`:

```python
import cv2, numpy as np

def _mock_yolo_detect(image_path):
    net = cv2.dnn.readNet('models/yolov3-construction.weights', 'models/yolov3-construction.cfg')
    with open('models/construction.names') as f:
        classes = f.read().strip().split('\n')
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    blob = cv2.dnn.blobFromImage(img, 1/255, (416,416), swapRB=True)
    net.setInput(blob)
    layer_names = net.getLayerNames()
    output_layers = [layer_names[i-1] for i in net.getUnconnectedOutLayers()]
    outs = net.forward(output_layers)
    detections = []
    for out in outs:
        for det in out:
            scores = det[5:]
            class_id = np.argmax(scores)
            confidence = float(scores[class_id])
            if confidence > settings.YOLO_CONFIDENCE_THRESHOLD:
                detections.append({'label': classes[class_id], 'confidence': confidence, 'bbox': det[:4].tolist()})
    return detections
```

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | /api/projects/ | All projects JSON |
| GET | /monitoring/api/evidence/{id}/analysis/ | AI result JSON |
| POST | /monitoring/api/evidence/{id}/reanalyse/ | Trigger re-analysis |
| GET | /payments/api/stats/ | Payment statistics |
| GET | /blockchain/api/status/ | Chain validity check |
| GET | /blockchain/api/block/{n}/ | Single block data |

## Completion Algorithm

Stage weights (configurable in settings.py):
- Foundation: 15%
- Structure: 25%
- Roofing: 20%
- Finishing: 25%
- Landscaping: 15%

Score = Σ (stage_score × weight)
Stage score = sigmoid-smoothed confidence-weighted detection ratio

Multi-image aggregation uses exponential recency decay (λ=0.85) to
weight recent evidence more heavily than older submissions.

## Blockchain

Pure Python SHA-256 proof-of-work (difficulty=2, configurable).
Every analysis result and payment event is recorded as a block.
Chain integrity can be verified at /blockchain/ or via the API.
