from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone

from .models import CitizenProfile
from projects.models import Project
from monitoring.models import MediaEvidence
from monitoring.views import _run_analysis


# ── Auth ────────────────────────────────────────────────────────────────────

def citizen_register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        if password != confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'citizens/register.html', {'post': request.POST})
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return render(request, 'citizens/register.html', {'post': request.POST})
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return render(request, 'citizens/register.html', {'post': request.POST})
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'citizens/register.html', {'post': request.POST})

        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name
        )
        CitizenProfile.objects.create(
            user=user,
            phone=request.POST.get('phone', ''),
            state=request.POST.get('state', ''),
            lga=request.POST.get('lga', ''),
        )
        login(request, user)
        messages.success(request, f'Welcome, {first_name}! You can now submit evidence for projects near you.')
        return redirect('citizen_dashboard')

    return render(request, 'citizens/register.html')


def citizen_login(request):
    if request.user.is_authenticated:
        return redirect('citizen_dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(request.POST.get('next', 'citizen_dashboard'))
        messages.error(request, 'Invalid username or password.')
    return render(request, 'citizens/login.html', {'next': request.GET.get('next', '')})


def citizen_logout(request):
    logout(request)
    return redirect('citizen_login')


# ── Citizen-facing views ────────────────────────────────────────────────────

@login_required(login_url='/citizens/login/')
def citizen_dashboard(request):
    profile, _ = CitizenProfile.objects.get_or_create(user=request.user)
    my_submissions = MediaEvidence.objects.filter(
        uploaded_by=request.user
    ).select_related('project').order_by('-uploaded_at')[:10]

    active_projects = Project.objects.filter(status='active').order_by('-created_at')[:6]

    return render(request, 'citizens/dashboard.html', {
        'profile': profile,
        'submissions': my_submissions,
        'active_projects': active_projects,
    })


def public_project_list(request):
    """Public-facing project list — no login required."""
    projects = Project.objects.select_related('contractor').order_by('-created_at')
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')
    search = request.GET.get('q', '')

    if status_filter:
        projects = projects.filter(status=status_filter)
    if type_filter:
        projects = projects.filter(project_type=type_filter)
    if search:
        projects = projects.filter(title__icontains=search) | \
                   projects.filter(location_name__icontains=search)

    return render(request, 'citizens/project_list.html', {
        'projects': projects,
        'status_filter': status_filter,
        'type_filter': type_filter,
        'search': search,
        'project_types': Project.PROJECT_TYPES,
    })


def public_project_detail(request, pk):
    """Public project detail page — citizens can see progress and submit evidence."""
    project = get_object_or_404(Project, pk=pk)
    milestones = project.milestones.order_by('order')
    recent_evidence = project.evidence.filter(
        status__in=['analyzed', 'verified'],
        is_flagged=False
    ).order_by('-uploaded_at')[:12]
    snapshots = project.snapshots.order_by('-snapshot_date')[:8]

    return render(request, 'citizens/project_detail.html', {
        'project': project,
        'milestones': milestones,
        'recent_evidence': recent_evidence,
        'snapshots': snapshots,
    })


@login_required(login_url='/citizens/login/')
def citizen_upload(request, project_id):
    """Citizens upload crowdsourced evidence for a project."""
    project = get_object_or_404(Project, pk=project_id, status='active')
    profile, _ = CitizenProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        image = request.FILES.get('image')
        if not image:
            messages.error(request, 'Please select an image to upload.')
            return render(request, 'citizens/upload.html', {'project': project})

        # Basic size check — 15 MB max
        if image.size > 15 * 1024 * 1024:
            messages.error(request, 'Image too large. Maximum size is 15 MB.')
            return render(request, 'citizens/upload.html', {'project': project})

        ev = MediaEvidence.objects.create(
            project=project,
            source='camera_crowd',
            image=image,
            uploaded_by=request.user,
            uploader_name=request.user.get_full_name() or request.user.username,
            uploader_phone=profile.phone,
            gps_lat=request.POST.get('gps_lat') or None,
            gps_lng=request.POST.get('gps_lng') or None,
            captured_at=timezone.now(),
            notes=request.POST.get('notes', '').strip(),
        )

        # Run AI analysis
        _run_analysis(ev)

        # Update citizen stats
        profile.total_submissions += 1
        profile.save(update_fields=['total_submissions'])

        messages.success(
            request,
            'Thank you! Your photo has been submitted and analysed. '
            f'Contribution score: {ev.analysis.completion_score:.1f}% completion detected.'
            if hasattr(ev, 'analysis') else
            'Thank you! Your photo has been submitted for review.'
        )
        return redirect('public_project_detail', pk=project_id)

    return render(request, 'citizens/upload.html', {'project': project})


@login_required(login_url='/citizens/login/')
def citizen_profile(request):
    profile, _ = CitizenProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile.phone = request.POST.get('phone', profile.phone)
        profile.state = request.POST.get('state', profile.state)
        profile.lga = request.POST.get('lga', profile.lga)
        profile.bio = request.POST.get('bio', profile.bio)
        profile.save()
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.save()
        messages.success(request, 'Profile updated.')
        return redirect('citizen_profile')

    all_submissions = MediaEvidence.objects.filter(
        uploaded_by=request.user
    ).select_related('project').order_by('-uploaded_at')

    return render(request, 'citizens/profile.html', {
        'profile': profile,
        'submissions': all_submissions,
    })
