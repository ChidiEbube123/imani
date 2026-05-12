"""
GovTrust Simple Blockchain
---------------------------
Pure Python SHA-256 proof-of-work blockchain for immutable
payment/audit records. No external chain required for MVP.
"""

import hashlib
import json
from datetime import datetime, timezone
from django.conf import settings


def _hash_block(index, timestamp, data, previous_hash, nonce):
    block_string = json.dumps({
        'index': index,
        'timestamp': timestamp,
        'data': data,
        'previous_hash': previous_hash,
        'nonce': nonce,
    }, sort_keys=True)
    return hashlib.sha256(block_string.encode()).hexdigest()


def _proof_of_work(index, timestamp, data, previous_hash, difficulty):
    nonce = 0
    prefix = '0' * difficulty
    while True:
        h = _hash_block(index, timestamp, data, previous_hash, nonce)
        if h.startswith(prefix):
            return nonce, h
        nonce += 1


def get_latest_block():
    from blockchain_ledger.models import Block
    return Block.objects.order_by('-index').first()


def add_block(data: dict) -> 'Block':
    """
    Add a new block to the chain. data should be a JSON-serialisable dict.
    Returns the saved Block instance.
    """
    from blockchain_ledger.models import Block

    latest = get_latest_block()
    if latest is None:
        # Genesis block
        index = 0
        previous_hash = '0' * 64
    else:
        index = latest.index + 1
        previous_hash = latest.hash

    timestamp = datetime.now(timezone.utc).isoformat()
    difficulty = settings.BLOCKCHAIN_DIFFICULTY
    nonce, block_hash = _proof_of_work(index, timestamp, data, previous_hash, difficulty)

    block = Block.objects.create(
        index=index,
        data=data,
        previous_hash=previous_hash,
        hash=block_hash,
        nonce=nonce,
    )
    return block


def verify_chain() -> tuple[bool, str]:
    """Verify the entire chain for integrity."""
    from blockchain_ledger.models import Block

    blocks = Block.objects.order_by('index')
    if not blocks.exists():
        return True, "Empty chain"

    blocks = list(blocks)
    for i, block in enumerate(blocks):
        # Recompute hash
        recomputed = _hash_block(
            block.index,
            block.timestamp.isoformat(),
            block.data,
            block.previous_hash,
            block.nonce,
        )
        if recomputed != block.hash:
            return False, f"Block #{block.index} hash mismatch — CHAIN CORRUPTED"

        if i > 0:
            prev = blocks[i - 1]
            if block.previous_hash != prev.hash:
                return False, f"Block #{block.index} previous_hash mismatch"

    return True, f"Chain of {len(blocks)} blocks is VALID"


def record_payment_event(payment) -> str:
    """Convenience: record a payment on chain, return tx hash."""
    data = {
        'event': 'PAYMENT',
        'reference': payment.reference,
        'project': payment.project.title,
        'contractor': payment.project.contractor.name,
        'amount': str(payment.amount),
        'currency': 'NGN',
        'completion_pct': payment.completion_at_trigger,
        'status': payment.status,
    }
    block = add_block(data)
    return block.hash


def record_analysis_event(analysis) -> str:
    """Record a completion analysis on chain."""
    data = {
        'event': 'ANALYSIS',
        'project': analysis.evidence.project.title,
        'completion_score': analysis.completion_score,
        'confidence': analysis.confidence,
        'model': analysis.model_version,
        'evidence_id': analysis.evidence.id,
    }
    block = add_block(data)
    return block.hash
