from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
import django.db.models as models

from .models import Project, Contractor, ProjectMilestone
from .milestone_templates import get_milestones_for_type, MILESTONE_TEMPLATES


def dashboard(request):
    projects = Project.objects.select_related('contractor').order_by('-created_at')
    stats = {
        'total': projects.count(),
        'active': projects.filter(status='active').count(),
        'completed': projects.filter(status='completed').count(),
        'total_budget': projects.aggregate(t=Sum('total_budget'))['t'] or 0,
        'total_paid': projects.aggregate(t=Sum('amount_paid'))['t'] or 0,
    }
    return render(request, 'projects/dashboard.html', {
        'projects': projects[:10], 'stats': stats,
    })


def project_list(request):
    projects = Project.objects.select_related('contractor').order_by('-created_at')
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    if status_filter:
        projects = projects.filter(status=status_filter)
    if type_filter:
        projects = projects.filter(project_type=type_filter)
    return render(request, 'projects/project_list.html', {
        'projects': projects,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'project_types': Project.PROJECT_TYPES,
    })


def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    return render(request, 'projects/project_detail.html', {
        'project': project,
        'evidence': project.evidence.order_by('-uploaded_at')[:5],
        'payments': project.payments.order_by('-created_at')[:5],
        'snapshots': project.snapshots.order_by('-snapshot_date')[:10],
        'milestones': project.milestones.order_by('order'),
    })


def project_create(request):
    contractors = Contractor.objects.all()
    if request.method == 'POST':
        try:
            project_type = request.POST['project_type']
            project = Project.objects.create(
                title=request.POST['title'],
                project_type=project_type,
                description=request.POST['description'],
                contractor_id=request.POST['contractor'],
                location_name=request.POST['location_name'],
                latitude=float(request.POST['latitude']),
                longitude=float(request.POST['longitude']),
                total_budget=float(request.POST['total_budget']),
                start_date=request.POST['start_date'],
                expected_end_date=request.POST['expected_end_date'],
                status='active',
                created_by=request.user if request.user.is_authenticated else None,
            )
            # Create type-specific milestones
            milestones = get_milestones_for_type(project_type)
            for m in milestones:
                ProjectMilestone.objects.create(project=project, **m)

            messages.success(
                request,
                f'Project "{project.title}" created with {len(milestones)} '
                f'{project.get_project_type_display()} milestones.'
            )
            return redirect('project_detail', pk=project.pk)
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'projects/project_create.html', {
        'contractors': contractors,
        'project_types': Project.PROJECT_TYPES,
        'milestone_templates': {k: v for k, v in MILESTONE_TEMPLATES.items()},
    })


def contractor_list(request):
    contractors = Contractor.objects.annotate(
        project_count=Count('projects')
    ).order_by('name')
    return render(request, 'projects/contractor_list.html', {'contractors': contractors})


def contractor_create(request):
    if request.method == 'POST':
        Contractor.objects.create(
            name=request.POST['name'], company=request.POST['company'],
            email=request.POST['email'], phone=request.POST['phone'],
            bank_account=request.POST['bank_account'],
            registration_number=request.POST['registration_number'],
        )
        messages.success(request, 'Contractor registered.')
        return redirect('contractor_list')
    return render(request, 'projects/contractor_create.html')


@api_view(['GET'])
def projects_api(request):
    projects = Project.objects.select_related('contractor').values(
        'id', 'title', 'status', 'completion_percentage',
        'total_budget', 'amount_paid', 'latitude', 'longitude',
        'location_name', 'contractor__name', 'project_type',
    )
    return Response(list(projects))


@api_view(['GET'])
def milestone_template_api(request, project_type):
    """Return milestone template for a project type — used by JS on create form."""
    milestones = get_milestones_for_type(project_type)
    return Response(milestones)
