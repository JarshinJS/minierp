import pytest
from unittest.mock import patch
from decimal import Decimal
from django.contrib.auth import get_user_model
from core.exceptions import WorkflowError, DomainError
from apps.blockchain.models import BlockchainDocument, BlockchainAuditLog, AuditEventTypes
from apps.blockchain.services.hashing_service import generate_file_hash, hash_data
from apps.blockchain.services.web3_service import Web3Service
from apps.blockchain.services.verification_service import anchor_document_to_blockchain, verify_document

User = get_user_model()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(email="test@test.com", password="password123")


class MockDocument:
    def __init__(self):
        self.id = 1
        self.title = "Test Doc"
        self.document_type = "COMMERCIAL_INVOICE"
        self.version = 1
        self.file = type("MockFile", (), {"read": lambda self: b"test content"})()
        self.verification_status = "PENDING"
        
    def save(self, *args, **kwargs):
        pass


@pytest.mark.django_db
class TestHashingService:
    def test_generate_file_hash(self):
        mock_file = type("MockFile", (), {"read": lambda self: b"hello world"})()
        file_hash = generate_file_hash(mock_file)
        assert len(file_hash) == 64  # SHA-256 length

    def test_hash_data(self):
        data_hash = hash_data({"test": "data", "value": 123})
        assert len(data_hash) == 64


@pytest.mark.django_db
class TestWeb3Service:
    def test_singleton_pattern(self):
        w1 = Web3Service()
        w2 = Web3Service()
        assert w1 is w2

    def test_mock_mode_anchor(self):
        web3_service = Web3Service()
        tx_hash, network, block = web3_service.anchor_hash("testhash")
        assert tx_hash.startswith("0xMOCK")
        assert network == "Mock-Network"
        assert block > 0


@pytest.mark.django_db
class TestVerificationService:
    @patch("apps.blockchain.services.verification_service.Web3Service")
    def test_anchor_document(self, MockWeb3Service, test_user):
        mock_web3_instance = MockWeb3Service.return_value
        mock_web3_instance.anchor_hash.return_value = ("0xtesttx", "Test-Network", 100)
        
        doc = MockDocument()
        bc_doc = anchor_document_to_blockchain(doc, user=test_user)
        
        assert bc_doc.document_hash is not None
        assert bc_doc.blockchain_txn == "0xtesttx"
        assert bc_doc.network == "Test-Network"
        assert bc_doc.verified is True
        
        # Verify status update
        assert doc.verification_status == "VERIFIED"
        
        # Verify audit log creation
        assert BlockchainAuditLog.objects.count() == 1
        log = BlockchainAuditLog.objects.first()
        assert log.event_type == AuditEventTypes.DOCUMENT_ANCHORED
        assert log.reference_id == str(doc.id)

    def test_verify_document_success(self, test_user):
        # Setup mock document and DB record
        doc = MockDocument()
        doc_hash = generate_file_hash(doc.file)
        
        bc_doc = BlockchainDocument.objects.create(
            document_id=doc.id,
            document_hash=doc_hash,
            blockchain_txn="0xtest",
            network="Mock",
            verified=True
        )
        
        result = verify_document(doc)
        assert result["verified"] is True
        assert result["status"] == "Valid"

    def test_verify_document_tampered(self):
        # Setup mock document but DB has different hash
        doc = MockDocument()
        
        bc_doc = BlockchainDocument.objects.create(
            document_id=doc.id,
            document_hash="differenthash123",
            blockchain_txn="0xtest",
            network="Mock",
            verified=True
        )
        
        result = verify_document(doc)
        assert result["verified"] is False
        assert result["status"] == "Tampered"
