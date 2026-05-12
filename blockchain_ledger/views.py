from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Block
from .chain import verify_chain


def ledger_view(request):
    blocks = Block.objects.order_by('-index')[:50]
    valid, message = verify_chain()
    return render(request, 'blockchain_ledger/ledger.html', {
        'blocks': blocks, 'valid': valid, 'message': message
    })


@api_view(['GET'])
def chain_status(request):
    valid, message = verify_chain()
    blocks = Block.objects.count()
    return Response({'valid': valid, 'message': message, 'block_count': blocks})


@api_view(['GET'])
def block_detail(request, index):
    try:
        block = Block.objects.get(index=index)
        return Response({
            'index': block.index,
            'timestamp': block.timestamp,
            'data': block.data,
            'hash': block.hash,
            'previous_hash': block.previous_hash,
            'nonce': block.nonce,
        })
    except Block.DoesNotExist:
        return Response({'error': 'Block not found'}, status=404)
