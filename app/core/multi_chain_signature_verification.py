"""
Multi-chain signature verification for different wallet types.
Supports Ethereum (MetaMask), Solana (Phantom), and other chains.
"""

import time
import re
import base64
import base58
from typing import Optional, Tuple
from eth_account import Account
from eth_account.messages import encode_defunct
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


def verify_ethereum_signature(wallet_address: str, message: str, signature: str) -> bool:
    """
    Verify Ethereum signature (MetaMask, Coinbase Wallet, etc.).
    
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
        print(f"Ethereum signature verification error: {e}")
        return False


def verify_solana_signature(wallet_address: str, message: str, signature: str) -> bool:
    """
    Verify Solana signature (Phantom, Solflare, etc.) using Ed25519 cryptography.
    
    Args:
        wallet_address: The Solana wallet address (base58)
        message: The original message that was signed
        signature: The signature to verify (base58)
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    try:
        # Validate input formats
        if not is_valid_solana_address(wallet_address):
            print("Invalid Solana address format")
            return False
        
        if not is_valid_solana_signature(signature):
            print("Invalid Solana signature format")
            return False
        
        # Decode base58 addresses and signatures
        try:
            public_key_bytes = base58.b58decode(wallet_address)
            signature_bytes = base58.b58decode(signature)
        except Exception as e:
            print(f"Base58 decoding error: {e}")
            return False
        
        # Verify the signature using Ed25519
        try:
            # Create Ed25519 public key from decoded bytes
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            
            # Verify the signature against the message
            public_key.verify(signature_bytes, message.encode('utf-8'))
            
            print("✅ Solana signature verified successfully")
            return True
            
        except InvalidSignature:
            print("❌ Solana signature verification failed: Invalid signature")
            return False
        except Exception as e:
            print(f"❌ Solana signature verification error: {e}")
            return False
    
    except Exception as e:
        print(f"Solana signature verification error: {e}")
        return False


def is_valid_solana_address(address: str) -> bool:
    """Check if address is a valid Solana address format."""
    try:
        # Solana addresses are base58 encoded and typically 32-44 characters
        if len(address) < 32 or len(address) > 44:
            return False
        
        # Basic base58 character check
        import string
        base58_chars = string.ascii_letters + string.digits + "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        return all(c in base58_chars for c in address)
    
    except:
        return False


def is_valid_solana_signature(signature: str) -> bool:
    """Check if signature is a valid Solana signature format."""
    try:
        # Solana signatures are base58 encoded Ed25519 signatures (64 bytes = 88 base58 chars)
        # But they can vary in length due to base58 encoding
        if len(signature) < 80 or len(signature) > 100:
            return False
        
        # Try to decode as base58 to validate format
        try:
            decoded = base58.b58decode(signature)
            # Ed25519 signatures should be 64 bytes
            return len(decoded) == 64
        except:
            return False
    
    except:
        return False


def detect_wallet_type(wallet_address: str) -> str:
    """
    Detect wallet type based on address format.
    
    Args:
        wallet_address: The wallet address to analyze
    
    Returns:
        str: 'ethereum', 'solana', or 'unknown'
    """
    if wallet_address.startswith('0x') and len(wallet_address) == 42:
        return 'ethereum'
    elif is_valid_solana_address(wallet_address):
        return 'solana'
    else:
        return 'unknown'


def verify_signature_multi_chain(wallet_address: str, message: str, signature: str) -> bool:
    """
    Verify signature for any supported wallet type.
    
    Args:
        wallet_address: The wallet address
        message: The signed message
        signature: The signature
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    wallet_type = detect_wallet_type(wallet_address)
    
    if wallet_type == 'ethereum':
        return verify_ethereum_signature(wallet_address, message, signature)
    elif wallet_type == 'solana':
        return verify_solana_signature(wallet_address, message, signature)
    else:
        print(f"Unsupported wallet type for address: {wallet_address}")
        return False


def validate_message_format_multi_chain(message: str, expected_wallet: str, expected_company: str) -> bool:
    """
    Validate message format for any wallet type.
    
    Expected format (7 lines):
    Adtivity Wallet Verification
    Wallet: 0x... or Solana address
    Network: ethereum/solana
    Company: uuid
    ConnectionID: uuid
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
        
        # Check we have exactly 7 lines
        if len(lines) != 7:
            return False
        
        # Check header
        if lines[0].strip() != "Adtivity Wallet Verification":
            return False
        
        # Check wallet line - support both Ethereum and Solana formats
        wallet_match = re.match(r'^Wallet: (.+)$', lines[1].strip())
        if not wallet_match or wallet_match.group(1) != expected_wallet:
            return False
        
        # Check network line
        if not lines[2].strip().startswith('Network: '):
            return False
        
        # Check company line
        company_match = re.match(r'^Company: ([a-f0-9-]{36})$', lines[3].strip())
        if not company_match or company_match.group(1) != expected_company:
            return False
        
        # Check connection ID line
        if not lines[4].strip().startswith('ConnectionID: '):
            return False
        
        # Check timestamp line
        timestamp_match = re.match(r'^Timestamp\(ms\): (\d+)$', lines[5].strip())
        if not timestamp_match:
            return False
        
        # Check nonce line
        if not lines[6].strip().startswith('Nonce: '):
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


def verify_wallet_ownership_multi_chain(
    wallet_address: str, 
    message: str, 
    signature: str, 
    expected_company: str
) -> Tuple[bool, str]:
    """
    Complete wallet ownership verification for any supported chain.
    
    Args:
        wallet_address: The wallet address to verify
        message: The signed message
        signature: The signature
        expected_company: The expected company ID
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # 1. Validate message format
    if not validate_message_format_multi_chain(message, wallet_address, expected_company):
        return False, "Invalid message format"
    
    # 2. Check signature freshness
    timestamp = extract_timestamp_from_message(message)
    if timestamp is None:
        return False, "Invalid timestamp in message"
    
    if not is_signature_recent(timestamp):
        return False, "Signature is too old"
    
    # 3. Verify signature based on wallet type
    if not verify_signature_multi_chain(wallet_address, message, signature):
        return False, "Invalid signature"
    
    return True, "Wallet ownership verified"
