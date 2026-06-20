import logging
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)


class Web3ServiceError(Exception):
    """Raised when a Web3 operation fails."""
    pass


class MockWeb3Service:
    """
    In-memory mock that simulates blockchain operations.
    Used when WEB3_PROVIDER_URL is not configured or BLOCKCHAIN_MOCK_MODE is True.
    """

    def __init__(self):
        self._transactions = {}
        self._block_counter = 1000
        self.network_name = "mock-network"
        self.chain_id = 0

    def is_connected(self):
        return True

    def get_network_info(self):
        return {
            "chain_id": self.chain_id,
            "network_name": self.network_name,
            "is_mock": True,
        }

    def submit_data_hash(self, data_hash):
        """Simulate submitting a hash to the blockchain."""
        txn_hash = f"0x{uuid.uuid4().hex}"
        self._block_counter += 1
        self._transactions[txn_hash] = {
            "hash": txn_hash,
            "input_data": data_hash,
            "block_number": self._block_counter,
            "status": 1,  # success
        }
        logger.info("Mock blockchain: stored hash %s in tx %s", data_hash, txn_hash)
        return txn_hash

    def get_transaction(self, txn_hash):
        """Retrieve a mock transaction."""
        txn = self._transactions.get(txn_hash)
        if not txn:
            return None
        return txn

    def verify_data_hash(self, txn_hash, expected_hash):
        """Verify a hash against mock stored data."""
        txn = self.get_transaction(txn_hash)
        if not txn:
            return {"verified": False, "reason": "Transaction not found"}
        stored_hash = txn.get("input_data", "")
        is_match = stored_hash == expected_hash
        return {
            "verified": is_match,
            "stored_hash": stored_hash,
            "expected_hash": expected_hash,
            "reason": "Match" if is_match else "Hash mismatch",
        }


class LiveWeb3Service:
    """
    Real Web3 service that connects to a Polygon (or compatible) network.
    Requires WEB3_PROVIDER_URL, BLOCKCHAIN_WALLET_ADDRESS, and BLOCKCHAIN_WALLET_PRIVATE_KEY.
    """

    def __init__(self):
        try:
            from web3 import Web3
        except ImportError:
            raise Web3ServiceError(
                "web3 package is not installed. Run: pip install web3"
            )

        provider_url = getattr(settings, "WEB3_PROVIDER_URL", "")
        if not provider_url:
            raise Web3ServiceError("WEB3_PROVIDER_URL is not configured.")

        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        if not self.w3.is_connected():
            raise Web3ServiceError(f"Cannot connect to Web3 provider: {provider_url}")

        self.wallet_address = getattr(settings, "BLOCKCHAIN_WALLET_ADDRESS", "")
        self.network_name = getattr(settings, "BLOCKCHAIN_NETWORK_NAME", "polygon-amoy")
        self.chain_id = self.w3.eth.chain_id
        logger.info("Web3 connected to %s (chain %d)", self.network_name, self.chain_id)

    def is_connected(self):
        return self.w3.is_connected()

    def get_network_info(self):
        return {
            "chain_id": self.chain_id,
            "network_name": self.network_name,
            "is_mock": False,
        }

    def submit_data_hash(self, data_hash):
        """Submit a SHA-256 hash to the blockchain as transaction input data."""
        from web3 import Web3
        import os

        private_key = os.getenv("BLOCKCHAIN_WALLET_PRIVATE_KEY", "")
        if not private_key:
            raise Web3ServiceError("BLOCKCHAIN_WALLET_PRIVATE_KEY is not set.")
        if not self.wallet_address:
            raise Web3ServiceError("BLOCKCHAIN_WALLET_ADDRESS is not set.")

        try:
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            txn = {
                "nonce": nonce,
                "to": self.wallet_address,  # Self-transfer
                "value": 0,
                "gas": 25000,
                "gasPrice": self.w3.eth.gas_price,
                "data": Web3.to_bytes(text=data_hash),
                "chainId": self.chain_id,
            }
            signed = self.w3.eth.account.sign_transaction(txn, private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            txn_hash = receipt.transactionHash.hex()
            logger.info("Blockchain tx submitted: %s (block %d)", txn_hash, receipt.blockNumber)
            return txn_hash
        except Exception as e:
            logger.error("Blockchain transaction failed: %s", str(e))
            raise Web3ServiceError(f"Transaction failed: {str(e)}")

    def get_transaction(self, txn_hash):
        """Retrieve transaction details from the blockchain."""
        try:
            from web3 import Web3
            txn = self.w3.eth.get_transaction(txn_hash)
            return {
                "hash": txn.hash.hex(),
                "input_data": txn.input.hex() if txn.input else "",
                "block_number": txn.blockNumber,
                "status": 1,
            }
        except Exception as e:
            logger.error("Failed to retrieve tx %s: %s", txn_hash, str(e))
            return None

    def verify_data_hash(self, txn_hash, expected_hash):
        """Verify that the hash stored on-chain matches the expected hash."""
        txn = self.get_transaction(txn_hash)
        if not txn:
            return {"verified": False, "reason": "Transaction not found"}

        from web3 import Web3
        stored_data = bytes.fromhex(txn["input_data"].lstrip("0x")) if txn["input_data"] else b""
        try:
            stored_hash = stored_data.decode("utf-8")
        except UnicodeDecodeError:
            stored_hash = stored_data.hex()

        is_match = stored_hash == expected_hash
        return {
            "verified": is_match,
            "stored_hash": stored_hash,
            "expected_hash": expected_hash,
            "reason": "Match" if is_match else "Hash mismatch",
        }


# ---------------------------------------------------------------------------
# Factory — returns the right implementation
# ---------------------------------------------------------------------------

_service_instance = None


def get_web3_service():
    """
    Returns a singleton Web3Service instance.
    Uses MockWeb3Service when BLOCKCHAIN_MOCK_MODE is True or Web3 is unavailable.
    """
    global _service_instance
    if _service_instance is not None:
        return _service_instance

    mock_mode = getattr(settings, "BLOCKCHAIN_MOCK_MODE", True)
    if mock_mode:
        logger.info("Blockchain running in MOCK mode.")
        _service_instance = MockWeb3Service()
        return _service_instance

    try:
        _service_instance = LiveWeb3Service()
    except (Web3ServiceError, ImportError) as e:
        logger.warning("Falling back to mock Web3: %s", str(e))
        _service_instance = MockWeb3Service()

    return _service_instance


def reset_web3_service():
    """Reset the singleton (useful for testing)."""
    global _service_instance
    _service_instance = None
