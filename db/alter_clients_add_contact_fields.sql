/*
Script name: alter_clients_add_contact_fields.sql
Purpose: Add contact and notes fields to clients table
Project: mcjs-expenses
Date: 2026-06-01
Author: Oscar
*/

ALTER TABLE clients
ADD COLUMN phone VARCHAR(30) NULL AFTER name;

ALTER TABLE clients
ADD COLUMN email VARCHAR(150) NULL AFTER phone;

ALTER TABLE clients
ADD COLUMN notes TEXT NULL AFTER email;

select * from clients;