from clickhouse_driver import Client  # Official ClickHouse Python driver

# Initialize ClickHouse client (connects to ClickHouse server)
clickhouse_client = Client(host='localhost', port=9000)

# Function to execute a ClickHouse query
def query_clickhouse(query: str):
    return clickhouse_client.execute(query)  # Runs the query and returns results