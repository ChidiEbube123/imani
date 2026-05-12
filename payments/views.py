import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from rest_framework.decorators import api_view
from rest_framework.response import Response

from projects.models import Project, ProjectMilestone
from monitoring.models import ProjectCompletionSnapshot
from .models import Payment, PaymentAuditLog
from blockchain_ledger.chain import record_payment_event


def payment_list(request):
    payments = Payment.objects.select_related('project', 'project__contractor').order_by('-created_at')
    return render(request, 'payments/payment_list.html', {'payments': payments})


def payment_detail(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    logs = payment.audit_logs.order_by('timestamp')
    return render(request, 'payments/payment_detail.html', {
        'payment': payment, 'logs': logs
    })


def approve_payment(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == 'POST' and payment.status == 'pending':
        payment.status = 'approved'
        payment.approved_by = request.user if request.user.is_authenticated else None
        payment.save()

        PaymentAuditLog.objects.create(
            payment=payment,
            action='APPROVED',
            performed_by=request.user if request.user.is_authenticated else None,
            details={'completion_pct': payment.completion_at_trigger},
        )

        # Record on blockchain & release
        tx_hash = record_payment_event(payment)
        payment.blockchain_tx_hash = tx_hash
        payment.status = 'released'
        payment.released_at = timezone.now()
        payment.save()

        # Update project amount paid
        project = payment.project
        project.amount_paid = (project.amount_paid or 0) + payment.amount
        project.save(update_fields=['amount_paid'])

        PaymentAuditLog.objects.create(
            payment=payment,
            action='RELEASED',
            performed_by=request.user if request.user.is_authenticated else None,
            details={'blockchain_tx': tx_hash, 'amount': str(payment.amount)},
        )
        messages.success(request, f'Payment ₦{payment.amount:,.2f} released. TX: {tx_hash[:20]}...')
    return redirect('payment_detail', pk=pk)


def _create_milestone_payment(project, milestone, snapshot):
    """Called automatically when a milestone is achieved."""
    amount = (milestone.payment_percentage / 100) * project.total_budget
    reference = f"PAY-{project.id}-{milestone.id}-{uuid.uuid4().hex[:8].upper()}"
    payment = Payment.objects.create(
        project=project,
        milestone=milestone,
        snapshot=snapshot,
        amount=amount,
        completion_at_trigger=project.completion_percentage,
        reference=reference,
        notes=f'Auto-triggered: {milestone.title} @ {project.completion_percentage:.1f}%',
    )
    PaymentAuditLog.objects.create(
        payment=payment,
        action='AUTO_CREATED',
        details={
            'milestone': milestone.title,
            'trigger_pct': project.completion_percentage,
            'amount': str(amount),
        },
    )
    return payment


@api_view(['GET'])
def payment_stats_api(request):
    from django.db.models import Sum, Count
    stats = Payment.objects.aggregate(
        total_released=Sum('amount', filter=models.Q(status='released')),
        total_pending=Sum('amount', filter=models.Q(status='pending')),
        count_released=Count('id', filter=models.Q(status='released')),
        count_pending=Count('id', filter=models.Q(status='pending')),
    )
    return Response(stats)


import django.db.models as models
