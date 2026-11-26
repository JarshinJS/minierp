import logging

from django.db import transaction

from apps.blockchain.models import BlockchainDocument, BlockchainAuditLog
from apps.blockchain.services.hashing_service import generate_file_hash, generate_data_hash
from apps.blockchain.services.web3_service import get_web3_service
from apps.foreign_trade.models import DocumentVerificationStatus

logger = logging.getLogger(__name__)


# ===========================================================================
# Document Verification
# ===========================================================================

@transaction.atomic
def register_document(trade_document):
    """
    Register a trade document on the blockchain.
    Steps:
      1. Generate SHA-256 hash of the file
      2. Submit hash to blockchain
      3. Create BlockchainDocument record linking doc → txn
    """
    # Step 1: Hash the file
    doc_hash = generate_file_hash(trade_document.file)

    # Step 2: Submit to blockchain
    web3_svc = get_web3_service()
    txn_hash = web3_svc.submit_data_hash(doc_hash)

    # Get block number if available
    txn_details = web3_svc.get_transaction(txn_hash)
    block_number = txn_details.get("block_number") if txn_details else None

    network_info = web3_svc.get_network_info()

    # Step 3: Create blockchain record
    bc_doc = BlockchainDocument.objects.create(
        document=trade_document,
        document_hash=doc_hash,
        blockchain_txn=txn_hash,
        network=network_info.get("network_name", "unknown"),
        block_number=block_number,
        verified=True,
    )

    # Update document verification status
    trade_document.verification_status = DocumentVerificationStatus.VERIFIED
    trade_document.save(update_fields=["verification_status"])

    logger.info(
        "Document %s registered on blockchain: hash=%s txn=%s",
        trade_document.id, doc_hash, txn_hash,
    )
    return bc_doc


def verify_document(trade_document):
    """
    Verify a trade document against its blockchain record.
    Steps:
      1. Re-hash the current file
      2. Find the blockchain record
      3. Compare hashes (and optionally verify on-chain)
      4. Update verification status
    Returns a dict with verification result.
    """
    # Step 1: Re-hash the current file
    current_hash = generate_file_hash(trade_document.file)

    # Step 2: Find the latest blockchain record
    bc_record = BlockchainDocument.objects.filter(
        document=trade_document
    ).order_by("-created_at").first()

    if not bc_record:
        trade_document.verification_status = DocumentVerificationStatus.UNVERIFIED
        trade_document.save(update_fields=["verification_status"])
        return {
            "verified": False,
            "status": "UNVERIFIED",
            "message": "No blockchain record found for this document.",
            "current_hash": current_hash,
            "stored_hash": None,
        }

    # Step 3: Compare hashes
    hashes_match = current_hash == bc_record.document_hash

    # Optionally verify on-chain as well
    web3_svc = get_web3_service()
    on_chain = web3_svc.verify_data_hash(bc_record.blockchain_txn, current_hash)

    is_verified = hashes_match and on_chain.get("verified", False)

    # Step 4: Update status
    if is_verified:
        trade_document.verification_status = DocumentVerificationStatus.VERIFIED
        bc_record.verified = True
    else:
        trade_document.verification_status = DocumentVerificationStatus.TAMPERED
        bc_record.verified = False

    trade_document.save(update_fields=["verification_status"])
    bc_record.save(update_fields=["verified"])

    result = {
        "verified": is_verified,
        "status": trade_document.verification_status,
        "message": "Document verified ✓" if is_verified else "Document may have been tampered with ✗",
        "current_hash": current_hash,
        "stored_hash": bc_record.document_hash,
        "blockchain_txn": bc_record.blockchain_txn,
        "network": bc_record.network,
        "block_number": bc_record.block_number,
    }

    logger.info(
        "Document %s verification: %s (current=%s stored=%s)",
        trade_document.id,
        "PASS" if is_verified else "FAIL",
        current_hash[:12],
        bc_record.document_hash[:12],
    )
    return result


# ===========================================================================
# Audit Trail
# ===========================================================================

@transaction.atomic
def log_audit_event(event_type, reference_id, reference_model="", user=None, metadata=None):
    """
    Log a critical business event to the blockchain audit trail.
    Steps:
      1. Hash the event data
      2. Submit hash to blockchain
      3. Create BlockchainAuditLog record
    """
    event_data = {
        "event_type": event_type,
        "reference_id": str(reference_id),
        "reference_model": reference_model,
        "metadata": metadata or {},
    }

    # Step 1: Hash event data
    data_hash = generate_data_hash(event_data)

    # Step 2: Submit to blockchain
    web3_svc = get_web3_service()
    txn_hash = web3_svc.submit_data_hash(data_hash)

    txn_details = web3_svc.get_transaction(txn_hash)
    block_number = txn_details.get("block_number") if txn_details else None
    network_info = web3_svc.get_network_info()

    # Step 3: Create audit log record
    audit_log = BlockchainAuditLog.objects.create(
        event_type=event_type,
        reference_id=str(reference_id),
        reference_model=reference_model,
        data_hash=data_hash,
        blockchain_txn=txn_hash,
        network=network_info.get("network_name", "unknown"),
        block_number=block_number,
        created_by=user,
        metadata=metadata or {},
    )

    logger.info(
        "Audit event logged: %s for %s txn=%s",
        event_type, reference_id, txn_hash,
    )
    return audit_log


def verify_audit_event(audit_log):
    """
    Verify that a blockchain audit log entry has not been tampered with.
    Re-hashes the event data and compares with the stored and on-chain hash.
    """
    event_data = {
        "event_type": audit_log.event_type,
        "reference_id": audit_log.reference_id,
        "reference_model": audit_log.reference_model,
        "metadata": audit_log.metadata or {},
    }
    current_hash = generate_data_hash(event_data)
    hashes_match = current_hash == audit_log.data_hash

    web3_svc = get_web3_service()
    on_chain = web3_svc.verify_data_hash(audit_log.blockchain_txn, current_hash)

    return {
        "verified": hashes_match and on_chain.get("verified", False),
        "current_hash": current_hash,
        "stored_hash": audit_log.data_hash,
        "on_chain_result": on_chain,
    }
