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
        
        # Moralis base URLs for different chains
        self.moralis_base_urls = {
            'ethereum': 'https://deep-index.moralis.io/api/v2.2',
            'polygon': 'https://deep-index.moralis.io/api/v2.2',
            'bsc': 'https://deep-index.moralis.io/api/v2.2',
            'arbitrum': 'https://deep-index.moralis.io/api/v2.2',
            'optimism': 'https://deep-index.moralis.io/api/v2.2',
            'base': 'https://deep-index.moralis.io/api/v2.2',
            'avalanche': 'https://deep-index.moralis.io/api/v2.2',
            'solana': 'https://solana-gateway.moralis.io'
        }
        
        # Chain IDs for Moralis
        self.chain_ids = {
            'ethereum': '0x1',
            'polygon': '0x89',
            'bsc': '0x38',
            'arbitrum': '0xa4b1',
            'optimism': '0xa',
            'base': '0x2105',
            'avalanche': '0xa86a',
            'solana': 'solana'
        }
        
        # Etherscan as fallback for Ethereum
        self.etherscan_base_url = "https://api.etherscan.io/api"
        
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
            # Handle Solana with special endpoint
            if network.lower() == 'solana':
                return await self._fetch_solana_transactions(
                    wallet_address, start_block, end_block, limit
                )
            
            # Use Moralis for multi-chain support
            if network.lower() in self.moralis_base_urls:
                return await self._fetch_moralis_transactions(
                    wallet_address, network.lower(), start_block, end_block, limit
                )
            elif network.lower() in ["ethereum", "eth"]:
                # Fallback to Etherscan for Ethereum
                return await self._fetch_ethereum_transactions(
                    wallet_address, start_block, end_block, limit
                )
            else:
                logger.warning(f"Unsupported network: {network}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching transactions for {wallet_address}: {e}")
            return []
    
    async def _fetch_solana_transactions(
        self,
        wallet_address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch transactions from Moralis Solana API."""
        try:
            # Use Solana-specific Moralis endpoint
            base_url = self.moralis_base_urls['solana']
            url = f"{base_url}/account/mainnet/{wallet_address}/portfolio"
            
            headers = {
                'Accept': 'application/json',
                'X-API-Key': self.moralis_api_key
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                
                # Process Solana portfolio data
                processed_transactions = []
                
                # Extract NFT data if available
                nfts = data.get('nfts', [])
                for nft in nfts[:limit]:
                    processed_tx = {
                        'transaction_hash': f"solana_nft_{nft.get('mint', 'unknown')}",
                        'block_number': 0,  # Solana doesn't use block numbers the same way
                        'from_address': wallet_address,
                        'to_address': wallet_address,
                        'value': 0,
                        'gas_used': 0,
                        'gas_price': 0,
                        'timestamp': datetime.utcnow(),
                        'status': 'confirmed',
                        'transaction_type': 'nft_hold',
                        'network': 'solana',
                        'token_address': nft.get('mint', ''),
                        'token_symbol': nft.get('name', ''),
                        'token_name': nft.get('name', ''),
                        'amount': 1,
                        'token_id': nft.get('mint', ''),
                        'transaction_metadata': {
                            'moralis_data': nft,
                            'collection': nft.get('collection', ''),
                            'image': nft.get('image', ''),
                            'description': nft.get('description', '')
                        }
                    }
                    processed_transactions.append(processed_tx)
                
                # Extract token balances if available
                tokens = data.get('tokens', [])
                for token in tokens[:limit]:
                    processed_tx = {
                        'transaction_hash': f"solana_token_{token.get('mint', 'unknown')}",
                        'block_number': 0,
                        'from_address': wallet_address,
                        'to_address': wallet_address,
                        'value': float(token.get('amount', 0)),
                        'gas_used': 0,
                        'gas_price': 0,
                        'timestamp': datetime.utcnow(),
                        'status': 'confirmed',
                        'transaction_type': 'token_balance',
                        'network': 'solana',
                        'token_address': token.get('mint', ''),
                        'token_symbol': token.get('symbol', ''),
                        'token_name': token.get('name', ''),
                        'amount': float(token.get('amount', 0)),
                        'transaction_metadata': {
                            'moralis_data': token,
                            'decimals': token.get('decimals', 0),
                            'price_usd': token.get('price_usd', 0)
                        }
                    }
                    processed_transactions.append(processed_tx)
                
                return processed_transactions
                
        except Exception as e:
            logger.error(f"Failed to fetch Solana transactions: {e}")
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
    
    async def _fetch_moralis_transactions(
        self, 
        wallet_address: str, 
        network: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch transactions from Moralis API for any supported chain."""
        
        base_url = self.moralis_base_urls[network]
        chain_name = self._get_moralis_chain_name(network)
        
        # Use the unified wallet history endpoint
        try:
            url = f"{base_url}/wallets/{wallet_address}/history"
            params = {
                'chain': chain_name,
                'nft_metadata': 'true',
                'order': 'DESC',
                'limit': min(limit, 100)
            }
            
            headers = {
                'Accept': 'application/json',
                'X-API-Key': self.moralis_api_key
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                
                # Process the unified history data
                processed_transactions = []
                for item in data.get('result', []):
                    processed_tx = self._process_moralis_history_item(item, network)
                    if processed_tx:
                        processed_transactions.append(processed_tx)
                
                return processed_transactions
                
        except Exception as e:
            logger.error(f"Failed to fetch Moralis transactions: {e}")
            return []
    
    def _get_moralis_chain_name(self, network: str) -> str:
        """Get Moralis chain name from network."""
        chain_mapping = {
            'ethereum': 'eth',
            'polygon': 'polygon',
            'bsc': 'bsc',
            'arbitrum': 'arbitrum',
            'optimism': 'optimism',
            'base': 'base',
            'avalanche': 'avalanche',
            'solana': 'solana'
        }
        return chain_mapping.get(network, 'eth')
    
    async def _fetch_from_moralis(
        self, 
        wallet_address: str, 
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Fetch transactions from Moralis API (legacy method for Ethereum)."""
        return await self._fetch_moralis_transactions(
            wallet_address, 'ethereum', start_block, end_block, limit
        )
    
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
    
    def _process_moralis_transaction(self, tx: Dict[str, Any], network: str = 'ethereum') -> Optional[Dict[str, Any]]:
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
                'network': network,
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
    
    def _process_moralis_token_transfer(self, transfer: Dict[str, Any], network: str = 'ethereum') -> Optional[Dict[str, Any]]:
        """Process and normalize Moralis token transfer data."""
        try:
            return {
                'transaction_hash': transfer.get('transaction_hash', ''),
                'block_number': int(transfer.get('block_number', 0)),
                'from_address': transfer.get('from_address', ''),
                'to_address': transfer.get('to_address', ''),
                'value': Decimal(transfer.get('value', 0)) / Decimal(10 ** int(transfer.get('decimals', 18))),
                'token_address': transfer.get('address', ''),
                'token_symbol': transfer.get('symbol', ''),
                'token_name': transfer.get('name', ''),
                'timestamp': datetime.fromisoformat(transfer.get('block_timestamp', '').replace('Z', '+00:00')),
                'status': 'confirmed',
                'transaction_type': 'token_transfer',
                'network': network,
                'transaction_metadata': {
                    'moralis_data': transfer,
                    'token_decimals': transfer.get('decimals', 18),
                    'token_logo': transfer.get('logo', ''),
                    'token_thumbnail': transfer.get('thumbnail', '')
                }
            }
        except Exception as e:
            logger.error(f"Error processing Moralis token transfer: {e}")
            return None
    
    def _process_moralis_history_item(self, item: Dict[str, Any], network: str = 'ethereum') -> Optional[Dict[str, Any]]:
        """Process and normalize Moralis unified history item."""
        try:
            # Determine transaction type based on the item
            transaction_type = self._determine_moralis_transaction_type(item)
            
            # Extract common fields
            transaction_hash = item.get('hash', '')
            block_number = int(item.get('block_number', 0))
            timestamp = item.get('block_timestamp', '')
            
            # Convert timestamp to datetime
            if timestamp:
                try:
                    timestamp_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    timestamp_dt = datetime.utcnow()
            else:
                timestamp_dt = datetime.utcnow()
            
            # Build base transaction data
            processed_tx = {
                'transaction_hash': transaction_hash,
                'block_number': block_number,
                'from_address': item.get('from_address', ''),
                'to_address': item.get('to_address', ''),
                'value': Decimal(item.get('value', 0)) / Decimal(10**18),
                'gas_used': int(item.get('receipt_gas_used', 0)),
                'gas_price': int(item.get('gas_price', 0)),
                'timestamp': timestamp_dt,
                'status': 'confirmed' if item.get('receipt_status') == '1' else 'failed',
                'transaction_type': transaction_type,
                'network': network,
                'transaction_metadata': {
                    'moralis_data': item,
                    'method': item.get('method_label', ''),
                    'summary': item.get('summary', ''),
                    'category': item.get('category', ''),
                    'receipt_status': item.get('receipt_status', ''),
                    'transaction_fee': item.get('transaction_fee', ''),
                    'nft_transfers': item.get('nft_transfers', []),
                    'erc20_transfers': item.get('erc20_transfers', []),
                    'native_transfers': item.get('native_transfers', [])
                }
            }
            
            # Process NFT transfers if present
            nft_transfers = item.get('nft_transfers', [])
            if nft_transfers:
                nft = nft_transfers[0]  # Take first NFT transfer
                processed_tx.update({
                    'token_address': nft.get('token_address', ''),
                    'token_symbol': nft.get('contract_type', ''),
                    'token_name': nft.get('normalized_metadata', {}).get('name', ''),
                    'amount': int(nft.get('amount', 1)),
                    'token_id': nft.get('token_id', ''),
                    'collection_logo': nft.get('collection_logo', ''),
                    'direction': nft.get('direction', ''),
                    'verified_collection': nft.get('verified_collection', False)
                })
            
            # Process ERC20 transfers if present
            erc20_transfers = item.get('erc20_transfers', [])
            if erc20_transfers:
                token = erc20_transfers[0]  # Take first ERC20 transfer
                processed_tx.update({
                    'token_address': token.get('address', ''),
                    'token_symbol': token.get('token_symbol', ''),
                    'token_name': token.get('token_name', ''),
                    'amount': Decimal(token.get('value', 0)) / Decimal(10 ** int(token.get('token_decimals', 18))),
                    'amount_formatted': token.get('value_formatted', ''),
                    'direction': token.get('direction', ''),
                    'verified_contract': token.get('verified_contract', False),
                    'security_score': token.get('security_score', 0)
                })
            
            # Process native transfers if present
            native_transfers = item.get('native_transfers', [])
            if native_transfers:
                native = native_transfers[0]  # Take first native transfer
                processed_tx.update({
                    'value': Decimal(native.get('value', 0)) / Decimal(10**18),
                    'value_formatted': native.get('value_formatted', ''),
                    'direction': native.get('direction', ''),
                    'token_symbol': native.get('token_symbol', 'ETH'),
                    'token_logo': native.get('token_logo', '')
                })
            
            return processed_tx
            
        except Exception as e:
            logger.error(f"Error processing Moralis history item: {e}")
            return None
    
    def _determine_moralis_transaction_type(self, item: Dict[str, Any]) -> str:
        """Determine transaction type from Moralis history item."""
        # Check category first
        category = item.get('category', '')
        
        if category == 'nft purchase':
            return 'nft_purchase'
        elif category == 'nft sale':
            return 'nft_sale'
        elif category == 'token receive':
            return 'token_receive'
        elif category == 'token send':
            return 'token_send'
        elif category == 'token swap':
            return 'token_swap'
        elif category == 'airdrop':
            return 'airdrop'
        elif category == 'send':
            return 'send'
        elif category == 'receive':
            return 'receive'
        
        # Check for NFT transfers
        if item.get('nft_transfers'):
            return 'nft_transfer'
        
        # Check for ERC20 transfers
        if item.get('erc20_transfers'):
            return 'token_transfer'
        
        # Check for native transfers
        if item.get('native_transfers'):
            return 'native_transfer'
        
        # Check for contract interactions
        if item.get('method_label'):
            return 'contract_interaction'
        
        # Default to simple transfer
        return 'transfer'
    
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
    
    def get_supported_chains(self) -> List[str]:
        """Get list of supported blockchain networks."""
        return list(self.moralis_base_urls.keys())
    
    def get_chain_info(self, chain: str) -> Dict[str, Any]:
        """Get information about a specific chain."""
        if chain not in self.moralis_base_urls:
            raise Exception(f"Unsupported chain: {chain}")
        
        return {
            'chain': chain,
            'chain_id': self.chain_ids[chain],
            'base_url': self.moralis_base_urls[chain],
            'supported': True
        }
    
    def _detect_chain_from_address(self, address: str) -> str:
        """Detect chain from wallet address format."""
        address_lower = address.lower()
        
        # Ethereum addresses start with 0x and are 42 characters
        if address_lower.startswith('0x') and len(address) == 42:
            return 'ethereum'
        
        # Solana addresses are base58 and typically 32-44 characters
        if not address_lower.startswith('0x') and len(address) >= 32:
            return 'solana'
            
        # Default to Ethereum for now
        return 'ethereum'


# Create global instance
blockchain_explorer_service = BlockchainExplorerService()
