"""Blockchain Explorer Service - Fetches wallet transactions from multiple blockchain explorers."""

import asyncio
import httpx
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from decimal import Decimal
import json

logger = logging.getLogger(__name__)


class BlockchainExplorerService:
    """Service for fetching blockchain data from various explorers."""
    
    def __init__(self):
        from .config import settings
        
        self.etherscan_api_key = settings.ETHERSCAN_API_KEY
        self.alchemy_api_key = settings.ALCHEMY_API_KEY
        self.moralis_api_key = settings.MORALIS_API_KEY
        
        # API endpoints
        self.etherscan_base_url = "https://api.etherscan.io/api"
        self.alchemy_base_url = "https://eth-mainnet.g.alchemy.com/v2"
        self.moralis_base_url = "https://deep-index.moralis.io/api/v2"
        
        # Rate limiting
        self.rate_limits = {
            'etherscan': {'requests_per_second': 5, 'requests_per_day': 100000},
            'alchemy': {'requests_per_second': 10, 'requests_per_day': 1000000},
            'moralis': {'requests_per_second': 20, 'requests_per_day': 1000000}
        }
    
    async def fetch_wallet_transactions(
        self, 
        wallet_address: str, 
        network: str = "ethereum",
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Fetch wallet transactions from blockchain explorers.
        
        Args:
            wallet_address: The wallet address to fetch transactions for
            network: The blockchain network (ethereum, polygon, bsc, etc.)
            start_block: Starting block number (optional)
            end_block: Ending block number (optional)
            limit: Maximum number of transactions to fetch
            
        Returns:
            List of transaction data dictionaries
        """
        try:
            # Try multiple sources in order of preference
            if network.lower() in ["ethereum", "eth"]:
                return await self._fetch_ethereum_transactions(
                    wallet_address, start_block, end_block, limit
                )
            elif network.lower() in ["polygon", "matic"]:
                return await self._fetch_polygon_transactions(
                    wallet_address, start_block, end_block, limit
                )
            elif network.lower() in ["bsc", "binance"]:
                return await self._fetch_bsc_transactions(
                    wallet_address, start_block, end_block, limit
                )
            else:
                logger.warning(f"Unsupported network: {network}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching transactions for {wallet_address}: {e}")
            return []
    
    async def _fetch_ethereum_transactions(
        self, 
        wallet_address: str, 
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch Ethereum transactions using Etherscan API."""
        
        # Try Etherscan first
        if self.etherscan_api_key:
            try:
                return await self._fetch_from_etherscan(
                    wallet_address, start_block, end_block, limit
                )
            except Exception as e:
                logger.warning(f"Etherscan failed: {e}")
        
        # Fallback to Alchemy
        if self.alchemy_api_key:
            try:
                return await self._fetch_from_alchemy(
                    wallet_address, start_block, end_block, limit
                )
            except Exception as e:
                logger.warning(f"Alchemy failed: {e}")
        
        # Fallback to Moralis
        if self.moralis_api_key:
            try:
                return await self._fetch_from_moralis(
                    wallet_address, start_block, end_block, limit
                )
            except Exception as e:
                logger.warning(f"Moralis failed: {e}")
        
        logger.error("All blockchain explorer APIs failed")
        return []
    
    async def _fetch_from_etherscan(
        self, 
        wallet_address: str, 
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch transactions from Etherscan API."""
        
        params = {
            'module': 'account',
            'action': 'txlist',
            'address': wallet_address,
            'startblock': start_block or 0,
            'endblock': end_block or 99999999,
            'page': 1,
            'offset': min(limit, 10000),
            'sort': 'desc',
            'apikey': self.etherscan_api_key
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.etherscan_base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != '1':
                raise Exception(f"Etherscan API error: {data.get('message', 'Unknown error')}")
            
            transactions = data.get('result', [])
            
            # Process and normalize transaction data
            processed_transactions = []
            for tx in transactions:
                processed_tx = self._process_etherscan_transaction(tx)
                if processed_tx:
                    processed_transactions.append(processed_tx)
            
            return processed_transactions
    
    async def _fetch_from_alchemy(
        self, 
        wallet_address: str, 
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch transactions from Alchemy API."""
        
        url = f"{self.alchemy_base_url}/{self.alchemy_api_key}"
        
        payload = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "alchemy_getAssetTransfers",
            "params": [
                {
                    "fromBlock": hex(start_block) if start_block else "0x0",
                    "toBlock": hex(end_block) if end_block else "latest",
                    "fromAddress": wallet_address,
                    "toAddress": wallet_address,
                    "category": ["external", "erc20", "erc721", "erc1155"],
                    "maxCount": min(limit, 1000),
                    "excludeZeroValue": False
                }
            ]
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            if 'error' in data:
                raise Exception(f"Alchemy API error: {data['error']}")
            
            transfers = data.get('result', {}).get('transfers', [])
            
            # Process and normalize transfer data
            processed_transactions = []
            for transfer in transfers:
                processed_tx = self._process_alchemy_transfer(transfer)
                if processed_tx:
                    processed_transactions.append(processed_tx)
            
            return processed_transactions
    
    async def _fetch_from_moralis(
        self, 
        wallet_address: str, 
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch transactions from Moralis API."""
        
        url = f"{self.moralis_base_url}/{wallet_address}"
        
        params = {
            'chain': 'eth',
            'from_block': start_block or 0,
            'to_block': end_block or 'latest',
            'limit': min(limit, 100)
        }
        
        headers = {
            'X-API-Key': self.moralis_api_key,
            'Content-Type': 'application/json'
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            transactions = response.json()
            
            # Process and normalize transaction data
            processed_transactions = []
            for tx in transactions:
                processed_tx = self._process_moralis_transaction(tx)
                if processed_tx:
                    processed_transactions.append(processed_tx)
            
            return processed_transactions
    
    def _process_etherscan_transaction(self, tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process and normalize Etherscan transaction data."""
        try:
            return {
                'transaction_hash': tx.get('hash', ''),
                'block_number': int(tx.get('blockNumber', 0)),
                'from_address': tx.get('from', ''),
                'to_address': tx.get('to', ''),
                'value': Decimal(tx.get('value', 0)) / Decimal(10**18),  # Convert from wei to ETH
                'gas_used': int(tx.get('gasUsed', 0)),
                'gas_price': int(tx.get('gasPrice', 0)),
                'timestamp': datetime.fromtimestamp(int(tx.get('timeStamp', 0))),
                'status': 'confirmed' if tx.get('isError') == '0' else 'failed',
                'transaction_type': self._determine_transaction_type(tx),
                'network': 'ethereum',
                'transaction_metadata': {
                    'etherscan_data': tx,
                    'method_id': tx.get('methodId', ''),
                    'function_name': tx.get('functionName', ''),
                    'contract_address': tx.get('contractAddress', ''),
                    'input': tx.get('input', ''),
                    'nonce': tx.get('nonce', ''),
                    'transaction_index': tx.get('transactionIndex', '')
                }
            }
        except Exception as e:
            logger.error(f"Error processing Etherscan transaction: {e}")
            return None
    
    def _process_alchemy_transfer(self, transfer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process and normalize Alchemy transfer data."""
        try:
            return {
                'transaction_hash': transfer.get('hash', ''),
                'block_number': int(transfer.get('blockNum', 0), 16) if transfer.get('blockNum') else 0,
                'from_address': transfer.get('from', ''),
                'to_address': transfer.get('to', ''),
                'value': Decimal(transfer.get('value', 0)) / Decimal(10**18),
                'timestamp': datetime.fromisoformat(transfer.get('blockTimestamp', '').replace('Z', '+00:00')),
                'status': 'confirmed',
                'transaction_type': transfer.get('category', 'transfer'),
                'network': 'ethereum',
                'token_address': transfer.get('rawContract', {}).get('address', ''),
                'token_symbol': transfer.get('asset', ''),
                'transaction_metadata': {
                    'alchemy_data': transfer,
                    'category': transfer.get('category', ''),
                    'raw_contract': transfer.get('rawContract', {}),
                    'unique_id': transfer.get('uniqueId', '')
                }
            }
        except Exception as e:
            logger.error(f"Error processing Alchemy transfer: {e}")
            return None
    
    def _process_moralis_transaction(self, tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process and normalize Moralis transaction data."""
        try:
            return {
                'transaction_hash': tx.get('hash', ''),
                'block_number': int(tx.get('block_number', 0)),
                'from_address': tx.get('from_address', ''),
                'to_address': tx.get('to_address', ''),
                'value': Decimal(tx.get('value', 0)) / Decimal(10**18),
                'gas_used': int(tx.get('gas', 0)),
                'gas_price': int(tx.get('gas_price', 0)),
                'timestamp': datetime.fromisoformat(tx.get('block_timestamp', '').replace('Z', '+00:00')),
                'status': 'confirmed',
                'transaction_type': self._determine_transaction_type(tx),
                'network': 'ethereum',
                'transaction_metadata': {
                    'moralis_data': tx,
                    'receipt_status': tx.get('receipt_status', ''),
                    'method': tx.get('method', ''),
                    'input': tx.get('input', '')
                }
            }
        except Exception as e:
            logger.error(f"Error processing Moralis transaction: {e}")
            return None
    
    def _determine_transaction_type(self, tx_data: Dict[str, Any]) -> str:
        """Determine the type of transaction based on the data."""
        # Check for token transfers
        if tx_data.get('tokenSymbol') or tx_data.get('asset'):
            return 'token_transfer'
        
        # Check for contract interactions
        if tx_data.get('contractAddress') or tx_data.get('input'):
            return 'contract_interaction'
        
        # Check for NFT transfers
        if tx_data.get('category') in ['erc721', 'erc1155']:
            return 'nft_transfer'
        
        # Default to simple transfer
        return 'transfer'
    
    async def fetch_token_transfers(
        self, 
        wallet_address: str, 
        token_address: Optional[str] = None,
        network: str = "ethereum",
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch token transfers for a wallet."""
        # This would be implemented similarly to fetch_wallet_transactions
        # but focused on ERC-20/ERC-721/ERC-1155 transfers
        pass
    
    async def get_wallet_balance(self, wallet_address: str, network: str = "ethereum") -> Dict[str, Any]:
        """Get wallet balance and token holdings."""
        # This would fetch current balance and token holdings
        pass


# Create global instance
blockchain_explorer_service = BlockchainExplorerService()
