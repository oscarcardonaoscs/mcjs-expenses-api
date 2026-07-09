/*
  Script name: 20260601_create_client_locations_table.sql
  Purpose: Create client service locations linked to clients.
  Project: MCJ's Expenses
  Date: 2026-06-01
  Author: Oscar Cardona
*/

CREATE TABLE IF NOT EXISTS client_locations (
    id INT NOT NULL AUTO_INCREMENT,
    client_id INT NOT NULL,
    location_name VARCHAR(100) NOT NULL DEFAULT 'HOME',
    street_line1 VARCHAR(150) NULL,
    street_line2 VARCHAR(150) NULL,
    city VARCHAR(100) NULL,
    state VARCHAR(50) NULL,
    postal_code VARCHAR(20) NULL,
    country VARCHAR(50) NOT NULL DEFAULT 'USA',
    square_feet INT NULL,
    bedrooms DECIMAL(4,1) NULL,
    bathrooms DECIMAL(4,1) NULL,
    access_notes TEXT NULL,
    service_notes TEXT NULL,
    is_primary TINYINT(1) NOT NULL DEFAULT 0,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_client_locations_client
        FOREIGN KEY (client_id)
        REFERENCES clients(id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    INDEX idx_client_locations_client_id (client_id),
    INDEX idx_client_locations_is_active (is_active),
    INDEX idx_client_locations_city_state (city, state)
)