"""SQL schema for Meshloom database."""

NODES_TABLE = """
CREATE TABLE IF NOT EXISTS nodes (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    summary VARCHAR(1000),
    interest_level INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    source_url VARCHAR(1000),
    source_type VARCHAR(100),
    metadata JSON,
    INDEX idx_nodes_title (title),
    INDEX idx_nodes_interest (interest_level),
    INDEX idx_nodes_created (created_at)
);
"""

EDGES_TABLE = """
CREATE TABLE IF NOT EXISTS edges (
    id VARCHAR(36) PRIMARY KEY,
    source_id VARCHAR(36) NOT NULL,
    target_id VARCHAR(36) NOT NULL,
    relationship_type VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_edges_source (source_id),
    INDEX idx_edges_target (target_id),
    INDEX idx_edges_type (relationship_type),
    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
);
"""

APPS_TABLE = """
CREATE TABLE IF NOT EXISTS apps (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    state VARCHAR(50) DEFAULT 'installed',
    config JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_apps_name (name),
    INDEX idx_apps_state (state)
);
"""

DEVICES_TABLE = """
CREATE TABLE IF NOT EXISTS devices (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    hostname VARCHAR(255),
    identity_hash VARCHAR(255),
    hardware_json JSON,
    last_seen DATETIME,
    INDEX idx_devices_name (name),
    INDEX idx_devices_identity (identity_hash)
);
"""

SYNC_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS sync_log (
    id VARCHAR(36) PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(36) NOT NULL,
    action VARCHAR(50) NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    peer_id VARCHAR(36),
    INDEX idx_sync_log_entity (entity_type, entity_id),
    INDEX idx_sync_log_timestamp (timestamp),
    INDEX idx_sync_log_peer (peer_id)
);
"""

INITIAL_SCHEMA = NODES_TABLE + EDGES_TABLE + APPS_TABLE + DEVICES_TABLE + SYNC_LOG_TABLE