from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.db.models import Sum
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Project, Contractor, ProjectMilestone


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
        'projects': projects[:10],
        'stats': stats,
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
    evidence = project.evidence.order_by('-uploaded_at')[:5]
    payments = project.payments.order_by('-created_at')[:5]
    snapshots = project.snapshots.order_by('-snapshot_date')[:10]
    milestones = project.milestones.order_by('target_percentage')
    return render(request, 'projects/project_detail.html', {
        'project': project,
        'evidence': evidence,
        'payments': payments,
        'snapshots': snapshots,
        'milestones': milestones,
    })


def project_create(request):
    contractors = Contractor.objects.all()
    if request.method == 'POST':
        try:
            project = Project.objects.create(
                title=request.POST['title'],
                project_type=request.POST['project_type'],
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
            # Auto-create standard milestones
            milestones = [
                ('Foundation Complete', 25, 20),
                ('Structure Complete', 50, 25),
                ('Roofing Complete', 70, 25),
                ('Finishing Complete', 90, 20),
                ('Project Complete', 100, 10),
            ]
            for title, target_pct, payment_pct in milestones:
                ProjectMilestone.objects.create(
                    project=project,
                    title=title,
                    description=f'Auto milestone: {title}',
                    target_percentage=target_pct,
                    payment_percentage=payment_pct,
                )
            messages.success(request, f'Project "{project.title}" created with standard milestones.')
            return redirect('project_detail', pk=project.pk)
        except Exception as e:
            messages.error(request, f'Error creating project: {e}')

    return render(request, 'projects/project_create.html', {
        'contractors': contractors,
        'project_types': Project.PROJECT_TYPES,
    })


def contractor_list(request):
    contractors = Contractor.objects.annotate(
        project_count=models.Count('projects')
    ).order_by('name')
    return render(request, 'projects/contractor_list.html', {'contractors': contractors})


def contractor_create(request):
    if request.method == 'POST':
        Contractor.objects.create(
            name=request.POST['name'],
            company=request.POST['company'],
            email=request.POST['email'],
            phone=request.POST['phone'],
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
        'location_name', 'contractor__name',
    )
    return Response(list(projects))


import django.db.models as models
