"""Canonical registry of supported external data source types."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

SourceCategory = Literal["relational", "warehouse", "nosql", "storage", "api", "saas"]

ConnectionFieldType = Literal["text", "number", "password", "boolean", "textarea", "select"]


def _field(
    key: str,
    label: str,
    *,
    type: ConnectionFieldType = "text",
    required: bool = False,
    placeholder: str | None = None,
    default: Any = None,
    options: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    field: dict[str, Any] = {"key": key, "label": label, "type": type, "required": required}
    if placeholder:
        field["placeholder"] = placeholder
    if default is not None:
        field["default"] = default
    if options:
        field["options"] = options
    return field


def _sql_host_fields(
    *,
    default_port: int,
    include_ssl: bool = True,
    include_connection_string: bool = True,
) -> list[dict[str, Any]]:
    fields = [
        _field("host", "Host", placeholder="localhost or db.example.com", required=True),
        _field("port", "Port", type="number", default=default_port, required=True),
        _field("database", "Database", required=True),
        _field("username", "Username", required=True),
        _field("password", "Password", type="password", required=True),
    ]
    if include_ssl:
        fields.append(_field("ssl", "Use SSL", type="boolean", default=True))
    if include_connection_string:
        fields.append(
            _field(
                "connection_string",
                "Or connection string",
                placeholder=f"postgresql://user:pass@host:{default_port}/db",
            )
        )
    return fields


def _entry(
    *,
    name: str,
    category: SourceCategory,
    icon: str,
    color: str,
    driver: str,
    connection_fields: list[dict[str, Any]],
    test_query: str | None = None,
    schema_query: str | None = None,
    oauth_vendor: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": name,
        "category": category,
        "icon": icon,
        "color": color,
        "driver": driver,
        "connection_fields": connection_fields,
    }
    if test_query:
        item["test_query"] = test_query
    if schema_query:
        item["schema_query"] = schema_query
    if oauth_vendor:
        item["oauth_vendor"] = oauth_vendor
    return item


DATA_SOURCE_TYPES: dict[str, dict[str, Any]] = {
    # --- Relational ---
    "postgresql": _entry(
        name="PostgreSQL",
        category="relational",
        icon="database",
        color="#336791",
        driver="asyncpg",
        connection_fields=_sql_host_fields(default_port=5432),
        test_query="SELECT 1",
        schema_query="""
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """,
    ),
    "mysql": _entry(
        name="MySQL",
        category="relational",
        icon="database",
        color="#00618A",
        driver="aiomysql",
        connection_fields=_sql_host_fields(default_port=3306, include_ssl=False),
        test_query="SELECT 1",
    ),
    "mariadb": _entry(
        name="MariaDB",
        category="relational",
        icon="database",
        color="#003545",
        driver="aiomysql",
        connection_fields=_sql_host_fields(default_port=3306, include_ssl=False),
        test_query="SELECT 1",
    ),
    "mssql": _entry(
        name="Microsoft SQL Server",
        category="relational",
        icon="database",
        color="#CC2927",
        driver="aioodbc",
        connection_fields=_sql_host_fields(default_port=1433, include_ssl=False)
        + [_field("encrypt", "Encrypt connection", type="boolean", default=True)],
        test_query="SELECT 1",
    ),
    "oracle": _entry(
        name="Oracle Database",
        category="relational",
        icon="database",
        color="#F80000",
        driver="oracledb",
        connection_fields=[
            _field("host", "Host", required=True),
            _field("port", "Port", type="number", default=1521, required=True),
            _field("service_name", "Service name", required=True),
            _field("username", "Username", required=True),
            _field("password", "Password", type="password", required=True),
        ],
        test_query="SELECT 1 FROM DUAL",
    ),
    "sqlite": _entry(
        name="SQLite",
        category="relational",
        icon="database",
        color="#003B57",
        driver="aiosqlite",
        connection_fields=[_field("path", "Database file path", placeholder="/path/to/db.sqlite", required=True)],
        test_query="SELECT 1",
    ),
    "cockroachdb": _entry(
        name="CockroachDB",
        category="relational",
        icon="database",
        color="#6933FF",
        driver="asyncpg",
        connection_fields=_sql_host_fields(default_port=26257),
        test_query="SELECT 1",
    ),
    "planetscale": _entry(
        name="PlanetScale",
        category="relational",
        icon="database",
        color="#000000",
        driver="aiomysql",
        connection_fields=[
            _field("host", "Host", required=True),
            _field("username", "Username", required=True),
            _field("password", "Password", type="password", required=True),
            _field("database", "Database", required=True),
        ],
        test_query="SELECT 1",
    ),
    "neon": _entry(
        name="Neon",
        category="relational",
        icon="database",
        color="#00E599",
        driver="asyncpg",
        connection_fields=[
            _field(
                "connection_string",
                "Connection string",
                placeholder="postgresql://user:pass@ep-xxx.neon.tech/db?sslmode=require",
                required=True,
            ),
        ],
        test_query="SELECT 1",
    ),
    "supabase_db": _entry(
        name="Supabase",
        category="relational",
        icon="database",
        color="#3ECF8E",
        driver="asyncpg",
        connection_fields=[
            _field("project_ref", "Project ref", placeholder="abcdefghijklmnop", required=True),
            _field("password", "Database password", type="password", required=True),
            _field(
                "connection_string",
                "Or direct connection string",
                placeholder="postgresql://postgres:pass@db.xxx.supabase.co:5432/postgres",
            ),
        ],
        test_query="SELECT 1",
    ),
    "rds": _entry(
        name="Amazon RDS",
        category="relational",
        icon="cloud",
        color="#FF9900",
        driver="asyncpg",
        connection_fields=_sql_host_fields(default_port=5432)
        + [
            _field(
                "engine",
                "Engine",
                type="select",
                default="postgresql",
                options=[
                    {"value": "postgresql", "label": "PostgreSQL / Aurora PostgreSQL"},
                    {"value": "mysql", "label": "MySQL / Aurora MySQL"},
                ],
            )
        ],
        test_query="SELECT 1",
    ),
    "cloud_sql": _entry(
        name="Google Cloud SQL",
        category="relational",
        icon="cloud",
        color="#4285F4",
        driver="asyncpg",
        connection_fields=_sql_host_fields(default_port=5432),
        test_query="SELECT 1",
    ),
    "azure_sql": _entry(
        name="Azure SQL Database",
        category="relational",
        icon="cloud",
        color="#0078D4",
        driver="aioodbc",
        connection_fields=_sql_host_fields(default_port=1433, include_ssl=False)
        + [_field("encrypt", "Encrypt connection", type="boolean", default=True)],
        test_query="SELECT 1",
    ),
    # --- Warehouses ---
    "snowflake": _entry(
        name="Snowflake",
        category="warehouse",
        icon="cloud",
        color="#29B5E8",
        driver="snowflake-connector-python",
        connection_fields=[
            _field("account", "Account identifier", placeholder="xy12345.us-east-1", required=True),
            _field("username", "Username", required=True),
            _field("password", "Password", type="password", required=True),
            _field("warehouse", "Warehouse", required=True),
            _field("database", "Database", required=True),
            _field("schema", "Schema", default="PUBLIC"),
        ],
        test_query="SELECT 1",
    ),
    "bigquery": _entry(
        name="Google BigQuery",
        category="warehouse",
        icon="cloud",
        color="#4285F4",
        driver="google-cloud-bigquery",
        connection_fields=[
            _field("project_id", "Project ID", required=True),
            _field("dataset", "Dataset (optional)"),
            _field(
                "credentials_json",
                "Service account JSON",
                type="textarea",
                placeholder="Paste your service account key JSON",
                required=True,
            ),
        ],
        test_query="SELECT 1",
    ),
    "redshift": _entry(
        name="Amazon Redshift",
        category="warehouse",
        icon="cloud",
        color="#205B99",
        driver="redshift_connector",
        connection_fields=_sql_host_fields(default_port=5439, include_ssl=True),
        test_query="SELECT 1",
    ),
    "synapse": _entry(
        name="Azure Synapse Analytics",
        category="warehouse",
        icon="cloud",
        color="#0078D4",
        driver="aioodbc",
        connection_fields=_sql_host_fields(default_port=1433, include_ssl=False),
        test_query="SELECT 1",
    ),
    "databricks": _entry(
        name="Databricks",
        category="warehouse",
        icon="cloud",
        color="#FF3621",
        driver="databricks-sql-connector",
        connection_fields=[
            _field("server_hostname", "Server hostname", required=True),
            _field("http_path", "HTTP path", required=True),
            _field("access_token", "Access token", type="password", required=True),
            _field("catalog", "Catalog"),
            _field("schema", "Schema", default="default"),
        ],
        test_query="SELECT 1",
    ),
    "firebolt": _entry(
        name="Firebolt",
        category="warehouse",
        icon="cloud",
        color="#FFCC00",
        driver="firebolt-sdk",
        connection_fields=[
            _field("account", "Account name", required=True),
            _field("database", "Database", required=True),
            _field("username", "Username", required=True),
            _field("password", "Password", type="password", required=True),
        ],
        test_query="SELECT 1",
    ),
    "clickhouse": _entry(
        name="ClickHouse",
        category="warehouse",
        icon="database",
        color="#FFCC01",
        driver="clickhouse-connect",
        connection_fields=_sql_host_fields(default_port=8123, include_ssl=False),
        test_query="SELECT 1",
    ),
    "duckdb": _entry(
        name="DuckDB",
        category="warehouse",
        icon="database",
        color="#FFF000",
        driver="duckdb",
        connection_fields=[
            _field("path", "Database path", placeholder=":memory: or /path/to/db.duckdb", required=True),
        ],
        test_query="SELECT 1",
    ),
    # --- NoSQL / vector ---
    "mongodb": _entry(
        name="MongoDB",
        category="nosql",
        icon="leaf",
        color="#47A248",
        driver="motor",
        connection_fields=[
            _field(
                "connection_string",
                "Connection string",
                placeholder="mongodb+srv://user:pass@cluster.mongodb.net/db",
                required=True,
            ),
            _field("database", "Database name", required=True),
        ],
        test_query='{"ping": 1}',
    ),
    "firestore": _entry(
        name="Firebase Firestore",
        category="nosql",
        icon="leaf",
        color="#FFCA28",
        driver="google-cloud-firestore",
        connection_fields=[
            _field("project_id", "Project ID", required=True),
            _field("credentials_json", "Service account JSON", type="textarea", required=True),
        ],
    ),
    "dynamodb": _entry(
        name="Amazon DynamoDB",
        category="nosql",
        icon="database",
        color="#FF9900",
        driver="boto3",
        connection_fields=[
            _field("region", "Region", placeholder="us-east-1", required=True),
            _field("access_key_id", "Access Key ID"),
            _field("secret_access_key", "Secret Access Key", type="password"),
            _field("table_prefix", "Table prefix (optional)"),
        ],
    ),
    "couchbase": _entry(
        name="Couchbase",
        category="nosql",
        icon="database",
        color="#EA2328",
        driver="couchbase",
        connection_fields=[
            _field("connection_string", "Connection string", required=True),
            _field("username", "Username", required=True),
            _field("password", "Password", type="password", required=True),
            _field("bucket", "Bucket", required=True),
        ],
    ),
    "cassandra": _entry(
        name="Cassandra",
        category="nosql",
        icon="database",
        color="#1287B1",
        driver="cassandra-driver",
        connection_fields=[
            _field("hosts", "Contact points", placeholder="host1,host2", required=True),
            _field("keyspace", "Keyspace", required=True),
            _field("username", "Username"),
            _field("password", "Password", type="password"),
        ],
    ),
    "elasticsearch": _entry(
        name="Elasticsearch / OpenSearch",
        category="nosql",
        icon="search",
        color="#FEC514",
        driver="elasticsearch",
        connection_fields=[
            _field("url", "Cluster URL", placeholder="https://cluster.es.io:9243", required=True),
            _field("api_key", "API Key", type="password"),
            _field("username", "Username"),
            _field("password", "Password", type="password"),
        ],
    ),
    "redis": _entry(
        name="Redis",
        category="nosql",
        icon="database",
        color="#DC382D",
        driver="redis",
        connection_fields=[
            _field("url", "Redis URL", placeholder="redis://:pass@host:6379/0", required=True),
        ],
        test_query="PING",
    ),
    "pinecone": _entry(
        name="Pinecone",
        category="nosql",
        icon="database",
        color="#000000",
        driver="pinecone",
        connection_fields=[
            _field("api_key", "API Key", type="password", required=True),
            _field("index_name", "Index name", required=True),
            _field("environment", "Environment / region"),
        ],
    ),
    "weaviate": _entry(
        name="Weaviate",
        category="nosql",
        icon="database",
        color="#FAFAFA",
        driver="weaviate",
        connection_fields=[
            _field("url", "Cluster URL", required=True),
            _field("api_key", "API Key", type="password"),
        ],
    ),
    "qdrant": _entry(
        name="Qdrant",
        category="nosql",
        icon="database",
        color="#DC244C",
        driver="qdrant-client",
        connection_fields=[
            _field("url", "Cluster URL", required=True),
            _field("api_key", "API Key", type="password"),
            _field("collection", "Collection"),
        ],
    ),
    "chromadb": _entry(
        name="ChromaDB",
        category="nosql",
        icon="database",
        color="#FF6F61",
        driver="chromadb",
        connection_fields=[
            _field("host", "Host", default="localhost"),
            _field("port", "Port", type="number", default=8000),
            _field("collection", "Collection"),
        ],
    ),
    # --- Storage ---
    "csv_upload": _entry(
        name="CSV / Excel upload",
        category="storage",
        icon="file",
        color="#64748B",
        driver="local",
        connection_fields=[_field("file_url", "File URL or storage path", required=True)],
    ),
    "s3": _entry(
        name="Amazon S3",
        category="storage",
        icon="cloud",
        color="#FF9900",
        driver="boto3",
        connection_fields=[
            _field("bucket", "Bucket name", required=True),
            _field("region", "Region", placeholder="us-east-1", required=True),
            _field("prefix", "Object prefix"),
            _field("access_key_id", "Access Key ID"),
            _field("secret_access_key", "Secret Access Key", type="password"),
            _field(
                "format",
                "File format",
                type="select",
                default="csv",
                options=[
                    {"value": "csv", "label": "CSV"},
                    {"value": "parquet", "label": "Parquet"},
                    {"value": "json", "label": "JSON"},
                    {"value": "jsonl", "label": "JSONL / NDJSON"},
                ],
            ),
        ],
    ),
    "gcs": _entry(
        name="Google Cloud Storage",
        category="storage",
        icon="cloud",
        color="#4285F4",
        driver="google-cloud-storage",
        connection_fields=[
            _field("bucket", "Bucket name", required=True),
            _field("prefix", "Object prefix"),
            _field("credentials_json", "Service account JSON", type="textarea", required=True),
        ],
    ),
    "azure_blob": _entry(
        name="Azure Blob Storage",
        category="storage",
        icon="cloud",
        color="#0078D4",
        driver="azure-storage-blob",
        connection_fields=[
            _field("account_name", "Storage account", required=True),
            _field("container", "Container", required=True),
            _field("sas_token", "SAS token", type="password"),
            _field("connection_string", "Or connection string", type="password"),
        ],
    ),
    "parquet": _entry(
        name="Parquet files",
        category="storage",
        icon="file",
        color="#64748B",
        driver="pyarrow",
        connection_fields=[_field("path", "Path or URI", placeholder="s3://bucket/path/", required=True)],
    ),
    "json_files": _entry(
        name="JSON files",
        category="storage",
        icon="file",
        color="#64748B",
        driver="local",
        connection_fields=[_field("path", "Path or URI", required=True)],
    ),
    "jsonl": _entry(
        name="NDJSON / JSONL",
        category="storage",
        icon="file",
        color="#64748B",
        driver="local",
        connection_fields=[_field("path", "Path or URI", required=True)],
    ),
    # --- APIs & streams ---
    "rest_api": _entry(
        name="REST API",
        category="api",
        icon="globe",
        color="#6366F1",
        driver="httpx",
        connection_fields=[
            _field("base_url", "Base URL", placeholder="https://api.example.com", required=True),
            _field("auth_header", "Authorization header", type="password"),
            _field("api_key", "API key query param name"),
        ],
        test_query="GET /",
    ),
    "graphql": _entry(
        name="GraphQL endpoint",
        category="api",
        icon="globe",
        color="#E535AB",
        driver="httpx",
        connection_fields=[
            _field("endpoint", "GraphQL endpoint", required=True),
            _field("auth_header", "Authorization header", type="password"),
        ],
    ),
    "webhook": _entry(
        name="Webhook (receive data)",
        category="api",
        icon="webhook",
        color="#22C55E",
        driver="internal",
        connection_fields=[_field("path", "Inbound path slug", placeholder="my-ingest-endpoint", required=True)],
    ),
    "kafka": _entry(
        name="Apache Kafka",
        category="api",
        icon="stream",
        color="#231F20",
        driver="confluent-kafka",
        connection_fields=[
            _field("bootstrap_servers", "Bootstrap servers", required=True),
            _field("topic", "Topic", required=True),
            _field("sasl_username", "SASL username"),
            _field("sasl_password", "SASL password", type="password"),
        ],
    ),
    "kinesis": _entry(
        name="Amazon Kinesis",
        category="api",
        icon="stream",
        color="#FF9900",
        driver="boto3",
        connection_fields=[
            _field("stream_name", "Stream name", required=True),
            _field("region", "Region", required=True),
        ],
    ),
    "pubsub": _entry(
        name="Google Pub/Sub",
        category="api",
        icon="stream",
        color="#4285F4",
        driver="google-cloud-pubsub",
        connection_fields=[
            _field("project_id", "Project ID", required=True),
            _field("subscription", "Subscription", required=True),
            _field("credentials_json", "Service account JSON", type="textarea", required=True),
        ],
    ),
    "mqtt": _entry(
        name="MQTT",
        category="api",
        icon="stream",
        color="#660066",
        driver="paho-mqtt",
        connection_fields=[
            _field("broker_url", "Broker URL", placeholder="mqtts://broker.example.com:8883", required=True),
            _field("topic", "Topic", required=True),
            _field("username", "Username"),
            _field("password", "Password", type="password"),
        ],
    ),
    # --- SaaS (OAuth via connectors where available) ---
    "salesforce": _entry(
        name="Salesforce",
        category="saas",
        icon="cloud",
        color="#00A1E0",
        driver="connector",
        connection_fields=[_field("connector_id", "Linked connector ID", required=True)],
        oauth_vendor="salesforce",
    ),
    "hubspot": _entry(
        name="HubSpot",
        category="saas",
        icon="cloud",
        color="#FF7A59",
        driver="connector",
        connection_fields=[_field("connector_id", "Linked connector ID", required=True)],
        oauth_vendor="hubspot",
    ),
    "stripe": _entry(
        name="Stripe",
        category="saas",
        icon="cloud",
        color="#635BFF",
        driver="connector",
        connection_fields=[
            _field("connector_id", "Linked connector ID"),
            _field("secret_key", "Secret key", type="password"),
        ],
        oauth_vendor="stripe",
    ),
    "notion": _entry(
        name="Notion",
        category="saas",
        icon="file",
        color="#000000",
        driver="connector",
        connection_fields=[_field("connector_id", "Linked connector ID", required=True)],
        oauth_vendor="notion",
    ),
    "airtable": _entry(
        name="Airtable",
        category="saas",
        icon="table",
        color="#18BFFF",
        driver="httpx",
        connection_fields=[
            _field("base_id", "Base ID", required=True),
            _field("api_key", "Personal access token", type="password", required=True),
        ],
    ),
    "google_sheets": _entry(
        name="Google Sheets",
        category="saas",
        icon="table",
        color="#34A853",
        driver="connector",
        connection_fields=[_field("connector_id", "Linked connector ID", required=True)],
        oauth_vendor="google_sheets",
    ),
    "zendesk": _entry(
        name="Zendesk",
        category="saas",
        icon="cloud",
        color="#03363D",
        driver="connector",
        connection_fields=[_field("connector_id", "Linked connector ID", required=True)],
        oauth_vendor="zendesk",
    ),
    "jira": _entry(
        name="Jira",
        category="saas",
        icon="cloud",
        color="#0052CC",
        driver="connector",
        connection_fields=[_field("connector_id", "Linked connector ID", required=True)],
        oauth_vendor="jira",
    ),
    "github": _entry(
        name="GitHub",
        category="saas",
        icon="cloud",
        color="#24292F",
        driver="connector",
        connection_fields=[_field("connector_id", "Linked connector ID", required=True)],
        oauth_vendor="github",
    ),
    "linear": _entry(
        name="Linear",
        category="saas",
        icon="cloud",
        color="#5E6AD2",
        driver="httpx",
        connection_fields=[_field("api_key", "API key", type="password", required=True)],
    ),
}

CATEGORY_LABELS: dict[SourceCategory, str] = {
    "relational": "Relational databases",
    "warehouse": "Data warehouses",
    "nosql": "NoSQL & vector",
    "storage": "Files & object storage",
    "api": "APIs & streams",
    "saas": "SaaS applications",
}


def get_source_type(type_id: str) -> dict[str, Any] | None:
    spec = DATA_SOURCE_TYPES.get(type_id.strip().lower())
    return deepcopy(spec) if spec else None


def list_source_types(
    *,
    category: SourceCategory | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    query = (search or "").strip().lower()
    items: list[dict[str, Any]] = []
    for type_id, spec in DATA_SOURCE_TYPES.items():
        if category and spec["category"] != category:
            continue
        if query and query not in type_id and query not in spec["name"].lower():
            continue
        items.append(
            {
                "id": type_id,
                "name": spec["name"],
                "category": spec["category"],
                "categoryLabel": CATEGORY_LABELS[spec["category"]],
                "icon": spec["icon"],
                "color": spec["color"],
                "driver": spec["driver"],
                "connectionFields": spec["connection_fields"],
                "oauthVendor": spec.get("oauth_vendor"),
            }
        )
    items.sort(key=lambda row: (row["category"], row["name"]))
    return items


def validate_connection_config(type_id: str, config: dict[str, Any] | None) -> list[str]:
    spec = DATA_SOURCE_TYPES.get(type_id.strip().lower())
    if not spec:
        return [f"Unknown data source type: {type_id}"]
    config = dict(config or {})
    errors: list[str] = []
    connection_string = str(config.get("connection_string") or "").strip()
    has_alt_endpoint = any(
        str(config.get(k) or "").strip()
        for k in ("host", "url", "path", "endpoint", "base_url", "broker_url", "bootstrap_servers")
    )
    for field in spec["connection_fields"]:
        key = field["key"]
        if not field.get("required"):
            continue
        if key == "connection_string" and (connection_string or has_alt_endpoint):
            continue
        if connection_string and key in {"host", "port", "database", "username", "password"}:
            continue
        value = config.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"{field['label']} is required")
    return errors


def serialize_connection_config(type_id: str, config: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize config for encrypted storage."""
    spec = DATA_SOURCE_TYPES.get(type_id.strip().lower())
    if not spec:
        return dict(config or {})
    normalized = dict(config or {})
    for field in spec["connection_fields"]:
        key = field["key"]
        if key not in normalized and field.get("default") is not None:
            normalized.setdefault(key, field["default"])
    normalized["source_type_id"] = type_id.strip().lower()
    return normalized
