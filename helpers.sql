/******************************************************************************
Script name : 001_create_helper_payroll_tables.sql
Purpose     : Create payroll-related tables for helpers, including helpers,
              helper time entries, and helper payroll periods.
Project     : MCJ's Cleaning Service
Date        : 2026-03-08
Author      : OpenAI
******************************************************************************/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------------------------------------------------------
-- Table: helpers
-- Purpose:
--   Stores helper/employee basic information and default hourly rates.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS helper_time_entries;
DROP TABLE IF EXISTS helper_payroll_periods;
DROP TABLE IF EXISTS helpers;

CREATE TABLE helpers (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) DEFAULT NULL,
    phone VARCHAR(30) DEFAULT NULL,
    email VARCHAR(150) DEFAULT NULL,
    default_work_rate DECIMAL(10,2) NOT NULL DEFAULT 15.00,
    default_travel_rate DECIMAL(10,2) NOT NULL DEFAULT 7.25,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    notes TEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_helpers_is_active (is_active),
    KEY idx_helpers_name (first_name, last_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table: helper_payroll_periods
-- Purpose:
--   Stores payroll period summaries for each helper.
-- ----------------------------------------------------------------------------
CREATE TABLE helper_payroll_periods (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    helper_id INT UNSIGNED NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    pay_date DATE DEFAULT NULL,
    work_rate DECIMAL(10,2) NOT NULL,
    travel_rate DECIMAL(10,2) NOT NULL,
    total_work_minutes INT UNSIGNED NOT NULL DEFAULT 0,
    total_travel_minutes INT UNSIGNED NOT NULL DEFAULT 0,
    work_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    travel_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    status ENUM('Open', 'Ready', 'Paid', 'Cancelled') NOT NULL DEFAULT 'Open',
    notes TEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_helper_payroll_period (helper_id, period_start, period_end),
    KEY idx_helper_payroll_periods_helper_id (helper_id),
    KEY idx_helper_payroll_periods_period_start (period_start),
    KEY idx_helper_payroll_periods_period_end (period_end),
    KEY idx_helper_payroll_periods_pay_date (pay_date),
    KEY idx_helper_payroll_periods_status (status),
    CONSTRAINT fk_helper_payroll_periods_helper
        FOREIGN KEY (helper_id) REFERENCES helpers (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT chk_helper_payroll_periods_dates
        CHECK (period_end >= period_start),
    CONSTRAINT chk_helper_payroll_periods_minutes
        CHECK (
            total_work_minutes >= 0
            AND total_travel_minutes >= 0
        ),
    CONSTRAINT chk_helper_payroll_periods_amounts
        CHECK (
            work_rate >= 0
            AND travel_rate >= 0
            AND work_amount >= 0
            AND travel_amount >= 0
            AND total_amount >= 0
        )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- Table: helper_time_entries
-- Purpose:
--   Stores daily helper work entries before or after payroll assignment.
-- ----------------------------------------------------------------------------
CREATE TABLE helper_time_entries (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    helper_id INT UNSIGNED NOT NULL,
    helper_payroll_period_id INT UNSIGNED DEFAULT NULL,
    work_date DATE NOT NULL,
    client_name VARCHAR(200) NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    work_minutes INT UNSIGNED NOT NULL DEFAULT 0,
    travel_minutes INT UNSIGNED NOT NULL DEFAULT 0,
    notes TEXT DEFAULT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_helper_time_entries_helper_id (helper_id),
    KEY idx_helper_time_entries_payroll_id (helper_payroll_period_id),
    KEY idx_helper_time_entries_work_date (work_date),
    KEY idx_helper_time_entries_helper_date (helper_id, work_date),
    KEY idx_helper_time_entries_client_name (client_name),
    CONSTRAINT fk_helper_time_entries_helper
        FOREIGN KEY (helper_id) REFERENCES helpers (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_helper_time_entries_payroll_period
        FOREIGN KEY (helper_payroll_period_id) REFERENCES helper_payroll_periods (id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    CONSTRAINT chk_helper_time_entries_minutes
        CHECK (
            work_minutes >= 0
            AND travel_minutes >= 0
        )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;