"""
Final held-out question set (v1), frozen BEFORE any agent change is tested on it.

Rules:
- Written without running the agent on them. Do not tune prompts, shortcuts or
  schema hints against these questions. If a fix is made after seeing a
  failure here, add NEW questions for that area instead of re-using these.
- Same format as eval/ablation_questions.py. Reference SQL is run on the same
  database at evaluation time.
- Run with:  $env:ABLATION_SET = "heldout"   (results go to eval/results/heldout)
"""

QUESTIONS = [
    # ---- joins ----
    {"id": "h_join_01", "category": "joins",
     "question": "How many orders were placed by female users?",
     "reference_sql": "SELECT COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.gender = 'F'"},
    {"id": "h_join_02", "category": "joins",
     "question": "Which 5 brands have the most order items?",
     "reference_sql": "SELECT p.brand, COUNT(*) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.brand ORDER BY 2 DESC, 1 LIMIT 5",
     "ordered": True},
    {"id": "h_join_03", "category": "joins",
     "question": "How many distinct users from Texas have placed an order?",
     "reference_sql": "SELECT COUNT(DISTINCT o.user_id) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.state = 'Texas'"},
    {"id": "h_join_04", "category": "joins",
     "question": "What is the average retail price of products in the Jeans category?",
     "reference_sql": "SELECT AVG(retail_price) FROM products WHERE category = 'Jeans'"},
    {"id": "h_join_05", "category": "joins",
     "question": "Which distribution center name supplies the most products?",
     "reference_sql": "SELECT d.name, COUNT(*) FROM products p JOIN distribution_centers d ON d.id = p.distribution_center_id GROUP BY d.name ORDER BY 2 DESC, 1 LIMIT 1",
     "ordered": True},

    # ---- date handling ----
    {"id": "h_date_01", "category": "dates",
     "question": "How many orders were created in March 2023?",
     "reference_sql": "SELECT COUNT(*) FROM orders WHERE created_at >= '2023-03-01' AND created_at < '2023-04-01'"},
    {"id": "h_date_02", "category": "dates",
     "question": "How many users joined in the year 2021?",
     "reference_sql": "SELECT COUNT(*) FROM users WHERE created_at >= '2021-01-01' AND created_at < '2022-01-01'"},
    {"id": "h_date_03", "category": "dates",
     "question": "How many orders were shipped in 2022?",
     "reference_sql": "SELECT COUNT(*) FROM orders WHERE shipped_at >= '2022-01-01' AND shipped_at < '2023-01-01'"},
    {"id": "h_date_04", "category": "dates",
     "question": "Which month of 2022 had the most orders? Give the month number.",
     "reference_sql": "SELECT EXTRACT(MONTH FROM created_at)::int FROM orders WHERE created_at >= '2022-01-01' AND created_at < '2023-01-01' GROUP BY 1 ORDER BY COUNT(*) DESC, 1 LIMIT 1",
     "ordered": True},
    {"id": "h_date_05", "category": "dates",
     "question": "How many events happened on 2023-06-15?",
     "reference_sql": "SELECT COUNT(*) FROM events WHERE created_at >= '2023-06-15' AND created_at < '2023-06-16'"},

    # ---- business definitions ----
    {"id": "h_biz_01", "category": "business",
     "question": "What is the total revenue from completed order items?",
     "reference_sql": "SELECT SUM(sale_price) FROM order_items WHERE status = 'Complete'"},
    {"id": "h_biz_02", "category": "business",
     "question": "What percentage of order items were returned?",
     "reference_sql": "SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Returned') / COUNT(*) FROM order_items"},
    {"id": "h_biz_03", "category": "business",
     "question": "What is the average order value, counting only completed order items?",
     "reference_sql": "SELECT SUM(sale_price) / COUNT(DISTINCT order_id) FROM order_items WHERE status = 'Complete'"},
    {"id": "h_biz_04", "category": "business",
     "question": "How many sessions contained a purchase event?",
     "reference_sql": "SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type = 'purchase'"},
    {"id": "h_biz_05", "category": "business",
     "question": "What is the gross margin percentage on completed order items (sale price minus product cost, divided by sale price)?",
     "reference_sql": "SELECT 100.0 * SUM(oi.sale_price - p.cost) / SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete'"},

    # ---- empty or tricky results ----
    {"id": "h_empty_01", "category": "empty",
     "question": "How many orders have the status 'Teleported'?",
     "reference_sql": "SELECT COUNT(*) FROM orders WHERE status = 'Teleported'", "expect_empty": True},
    {"id": "h_empty_02", "category": "empty",
     "question": "List the products in the brand 'Zzyzx Fashion'.",
     "reference_sql": "SELECT id FROM products WHERE brand = 'Zzyzx Fashion'", "expect_empty": True},
    {"id": "h_empty_03", "category": "empty",
     "question": "How many users joined before the year 2000?",
     "reference_sql": "SELECT COUNT(*) FROM users WHERE created_at < '2000-01-01'", "expect_empty": True},
    {"id": "h_empty_04", "category": "empty",
     "question": "How many users are older than 120?",
     "reference_sql": "SELECT COUNT(*) FROM users WHERE age > 120", "expect_empty": True},
    {"id": "h_empty_05", "category": "empty",
     "question": "How many events have the type 'teleport'?",
     "reference_sql": "SELECT COUNT(*) FROM events WHERE event_type = 'teleport'", "expect_empty": True},

    # ---- harder aggregations ----
    {"id": "h_agg_01", "category": "aggregation",
     "question": "How many users have placed more than 3 orders?",
     "reference_sql": "SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) > 3) t"},
    {"id": "h_agg_02", "category": "aggregation",
     "question": "What is the average number of items per order?",
     "reference_sql": "SELECT AVG(num_of_item) FROM orders"},
    {"id": "h_agg_03", "category": "aggregation",
     "question": "Which 3 states have the most users, and how many users does each have?",
     "reference_sql": "SELECT state, COUNT(*) FROM users GROUP BY state ORDER BY 2 DESC, 1 LIMIT 3",
     "ordered": True},
    {"id": "h_agg_04", "category": "aggregation",
     "question": "What is the highest sale price of any order item?",
     "reference_sql": "SELECT MAX(sale_price) FROM order_items"},
    {"id": "h_agg_05", "category": "aggregation",
     "question": "For each department, how many products are there?",
     "reference_sql": "SELECT department, COUNT(*) FROM products GROUP BY department ORDER BY 1"},
    {"id": "h_agg_06", "category": "aggregation",
     "question": "How many users have never placed an order?",
     "reference_sql": "SELECT COUNT(*) FROM users u WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)"},
    {"id": "h_agg_07", "category": "aggregation",
     "question": "What is the average age of users by traffic source?",
     "reference_sql": "SELECT traffic_source, AVG(age) FROM users GROUP BY traffic_source ORDER BY 1"},
    {"id": "h_agg_08", "category": "aggregation",
     "question": "Which product category has the highest average sale price per order item?",
     "reference_sql": "SELECT p.category, AVG(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.category ORDER BY 2 DESC, 1 LIMIT 1",
     "ordered": True},
    {"id": "h_agg_09", "category": "aggregation",
     "question": "How many orders were cancelled in 2023?",
     "reference_sql": "SELECT COUNT(*) FROM orders WHERE status = 'Cancelled' AND created_at >= '2023-01-01' AND created_at < '2024-01-01'"},
    {"id": "h_agg_10", "category": "aggregation",
     "question": "What share of users come from the Search traffic source, as a percentage?",
     "reference_sql": "SELECT 100.0 * COUNT(*) FILTER (WHERE traffic_source = 'Search') / COUNT(*) FROM users"},
]
