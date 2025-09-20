"""
Web3 signature verification utilities for wallet authentication.
"""

import time
import re
from typing import Optional, Tuple
from eth_account import Account
from eth_account.messages import encode_defunct


def verify_signature(wallet_address: str, message: str, signature: str) -> bool:
    """
    Verify that a signature was created by the wallet owner.
    
    Args:
        wallet_address: The Ethereum wallet address (0x...)
        message: The original message that was signed
        signature: The signature to verify (0x...)
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        # Encode the message in the same format as MetaMask
        message_hash = encode_defunct(text=message)
        
        # Recover the address from the signature
        recovered_address = Account.recover_message(message_hash, signature=signature)
        
        # Compare addresses (case-insensitive)
        return recovered_address.lower() == wallet_address.lower()
    
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False


def validate_message_format(message: str, expected_wallet: str, expected_company: str) -> bool:
    """
    Validate that the message follows the expected format.
    
    Expected format:
    Adtivity Wallet Verification
    Wallet: 0x...
    Company: uuid
    Timestamp(ms): 1234567890
    Nonce: ...
    
    Args:
        message: The message to validate
        expected_wallet: The expected wallet address
        expected_company: The expected company ID
    
    Returns:
        bool: True if format is valid, False otherwise
    """
    try:
        lines = message.strip().split('\n')
        
        # Check we have exactly 5 lines
        if len(lines) != 5:
            return False
        
        # Check each line format
        if lines[0].strip() != "Adtivity Wallet Verification":
            return False
        
        # Check wallet line
        wallet_match = re.match(r'^Wallet: (0x[a-fA-F0-9]{40})$', lines[1].strip())
        if not wallet_match or wallet_match.group(1).lower() != expected_wallet.lower():
            return False
        
        # Check company line
        company_match = re.match(r'^Company: ([a-f0-9-]{36})$', lines[2].strip())
        if not company_match or company_match.group(1) != expected_company:
            return False
        
        # Check timestamp line
        timestamp_match = re.match(r'^Timestamp\(ms\): (\d+)$', lines[3].strip())
        if not timestamp_match:
            return False
        
        # Check nonce line
        if not lines[4].strip().startswith('Nonce: '):
            return False
        
        return True
    
    except Exception as e:
        print(f"Message format validation error: {e}")
        return False


def is_signature_recent(timestamp_ms: int, max_age_minutes: int = 5) -> bool:
    """
    Check if a signature is recent enough to be valid.
    
    Args:
        timestamp_ms: Timestamp from the message in milliseconds
        max_age_minutes: Maximum age in minutes (default: 5 minutes)
    
    Returns:
        bool: True if signature is recent, False otherwise
    """
    try:
        current_time_ms = int(time.time() * 1000)
        age_ms = current_time_ms - timestamp_ms
        max_age_ms = max_age_minutes * 60 * 1000
        
        return age_ms >= 0 and age_ms <= max_age_ms
    
    except Exception as e:
        print(f"Timestamp validation error: {e}")
        return False


def extract_timestamp_from_message(message: str) -> Optional[int]:
    """
    Extract timestamp from the verification message.
    
    Args:
        message: The verification message
    
    Returns:
        int: Timestamp in milliseconds, or None if not found
    """
    try:
        lines = message.strip().split('\n')
        if len(lines) >= 4:
            timestamp_match = re.match(r'^Timestamp\(ms\): (\d+)$', lines[3].strip())
            if timestamp_match:
                return int(timestamp_match.group(1))
    except Exception as e:
        print(f"Timestamp extraction error: {e}")
    
    return None


def verify_wallet_ownership(
    wallet_address: str, 
    message: str, 
    signature: str, 
    expected_company: str
) -> Tuple[bool, str]:
    """
    Complete wallet ownership verification.
    
    Args:
        wallet_address: The wallet address to verify
        message: The signed message
        signature: The signature
        expected_company: The expected company ID
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # 1. Validate message format
    if not validate_message_format(message, wallet_address, expected_company):
        return False, "Invalid message format"
    
    # 2. Check signature freshness
    timestamp = extract_timestamp_from_message(message)
    if timestamp is None:
        return False, "Invalid timestamp in message"
    
    if not is_signature_recent(timestamp):
        return False, "Signature is too old"
    
    # 3. Verify signature
    if not verify_signature(wallet_address, message, signature):
        return False, "Invalid signature"
    
    return True, "Wallet ownership verified"

