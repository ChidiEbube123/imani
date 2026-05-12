"""
GovTrust Scheduled Monitoring Tasks
-------------------------------------
In production run these with:
  - Celery Beat (recommended): set CELERY_BEAT_SCHEDULE in settings.py
  - Django management commands (simpler): python manage.py run_monitoring
  - Cron: */30 * * * * python manage.py run_monitoring

These tasks simulate pulling images from:
  1. Satellite providers (e.g. Planet, Sentinel-2, Maxar API)
  2. On-site government IP cameras (RTSP/HTTP snapshot endpoints)

In production replace the _fetch_* functions with real API calls.
"""

import os
import io
import logging
import requests
from datetime import datetime, timezone
from django.utils import timezone as dj_tz
from django.conf import settings
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────

def _fetch_satellite_image(project) -> bytes | None:
    """
    Fetch latest satellite image for project coordinates.

    Production: replace with real provider, e.g.:
        Planet API:   https://api.planet.com/data/v1/...
        Sentinel Hub: https://services.sentinel-hub.com/ogc/wms/...
        Google Earth Engine: ee.Image(...).getThumbURL(...)

    MVP: Downloads a placeholder aerial-style image from a public tile server.
    """
    try:
        # Use OpenStreetMap tile as placeholder (shows terrain/satellite context)
        import math
        lat, lng, zoom = project.latitude, project.longitude, 16
        x = int((lng + 180) / 360 * (2 ** zoom))
        y = int((1 - math.log(math.tan(math.radians(lat)) +
                 1 / math.cos(math.radians(lat))) / math.pi) / 2 * (2 ** zoom))
        url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
        headers = {'User-Agent': 'GovTrust-Monitoring/1.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        logger.warning(f"Satellite fetch failed for {project.title}: {e}")
    return None


def _fetch_camera_snapshot(camera_url: str) -> bytes | None:
    """
    Fetch a JPEG snapshot from a government IP camera.

    Production: replace camera_url with actual RTSP/HTTP endpoints:
        http://cam.govsite.ng/axis-cgi/jpg/image.cgi
        rtsp://192.168.1.100/stream1  (use OpenCV: cv2.VideoCapture)

    MVP: Returns None if URL is not reachable (gracefully skipped).
    """
    if not camera_url or camera_url.startswith('rtsp://'):
        return None
    try:
        resp = requests.get(camera_url, timeout=8)
        if resp.status_code == 200 and 'image' in resp.headers.get('Content-Type', ''):
            return resp.content
    except Exception as e:
        logger.warning(f"Camera snapshot failed ({camera_url}): {e}")
    return None


# ── main task functions ─────────────────────────────────────────────────────

def run_satellite_capture(project=None):
    """
    Capture latest satellite image for one or all active projects,
    save as MediaEvidence and trigger AI analysis.
    """
    from projects.models import Project
    from monitoring.models import MediaEvidence
    from monitoring.views import _run_analysis

    projects = [project] if project else Project.objects.filter(status='active')
    captured = 0

    for proj in projects:
        logger.info(f"[SATELLITE] Capturing for: {proj.title}")
        image_bytes = _fetch_satellite_image(proj)
        if not image_bytes:
            logger.warning(f"[SATELLITE] No image returned for {proj.title}")
            continue

        filename = f"sat_{proj.id}_{dj_tz.now().strftime('%Y%m%d_%H%M%S')}.png"
        ev = MediaEvidence(
            project=proj,
            source='satellite',
            captured_at=dj_tz.now(),
            notes=f'Auto-captured by scheduled satellite task at {dj_tz.now().isoformat()}',
        )
        ev.image.save(filename, ContentFile(image_bytes), save=False)
        ev.save()

        _run_analysis(ev)
        captured += 1
        logger.info(f"[SATELLITE] Saved & analysed for {proj.title}")

    return captured


def run_camera_capture(project=None):
    """
    Pull snapshots from all registered on-site cameras for active projects.
    """
    from projects.models import Project
    from monitoring.models import MediaEvidence, SiteCamera
    from monitoring.views import _run_analysis

    projects = [project] if project else Project.objects.filter(status='active')
    captured = 0

    for proj in projects:
        cameras = SiteCamera.objects.filter(project=proj, is_active=True)
        for cam in cameras:
            logger.info(f"[CAMERA] Fetching from {cam.name} — {proj.title}")
            image_bytes = _fetch_camera_snapshot(cam.snapshot_url)
            if not image_bytes:
                continue

            filename = f"cam_{cam.id}_{dj_tz.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            ev = MediaEvidence(
                project=proj,
                source='camera_gov',
                captured_at=dj_tz.now(),
                notes=f'Auto-captured from camera: {cam.name}',
            )
            ev.image.save(filename, ContentFile(image_bytes), save=False)
            ev.save()

            _run_analysis(ev)
            cam.last_capture = dj_tz.now()
            cam.save(update_fields=['last_capture'])
            captured += 1

    return captured


def run_all_monitoring():
    """Entry point called by management command or Celery Beat."""
    logger.info("=== GovTrust Scheduled Monitoring Starting ===")
    sat = run_satellite_capture()
    cam = run_camera_capture()
    logger.info(f"=== Done: {sat} satellite + {cam} camera captures ===")
    return sat + cam
