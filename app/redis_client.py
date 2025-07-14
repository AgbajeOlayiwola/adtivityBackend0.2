import redis  # Redis Python client

# Initialize Redis client (connects to Redis server)
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Get a value from Redis cache
def get_from_cache(key: str):
    return redis_client.get(key)  # Returns None if key doesn't exist

# Set a value in Redis cache with TTL (time-to-live in seconds)
def set_in_cache(key: str, value: str, ttl: int = 3600):
    redis_client.setex(key, ttl, value)  # Key expires after `ttl` seconds