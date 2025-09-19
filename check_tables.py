#!/usr/bin/env python3
"""
Script to create wallet tables in Heroku database.
"""

from app.core.database import get_db
from sqlalchemy import text


def create_wallet_tables():
    """Create wallet tables in the database."""
    db = next(get_db())

    try:
        # Create wallet_connections table
        print("Creating wallet_connections table...")
        db.execute(text("""
        CREATE TABLE IF NOT EXISTS wallet_connections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES client_companies(id),
            wallet_address VARCHAR NOT NULL,
            wallet_type VARCHAR NOT NULL,
            network VARCHAR NOT NULL,
            wallet_name VARCHAR,
            is_active BOOLEAN DEFAULT TRUE,
            is_verified BOOLEAN DEFAULT FALSE,
            verification_method VARCHAR,
            verification_timestamp TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_activity TIMESTAMP WITH TIME ZONE
        );
        """))

        # Create indexes for wallet_connections
        print("Creating indexes for wallet_connections...")
        db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_wallet_connections_id ON wallet_connections(id);
        CREATE INDEX IF NOT EXISTS ix_wallet_connections_wallet_address ON wallet_connections(wallet_address);
        CREATE INDEX IF NOT EXISTS ix_wallet_connections_company_id ON wallet_connections(company_id);
        CREATE INDEX IF NOT EXISTS idx_company_wallet ON wallet_connections(company_id, wallet_address);
        """))

        # Create unique constraint (check if it exists first)
        print("Creating unique constraint...")
        try:
            db.execute(text("""
            ALTER TABLE wallet_connections ADD CONSTRAINT unique_company_wallet UNIQUE (company_id, wallet_address);
            """))
        except Exception as e:
            if "already exists" in str(e):
                print("Unique constraint already exists, skipping...")
            else:
                raise

        # Create wallet_activities table
        print("Creating wallet_activities table...")
        db.execute(text("""
        CREATE TABLE IF NOT EXISTS wallet_activities (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            wallet_connection_id UUID NOT NULL REFERENCES wallet_connections(id),
            activity_type VARCHAR NOT NULL,
            transaction_hash VARCHAR,
            contract_address VARCHAR,
            chain_id VARCHAR,
            amount NUMERIC,
            token_symbol VARCHAR,
            from_address VARCHAR,
            to_address VARCHAR,
            block_number BIGINT,
            gas_used BIGINT,
            gas_price NUMERIC,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """))

        # Create indexes for wallet_activities
        print("Creating indexes for wallet_activities...")
        db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_wallet_activities_id ON wallet_activities(id);
        CREATE INDEX IF NOT EXISTS ix_wallet_activities_wallet_connection_id ON wallet_activities(wallet_connection_id);
        CREATE INDEX IF NOT EXISTS ix_wallet_activities_transaction_hash ON wallet_activities(transaction_hash);
        CREATE INDEX IF NOT EXISTS ix_wallet_activities_timestamp ON wallet_activities(timestamp);
        """))

        db.commit()
        print("✅ Wallet tables created successfully!")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        db.rollback()
        raise


if __name__ == "__main__":
    create_wallet_tables()

