# Modules Overview

The Mini ERP System is highly modular, split into 14 core Django applications residing in the `apps/` directory. This document outlines the purpose of each app.

## 1. Accounts (`apps/accounts`)
Handles user authentication, authorization, and role management. Provides the custom User model and views for login/logout/signup and user listings.

## 2. Audit Logs (`apps/audit_logs`)
Maintains a system-wide trail of activities to ensure accountability. It tracks actions performed by users across various modules.

## 3. Blockchain (`apps/blockchain`)
Integrates rudimentary or conceptual blockchain tracking mechanisms for logistics and supply chain transparency.

## 4. Dashboard (`apps/dashboard`)
Serves as the Control Center of the ERP. Provides real-time overview metrics, KPI charts, and status alerts aggregating data from other modules.

## 5. Delivery (`apps/delivery`)
Manages the generation of delivery notes, tracking of shipments, and dispatching operations related to fulfilled sales or foreign trade orders.

## 6. Foreign Trade (`apps/foreign_trade`)
Handles international business transactions. Manages Export and Import orders, incorporating standard Incoterms 2020 logic and documentation.

## 7. Inventory (`apps/inventory`)
The core module for warehouse management. Tracks real-time stock levels, stock movement history, and provides services for receiving and issuing stock.

## 8. Manufacturing (`apps/manufacturing`)
Manages production workflows. Includes Bills of Materials (BOM), Manufacturing Orders (MO), work centers, and tracks the consumption of raw materials to produce finished goods.

## 9. Notifications (`apps/notifications`)
A centralized system for generating and dispatching in-app alerts and notifications to users based on triggered events (e.g., low stock, order approval).

## 10. Procurement (`apps/procurement`)
Streamlines procurement workflows and handles purchasing triggers (e.g., reorder points). Acts as a bridge between Inventory needs and the Purchase module.

## 11. Products (`apps/products`)
Maintains the master catalog of items. Stores details like SKUs, HS codes, pricing, units of measure, and categorizations. Used across sales, purchase, and inventory modules.

## 12. Purchase (`apps/purchase`)
Manages the purchasing lifecycle. Tracks vendors/suppliers, generates Purchase Orders (POs), and monitors the status of incoming goods.

## 13. Reports (`apps/reports`)
Generates structured data reports based on system activity (sales summaries, inventory valuations, etc.) for management review.

## 14. Sales (`apps/sales`)
Manages the sales lifecycle. Tracks customers, generates Sales Orders (SOs), and interfaces with the Delivery and Inventory modules upon fulfillment.
