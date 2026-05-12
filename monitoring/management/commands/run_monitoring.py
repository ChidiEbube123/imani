"""
Management command for scheduled satellite + camera capture.

Usage:
  python manage.py run_monitoring              # run once (all active projects)
  python manage.py run_monitoring --satellite  # satellite only
  python manage.py run_monitoring --cameras    # cameras only
  python manage.py run_monitoring --project 5  # specific project

Schedule with cron (every 6 hours):
  0 */6 * * * cd /path/to/project && python manage.py run_monitoring >> /var/log/govtrust_monitor.log 2>&1

Or with Celery Beat — add to settings.py:
  CELERY_BEAT_SCHEDULE = {
      'satellite-capture': {
          'task': 'monitoring.tasks.run_satellite_capture',
          'schedule': crontab(hour='*/6'),
      },
      'camera-capture': {
          'task': 'monitoring.tasks.run_camera_capture',
          'schedule': crontab(minute='*/30'),
      },
  }
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from projects.models import Project


class Command(BaseCommand):
    help = 'Run scheduled satellite and camera monitoring for active projects'

    def add_arguments(self, parser):
        parser.add_argument('--satellite', action='store_true', help='Run satellite capture only')
        parser.add_argument('--cameras', action='store_true', help='Run camera capture only')
        parser.add_argument('--project', type=int, help='Run for a specific project ID only')

    def handle(self, *args, **options):
        from monitoring.scheduled_tasks import (
            run_satellite_capture, run_camera_capture, run_all_monitoring
        )

        project = None
        if options['project']:
            try:
                project = Project.objects.get(pk=options['project'])
                self.stdout.write(f'Targeting project: {project.title}')
            except Project.DoesNotExist:
                raise CommandError(f'Project {options["project"]} not found')

        start = timezone.now()
        self.stdout.write(f'[{start.strftime("%Y-%m-%d %H:%M:%S")}] GovTrust monitoring starting...')

        sat_count = cam_count = 0

        if options['satellite'] and not options['cameras']:
            sat_count = run_satellite_capture(project)
        elif options['cameras'] and not options['satellite']:
            cam_count = run_camera_capture(project)
        else:
            sat_count = run_satellite_capture(project)
            cam_count = run_camera_capture(project)

        elapsed = (timezone.now() - start).seconds
        self.stdout.write(
            self.style.SUCCESS(
                f'Done in {elapsed}s — '
                f'{sat_count} satellite capture(s), {cam_count} camera capture(s).'
            )
        )
