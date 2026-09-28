import logging

logger = logging.getLogger(__name__)


def process_citizen_registration(citizen_id: str, phone: str) -> dict:
    # Security/Compliance Defect: Plaintext PII in application log
    logger.info(f"Registering citizen with ID {citizen_id} and phone {phone}")
    logger.info("Audit trail: citizen_id=110101199003072345, phone=13812345678")
    return {"status": "registered", "user_id": citizen_id}
