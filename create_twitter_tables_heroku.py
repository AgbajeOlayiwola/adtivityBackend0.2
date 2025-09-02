#!/usr/bin/env python3
"""Python script to create Twitter integration tables on Heroku."""

import os
import sys
from datetime import datetime

def create_twitter_tables_heroku():
    """Create Twitter integration tables on Heroku using DATABASE_URL."""

    # Get database URL from Heroku environment
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL environment variable not found!")
        print("💡 Make sure you're running this on Heroku or have DATABASE_URL set")
        return

    # Check if we're on Heroku
    print(f"🌐 Environment: {'Heroku' if os.getenv('DYNO') else 'Local'}")
    print(f"📊 Database URL: {database_url[:20]}...")

    try:
        # Try to import SQLAlchemy and PostgreSQL dependencies
        from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Boolean, DateTime, Text, Date, Float, UniqueConstraint
        from sqlalchemy.dialects.postgresql import JSONB
        print("✅ SQLAlchemy and PostgreSQL dependencies loaded successfully")
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("💡 Installing required packages...")
        
        # Try to install psycopg2-binary if missing
        try:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
            print("✅ psycopg2-binary installed successfully")
            
            # Re-import after installation
            from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, String, Boolean, DateTime, Text, Date, Float, UniqueConstraint
            from sqlalchemy.dialects.postgresql import JSONB
        except Exception as install_error:
            print(f"❌ Failed to install dependencies: {install_error}")
            print("💡 Please run: pip install psycopg2-binary sqlalchemy")
            return

    try:
        # Create engine with explicit PostgreSQL dialect
        if database_url.startswith('postgres://'):
            # Heroku uses postgres:// but SQLAlchemy expects postgresql://
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        engine = create_engine(database_url, echo=False)
        print("🔗 Connected to Heroku PostgreSQL database")

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ PostgreSQL version: {version.split(',')[0]}")

    except Exception as e:
        print(f"❌ Failed to connect to Heroku database: {e}")
        print("💡 Make sure DATABASE_URL is correct and database is accessible")
        print(f"💡 Current DATABASE_URL: {database_url}")
        return

    # Create tables
    metadata = MetaData()

    # Company Twitter table
    company_twitter = Table(
        'company_twitter', metadata,
        Column('id', Integer, primary_key=True, index=True),
        Column('company_id', Integer, nullable=False, index=True),
        Column('twitter_handle', String, nullable=False, unique=True, index=True),
        Column('twitter_user_id', String, nullable=True, index=True),
        Column('followers_count', Integer, default=0),
        Column('following_count', Integer, default=0),
        Column('tweets_count', Integer, default=0),
        Column('profile_image_url', String, nullable=True),
        Column('description', Text, nullable=True),
        Column('verified', Boolean, default=False),
        Column('last_updated', DateTime(timezone=True), default=datetime.utcnow),
        Column('created_at', DateTime(timezone=True), default=datetime.utcnow)
    )

    # Twitter Tweets table
    twitter_tweets = Table(
        'twitter_tweets', metadata,
        Column('id', Integer, primary_key=True, index=True),
        Column('tweet_id', String, nullable=False, unique=True, index=True),
        Column('company_twitter_id', Integer, nullable=False, index=True),
        Column('text', Text, nullable=False),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column('retweet_count', Integer, default=0),
        Column('like_count', Integer, default=0),
        Column('reply_count', Integer, default=0),
        Column('quote_count', Integer, default=0),
        Column('hashtags', JSONB, nullable=True),
        Column('mentions', JSONB, nullable=True),
        Column('sentiment_score', Float, nullable=True),
        Column('sentiment_label', String, nullable=True),
        Column('collected_at', DateTime(timezone=True), default=datetime.utcnow)
    )

    # Twitter Followers table
    twitter_followers = Table(
        'twitter_followers', metadata,
        Column('id', Integer, primary_key=True, index=True),
        Column('follower_id', String, nullable=False, index=True),
        Column('company_twitter_id', Integer, nullable=False, index=True),
        Column('username', String, nullable=False, index=True),
        Column('display_name', String, nullable=True),
        Column('profile_image_url', String, nullable=True),
        Column('verified', Boolean, default=False),
        Column('followers_count', Integer, default=0),
        Column('following_count', Integer, default=0),
        Column('tweets_count', Integer, default=0),
        Column('followed_at', DateTime(timezone=True), nullable=True),
        Column('collected_at', DateTime(timezone=True), default=datetime.utcnow)
    )

    # Hashtag Campaigns table
    hashtag_campaigns = Table(
        'hashtag_campaigns', metadata,
        Column('id', Integer, primary_key=True, index=True),
        Column('company_id', Integer, nullable=False, index=True),
        Column('hashtag', String, nullable=False, index=True),
        Column('campaign_name', String, nullable=False),
        Column('description', Text, nullable=True),
        Column('start_date', DateTime(timezone=True), nullable=False),
        Column('end_date', DateTime(timezone=True), nullable=True),
        Column('is_active', Boolean, default=True),
        Column('target_mentions', Integer, default=0),
        Column('current_mentions', Integer, default=0),
        Column('created_at', DateTime(timezone=True), default=datetime.utcnow)
    )

    # Hashtag Mentions table
    hashtag_mentions = Table(
        'hashtag_mentions', metadata,
        Column('id', Integer, primary_key=True, index=True),
        Column('campaign_id', Integer, nullable=False, index=True),
        Column('tweet_id', String, nullable=False, index=True),
        Column('user_id', String, nullable=False, index=True),
        Column('username', String, nullable=False, index=True),
        Column('text', Text, nullable=False),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column('retweet_count', Integer, default=0),
        Column('like_count', Integer, default=0),
        Column('reply_count', Integer, default=0),
        Column('sentiment_score', Float, nullable=True),
        Column('sentiment_label', String, nullable=True),
        Column('collected_at', DateTime(timezone=True), default=datetime.utcnow)
    )

    # Twitter Analytics table
    twitter_analytics = Table(
        'twitter_analytics', metadata,
        Column('id', Integer, primary_key=True, index=True),
        Column('company_twitter_id', Integer, nullable=False, index=True),
        Column('date', Date, nullable=False, index=True),
        Column('total_tweets', Integer, default=0),
        Column('total_likes', Integer, default=0),
        Column('total_retweets', Integer, default=0),
        Column('total_replies', Integer, default=0),
        Column('total_mentions', Integer, default=0),
        Column('followers_gained', Integer, default=0),
        Column('followers_lost', Integer, default=0),
        Column('engagement_rate', Float, default=0.0),
        Column('reach_estimate', Integer, default=0),
        Column('created_at', DateTime(timezone=True), default=datetime.utcnow),
        UniqueConstraint('company_twitter_id', 'date', name='unique_company_date')
    )

    # Create all tables
    print("🔨 Creating Twitter integration tables on Heroku...")
    try:
        metadata.create_all(engine)
        print("✅ Twitter tables created successfully on Heroku!")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return

    # Verify tables exist
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        twitter_tables = [
            'company_twitter', 'twitter_tweets', 'twitter_followers',
            'hashtag_campaigns', 'hashtag_mentions', 'twitter_analytics'
        ]

        print("\n📊 Database tables:")
        for table in twitter_tables:
            if table in tables:
                print(f"  ✅ {table}")
            else:
                print(f"  ❌ {table} - MISSING!")

        # Test connection to new tables
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM company_twitter"))
            count = result.scalar()
            print(f"\n📈 Company Twitter accounts: {count}")

    except Exception as e:
        print(f"⚠️  Warning: Could not verify tables - {e}")

    print("\n🎉 Twitter integration tables created successfully on Heroku!")
    print("🚀 You can now test the Twitter endpoints:")
    print("   - POST /twitter/accounts/")
    print("   - POST /twitter/sync/")
    print("   - GET /twitter/accounts/{id}/tweets")


if __name__ == "__main__":
    print("🚀 Starting Heroku Twitter tables creation...")
    print("📊 Using DATABASE_URL from environment")
    print("-" * 50)

    create_twitter_tables_heroku()
