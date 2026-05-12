from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

from projects.models import Project
from .models import MediaEvidence, AIAnalysisResult, ProjectCompletionSnapshot
from .ai_engine import analyse_evidence, aggregate_project_completion
from blockchain_ledger.chain import record_analysis_event


def evidence_list(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    evidence = project.evidence.order_by('-uploaded_at')
    return render(request, 'monitoring/evidence_list.html', {
        'project': project, 'evidence': evidence
    })


def upload_evidence(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if request.method == 'POST':
        image = request.FILES.get('image')
        if not image:
            messages.error(request, 'Please upload an image.')
            return redirect('upload_evidence', project_id=project_id)

        ev = MediaEvidence.objects.create(
            project=project,
            source=request.POST.get('source', 'camera_crowd'),
            image=image,
            uploaded_by=request.user if request.user.is_authenticated else None,
            uploader_name=request.POST.get('uploader_name', ''),
            uploader_phone=request.POST.get('uploader_phone', ''),
            gps_lat=request.POST.get('gps_lat') or None,
            gps_lng=request.POST.get('gps_lng') or None,
            captured_at=timezone.now(),
            notes=request.POST.get('notes', ''),
        )
        # Run AI analysis immediately (use Celery task in production)
        _run_analysis(ev)
        messages.success(request, 'Evidence uploaded and analysed successfully.')
        return redirect('evidence_list', project_id=project_id)

    return render(request, 'monitoring/upload_evidence.html', {'project': project})


def _run_analysis(evidence: MediaEvidence):
    """Run AI analysis and update project completion."""
    result = analyse_evidence(evidence)
    analysis = AIAnalysisResult.objects.create(evidence=evidence, **result)
    evidence.status = 'analyzed'
    evidence.save()

    # Record on blockchain
    try:
        record_analysis_event(analysis)
    except Exception:
        pass  # Don't fail upload if chain write fails

    # Recompute overall project completion
    project = evidence.project
    new_pct = aggregate_project_completion(project)
    project.completion_percentage = new_pct
    project.save(update_fields=['completion_percentage'])

    # Save snapshot
    snap = ProjectCompletionSnapshot.objects.create(
        project=project,
        completion_percentage=new_pct,
        evidence_count=project.evidence.filter(status='analyzed').count(),
    )

    # Check milestone triggers
    _check_milestones(project, snap)
    return analysis


def _check_milestones(project, snapshot):
    """Check if any milestones have been reached and trigger payments."""
    from payments.views import _create_milestone_payment
    for milestone in project.milestones.filter(achieved=False):
        if project.completion_percentage >= milestone.target_percentage:
            milestone.achieved = True
            milestone.achieved_at = timezone.now()
            milestone.save()
            snapshot.triggered_payment = True
            snapshot.save(update_fields=['triggered_payment'])
            _create_milestone_payment(project, milestone, snapshot)


@api_view(['GET'])
def analysis_api(request, evidence_id):
    ev = get_object_or_404(MediaEvidence, pk=evidence_id)
    if hasattr(ev, 'analysis'):
        a = ev.analysis
        return Response({
            'completion_score': a.completion_score,
            'confidence': a.confidence,
            'stage_scores': a.stage_scores,
            'detected_elements': a.detected_elements,
            'raw_detections': a.raw_detections,
            'model_version': a.model_version,
            'analyzed_at': a.analyzed_at,
        })
    return Response({'error': 'Not yet analyzed'}, status=404)


@api_view(['POST'])
def reanalyse(request, evidence_id):
    ev = get_object_or_404(MediaEvidence, pk=evidence_id)
    if hasattr(ev, 'analysis'):
        ev.analysis.delete()
    analysis = _run_analysis(ev)
    return Response({'completion_score': analysis.completion_score, 'status': 'ok'})
