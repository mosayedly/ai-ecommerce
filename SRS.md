Software Requirements Specification (SRS)

AI-Powered E-Commerce System

1. Introduction

1.1 Purpose
The AI-Powered E-Commerce System is a web-based application that enables customers to
browse, search, and purchase products online. The system includes an AI-powered
recommendation feature that suggests products based on customer preferences and
shopping behavior.

1.2 Project Objective
•  Browse products.
•  Purchase products online.
•  Manage shopping carts and orders.
•  Receive AI-based product recommendations.
•  Demonstrate AI integration in a modern web application.

2. Technology Constraints
Backend: Python, Django
Database: PostgreSQL
Frontend: HTML, CSS, Vanilla JavaScript

Note: React, Angular, Vue, and other frontend frameworks are not allowed.

3. Functional Requirements

3.1 System Actors
Actor
Customer

Administrator

FR-1 User Authentication
•  Register
•  Login
•  Logout

FR-2 Product Management
•  Add products

Main Responsibilities
Register, login, browse/search products,
manage cart, place orders, view order
history, receive AI recommendations.
Manage products, categories, orders, and
monitor the platform.

•  Edit products
•  Delete products
•  View products

FR-3 Product Browsing
•  View products
•  View product details
•  Search products
•  Filter by category

FR-4 Shopping Cart
•  Add to cart
•  Update quantities
•  Remove products
•  View cart

FR-5 Order Management
•  Place orders
•  View order history
•  Admin: View orders
•  Admin: Update order status

FR-6 AI Product Recommendation
•  Recommend similar products
•  Recommend trending products
•  Explain recommendations

4. AI Requirements
AI Recommendation Assistant
- Analyze customer interests.
- Recommend similar products.
- Suggest popular products.
- Generate a short recommendation explanation.

5. Non-Functional Requirements
•  User-friendly interface.
•  Validate user inputs.
•  Follow Django best practices.
•  Handle invalid requests gracefully.
•  Meaningful error messages.
•  Readable and modular code.
•  Reasonable response time.

6. Deliverables
•  Complete source code
•  API documentation
•  Demo.
•  ER Diagram

7. Evaluation Criteria (100 Marks)
Criterion
Backend Development (Django)
Frontend
Database Design (PostgreSQL)
Product & Order Management
AI Recommendation Feature
Shopping Cart
Code Quality & Error Handling
Total