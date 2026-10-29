"""
Fresh held-out question set (v2), frozen BEFORE the retry and schema-hint
fixes are built or tested.

Written without running the agent on any of them and without reading the
agent's outputs on the v1 set while choosing wording. Run with:

    $env:ABLATION_SET = "heldout2"     (results go to eval/results/heldout2)

Do not tune against these. If a fix is made after reading a failure here,
write new questions for that area.
"""

QUESTIONS = [
    # ---- joins ----
    {"id": "g_join_01", "category": "joins",
     "question": "How many order items were sold for products in the Accessories category?",
     "reference_sql": "SELECT COUNT(*) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.category = 'Accessories'"},
    {"id": "g_join_02", "category": "joins",
     "question": "What is the total sale price of order items for products from the brand Allegra K?",
     "reference_sql": "SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.brand = 'Allegra K'"},
    {"id": "g_join_03", "category": "joins",
     "question": "How many distinct products have been ordered by users from Brazil?",
     "reference_sql": "SELECT COUNT(DISTINCT oi.product_id) FROM order_items oi JOIN users u ON u.id = oi.user_id WHERE u.country = 'Brazil'"},
    {"id": "g_join_04", "category": "joins",
     "question": "What is the average sale price of order items bought by male users?",
     "reference_sql": "SELECT AVG(oi.sale_price) FROM order_items oi JOIN users u ON u.id = oi.user_id WHERE u.gender = 'M'"},
    {"id": "g_join_05", "category": "joins",
     "question": "Which distribution center name has the highest total retail price across its products?",
     "reference_sql": "SELECT d.name, SUM(p.retail_price) FROM products p JOIN distribution_centers d ON d.id = p.distribution_center_id GROUP BY d.name ORDER BY 2 DESC, 1 LIMIT 1",
     "ordered": True},

    # ---- date handling ----
    {"id": "g_date_01", "category": "dates",
     "question": "How many orders were delivered in the first quarter of 2023?",
     "reference_sql": "SELECT COUNT(*) FROM orders WHERE delivered_at >= '2023-01-01' AND delivered_at < '2023-04-01'"},
    {"id": "g_date_02", "category": "dates",
     "question": "How many events happened in December 2022?",
     "reference_sql": "SELECT COUNT(*) FROM events WHERE created_at >= '2022-12-01' AND created_at < '2023-01-01'"},
    {"id": "g_date_03", "category": "dates",
     "question": "How many order items were returned in 2023?",
     "reference_sql": "SELECT COUNT(*) FROM order_items WHERE returned_at >= '2023-01-01' AND returned_at < '2024-01-01'"},
    {"id": "g_date_04", "category": "dates",
     "question": "How many users joined on or after 2023-07-01?",
     "reference_sql": "SELECT COUNT(*) FROM users WHERE created_at >= '2023-07-01'"},
    {"id": "g_date_05", "category": "dates",
     "question": "How many orders were created between 2022-06-01 and 2022-06-30, including both days?",
     "reference_sql": "SELECT COUNT(*) FROM orders WHERE created_at >= '2022-06-01' AND created_at < '2022-07-01'"},

    # ---- business definitions ----
    {"id": "g_biz_01", "category": "business",
     "question": "What percentage of orders were returned?",
     "reference_sql": "SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Returned') / COUNT(*) FROM orders"},
    {"id": "g_biz_02", "category": "business",
     "question": "What is the cancellation rate of orders, as a percentage?",
     "reference_sql": "SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Cancelled') / COUNT(*) FROM orders"},
    {"id": "g_biz_03", "category": "business",
     "question": "How many distinct users have made a purchase?",
     "reference_sql": "SELECT COUNT(DISTINCT user_id) FROM events WHERE event_type = 'purchase'"},
    {"id": "g_biz_04", "category": "business",
     "question": "What is the total revenue from completed order items for products in the Men department?",
     "reference_sql": "SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete' AND p.department = 'Men'"},
    {"id": "g_biz_05", "category": "business",
     "question": "What is the average profit per completed order item, meaning sale price minus product cost?",
     "reference_sql": "SELECT AVG(oi.sale_price - p.cost) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete'"},

    # ---- empty or tricky results ----
    {"id": "g_empty_01", "category": "empty",
     "question": "How many orders contain more than 10 items?",
     "reference_sql": "SELECT COUNT(*) FROM orders WHERE num_of_item > 10", "expect_empty": True},
    {"id": "g_empty_02", "category": "empty",
     "question": "How many users are from the country Atlantis?",
     "reference_sql": "SELECT COUNT(*) FROM users WHERE country = 'Atlantis'", "expect_empty": True},
    {"id": "g_empty_03", "category": "empty",
     "question": "List the products with a retail price above 5000.",
     "reference_sql": "SELECT id FROM products WHERE retail_price > 5000", "expect_empty": True},
    {"id": "g_empty_04", "category": "empty",
     "question": "How many events used the browser Netscape?",
     "reference_sql": "SELECT COUNT(*) FROM events WHERE browser = 'Netscape'", "expect_empty": True},
    {"id": "g_empty_05", "category": "empty",
     "question": "How many order items have a negative sale price?",
     "reference_sql": "SELECT COUNT(*) FROM order_items WHERE sale_price < 0", "expect_empty": True},

    # ---- harder aggregations ----
    {"id": "g_agg_01", "category": "aggregation",
     "question": "Which country has the most users?",
     "reference_sql": "SELECT country, COUNT(*) FROM users GROUP BY country ORDER BY 2 DESC, 1 LIMIT 1",
     "ordered": True},
    {"id": "g_agg_02", "category": "aggregation",
     "question": "What is the average number of items per order for orders placed by users under 25?",
     "reference_sql": "SELECT AVG(o.num_of_item) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.age < 25"},
    {"id": "g_agg_03", "category": "aggregation",
     "question": "How many order items are there for each order status?",
     "reference_sql": "SELECT status, COUNT(*) FROM order_items GROUP BY status ORDER BY 1"},
    {"id": "g_agg_04", "category": "aggregation",
     "question": "What are the 3 most common event types, and how many events of each?",
     "reference_sql": "SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY 2 DESC, 1 LIMIT 3",
     "ordered": True},
    {"id": "g_agg_05", "category": "aggregation",
     "question": "What is the youngest age among female users?",
     "reference_sql": "SELECT MIN(age) FROM users WHERE gender = 'F'"},
    {"id": "g_agg_06", "category": "aggregation",
     "question": "How many users have placed exactly one order?",
     "reference_sql": "SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) = 1) t"},
    {"id": "g_agg_07", "category": "aggregation",
     "question": "What percentage of events come from the Chrome browser?",
     "reference_sql": "SELECT 100.0 * COUNT(*) FILTER (WHERE browser = 'Chrome') / COUNT(*) FROM events"},
    {"id": "g_agg_08", "category": "aggregation",
     "question": "Which month of 2023 had the highest total sale price of order items? Give the month number.",
     "reference_sql": "SELECT EXTRACT(MONTH FROM created_at)::int FROM order_items WHERE created_at >= '2023-01-01' AND created_at < '2024-01-01' GROUP BY 1 ORDER BY SUM(sale_price) DESC, 1 LIMIT 1",
     "ordered": True},
    {"id": "g_agg_09", "category": "aggregation",
     "question": "How many distinct sessions did users from Germany have?",
     "reference_sql": "SELECT COUNT(DISTINCT e.session_id) FROM events e JOIN users u ON u.id = e.user_id WHERE u.country = 'Germany'"},
    {"id": "g_agg_10", "category": "aggregation",
     "question": "How many products have a retail price above 100?",
     "reference_sql": "SELECT COUNT(*) FROM products WHERE retail_price > 100"},
]
