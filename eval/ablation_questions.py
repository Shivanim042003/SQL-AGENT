"""
Held-out questions for the ablation evaluation.

These are NOT the golden or red-team questions, and none of them appears in
the hardcoded shortcuts. Each has a hand-written reference query; the
evaluation runs that query on the same database at evaluation time and
compares the agent's rows with it (no stored numbers to go stale).

Fields:
    id, category, question
    reference_sql  PostgreSQL, run with the owner connection
    ordered        True when row order is part of the answer (top-N lists)
    expect_empty   True when the correct result is no rows, a zero count or
                   NULL (used to flag a reference query that unexpectedly
                   returns data)
"""

QUESTIONS = [

    # ============================================================
    # JOINS
    # ============================================================

    {
        "id": "join_01", "category": "joins",
        "question": "How many orders were placed by users from California?",
        "reference_sql": (
            "SELECT COUNT(*) FROM orders o "
            "JOIN users u ON u.id = o.user_id WHERE u.state = 'California'"
        ),
    },
    {
        "id": "join_02", "category": "joins",
        "question": (
            "What are the top 5 product categories by total sale price of "
            "order items?"
        ),
        "reference_sql": (
            "SELECT p.category, SUM(oi.sale_price) FROM order_items oi "
            "JOIN products p ON p.id = oi.product_id "
            "GROUP BY p.category ORDER BY 2 DESC LIMIT 5"
        ),
        "ordered": True,
    },
    {
        "id": "join_03", "category": "joins",
        "question": (
            "How many distinct users have bought a product from the brand "
            "Calvin Klein?"
        ),
        "reference_sql": (
            "SELECT COUNT(DISTINCT oi.user_id) FROM order_items oi "
            "JOIN products p ON p.id = oi.product_id "
            "WHERE p.brand = 'Calvin Klein'"
        ),
    },
    {
        "id": "join_04", "category": "joins",
        "question": (
            "What is the average age of users who have placed at least one "
            "order?"
        ),
        "reference_sql": (
            "SELECT AVG(age) FROM users "
            "WHERE id IN (SELECT DISTINCT user_id FROM orders)"
        ),
    },
    {
        "id": "join_05", "category": "joins",
        "question": (
            "How many order items were for products stocked at the "
            "Memphis TN distribution center?"
        ),
        "reference_sql": (
            "SELECT COUNT(*) FROM order_items oi "
            "JOIN products p ON p.id = oi.product_id "
            "JOIN distribution_centers d ON d.id = p.distribution_center_id "
            "WHERE d.name = 'Memphis TN'"
        ),
    },
    {
        "id": "join_06", "category": "joins",
        "question": (
            "Which 3 user traffic sources have the most orders, and how many "
            "orders does each have?"
        ),
        "reference_sql": (
            "SELECT u.traffic_source, COUNT(*) FROM orders o "
            "JOIN users u ON u.id = o.user_id "
            "GROUP BY u.traffic_source ORDER BY 2 DESC LIMIT 3"
        ),
        "ordered": True,
    },
    {
        "id": "join_07", "category": "joins",
        "question": "How many users have never placed an order?",
        "reference_sql": (
            "SELECT COUNT(*) FROM users u WHERE NOT EXISTS "
            "(SELECT 1 FROM orders o WHERE o.user_id = u.id)"
        ),
    },
    {
        "id": "join_08", "category": "joins",
        "question": (
            "What is the average sale price of order items for products in "
            "the Women department?"
        ),
        "reference_sql": (
            "SELECT AVG(oi.sale_price) FROM order_items oi "
            "JOIN products p ON p.id = oi.product_id "
            "WHERE p.department = 'Women'"
        ),
    },

    # ============================================================
    # DATE BOUNDARIES
    # ============================================================

    {
        "id": "date_01", "category": "dates",
        "question": "How many orders were created in 2022?",
        "reference_sql": (
            "SELECT COUNT(*) FROM orders "
            "WHERE created_at >= '2022-01-01' AND created_at < '2023-01-01'"
        ),
    },
    {
        "id": "date_02", "category": "dates",
        "question": (
            "How many users registered in the first quarter of 2021?"
        ),
        "reference_sql": (
            "SELECT COUNT(*) FROM users "
            "WHERE created_at >= '2021-01-01' AND created_at < '2021-04-01'"
        ),
    },
    {
        "id": "date_03", "category": "dates",
        "question": "How many events occurred on March 15, 2023?",
        "reference_sql": (
            "SELECT COUNT(*) FROM events "
            "WHERE created_at >= '2023-03-15' AND created_at < '2023-03-16'"
        ),
    },
    {
        "id": "date_04", "category": "dates",
        "question": "How many orders were created in February 2020?",
        "reference_sql": (
            "SELECT COUNT(*) FROM orders "
            "WHERE created_at >= '2020-02-01' AND created_at < '2020-03-01'"
        ),
    },
    {
        "id": "date_05", "category": "dates",
        "question": (
            "How many orders were created between January 1, 2022 and "
            "January 31, 2022, inclusive of both days?"
        ),
        "reference_sql": (
            "SELECT COUNT(*) FROM orders "
            "WHERE created_at >= '2022-01-01' AND created_at < '2022-02-01'"
        ),
    },
    {
        "id": "date_06", "category": "dates",
        "question": (
            "How many order items were delivered in the second half of 2022?"
        ),
        "reference_sql": (
            "SELECT COUNT(*) FROM order_items "
            "WHERE delivered_at >= '2022-07-01' AND delivered_at < '2023-01-01'"
        ),
    },
    {
        "id": "date_07", "category": "dates",
        "question": "How many orders were shipped in December 2021?",
        "reference_sql": (
            "SELECT COUNT(*) FROM orders "
            "WHERE shipped_at >= '2021-12-01' AND shipped_at < '2022-01-01'"
        ),
    },
    {
        "id": "date_08", "category": "dates",
        "question": (
            "How many orders took more than 5 days between being created "
            "and being delivered?"
        ),
        "reference_sql": (
            "SELECT COUNT(*) FROM orders "
            "WHERE delivered_at - created_at > INTERVAL '5 days'"
        ),
    },
    {
        "id": "date_09", "category": "dates",
        "question": (
            "For each calendar year, how many orders were created? Return "
            "the year as a number."
        ),
        "reference_sql": (
            "SELECT EXTRACT(YEAR FROM created_at), COUNT(*) FROM orders "
            "GROUP BY 1"
        ),
    },

    # ============================================================
    # BUSINESS DEFINITIONS (from the glossary)
    # ============================================================

    {
        "id": "biz_01", "category": "business",
        "question": "What is the average order value?",
        "reference_sql": (
            "SELECT SUM(sale_price) / COUNT(DISTINCT order_id) "
            "FROM order_items WHERE status = 'Complete'"
        ),
    },
    {
        "id": "biz_02", "category": "business",
        "question": "What is the repeat purchase rate?",
        "reference_sql": (
            "SELECT 100.0 * COUNT(*) FILTER (WHERE completed > 1) / COUNT(*) "
            "FROM (SELECT user_id, "
            "COUNT(*) FILTER (WHERE status = 'Complete') AS completed "
            "FROM orders GROUP BY user_id) t"
        ),
    },
    {
        "id": "biz_03", "category": "business",
        "question": "What is the cart abandonment rate?",
        "reference_sql": (
            "WITH s AS (SELECT session_id, "
            "BOOL_OR(event_type = 'cart') AS carted, "
            "BOOL_OR(event_type = 'purchase') AS bought "
            "FROM events GROUP BY session_id) "
            "SELECT 100.0 * COUNT(*) FILTER (WHERE carted AND NOT bought) "
            "/ NULLIF(COUNT(*) FILTER (WHERE carted), 0) FROM s"
        ),
    },
    {
        "id": "biz_04", "category": "business",
        "question": (
            "What percentage of sessions include at least one cart event?"
        ),
        "reference_sql": (
            "SELECT 100.0 * COUNT(DISTINCT session_id) "
            "FILTER (WHERE event_type = 'cart') "
            "/ COUNT(DISTINCT session_id) FROM events"
        ),
    },
    {
        "id": "biz_05", "category": "business",
        "question": "What is the total revenue from completed order items?",
        "reference_sql": (
            "SELECT SUM(sale_price) FROM order_items WHERE status = 'Complete'"
        ),
    },
    {
        "id": "biz_06", "category": "business",
        "question": (
            "What is the total profit from completed order items, using the "
            "product catalog cost (products.cost)?"
        ),
        "reference_sql": (
            "SELECT SUM(oi.sale_price - p.cost) FROM order_items oi "
            "JOIN products p ON p.id = oi.product_id "
            "WHERE oi.status = 'Complete'"
        ),
    },
    {
        "id": "biz_07", "category": "business",
        "question": "How many order items have been returned?",
        "reference_sql": (
            "SELECT COUNT(*) FROM order_items WHERE status = 'Returned'"
        ),
    },
    {
        "id": "biz_08", "category": "business",
        "question": "What percentage of orders were cancelled?",
        "reference_sql": (
            "SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Cancelled') "
            "/ COUNT(*) FROM orders"
        ),
    },
    {
        "id": "biz_09", "category": "business",
        "question": (
            "How many events came from visitors who were not logged in?"
        ),
        "reference_sql": "SELECT COUNT(*) FROM events WHERE user_id IS NULL",
    },
    {
        "id": "biz_10", "category": "business",
        "question": (
            "Which traffic source has the highest session-to-purchase "
            "conversion rate, and what is that rate?"
        ),
        "reference_sql": (
            "SELECT traffic_source, 100.0 * COUNT(DISTINCT session_id) "
            "FILTER (WHERE event_type = 'purchase') "
            "/ COUNT(DISTINCT session_id) AS rate "
            "FROM events GROUP BY traffic_source ORDER BY rate DESC LIMIT 1"
        ),
        "ordered": True,
    },

    # ============================================================
    # EMPTY RESULTS
    # ============================================================

    {
        "id": "empty_01", "category": "empty",
        "question": "Which users are older than 120 years?",
        "reference_sql": "SELECT id FROM users WHERE age > 120",
        "expect_empty": True,
    },
    {
        "id": "empty_02", "category": "empty",
        "question": "List the orders that have the status 'Refunded'.",
        "reference_sql": (
            "SELECT order_id FROM orders WHERE status = 'Refunded'"
        ),
        "expect_empty": True,
    },
    {
        "id": "empty_03", "category": "empty",
        "question": (
            "How many events were recorded before January 1, 2015?"
        ),
        "reference_sql": (
            "SELECT COUNT(*) FROM events WHERE created_at < '2015-01-01'"
        ),
        "expect_empty": True,
    },
    {
        "id": "empty_04", "category": "empty",
        "question": (
            "What is the average sale price of order items for products in "
            "the category 'Spacesuits'?"
        ),
        "reference_sql": (
            "SELECT AVG(oi.sale_price) FROM order_items oi "
            "JOIN products p ON p.id = oi.product_id "
            "WHERE p.category = 'Spacesuits'"
        ),
        "expect_empty": True,
    },
    {
        "id": "empty_05", "category": "empty",
        "question": "Which products have a retail price below zero?",
        "reference_sql": "SELECT id FROM products WHERE retail_price < 0",
        "expect_empty": True,
    },

    # ============================================================
    # HARDER AGGREGATIONS
    # ============================================================

    {
        "id": "agg_01", "category": "aggregation",
        "question": "What is the second most common event type?",
        "reference_sql": (
            "SELECT event_type FROM events GROUP BY event_type "
            "ORDER BY COUNT(*) DESC OFFSET 1 LIMIT 1"
        ),
    },
    {
        "id": "agg_02", "category": "aggregation",
        "question": (
            "For each order status, what is the average number of items "
            "per order?"
        ),
        "reference_sql": (
            "SELECT status, AVG(num_of_item) FROM orders GROUP BY status"
        ),
    },
    {
        "id": "agg_03", "category": "aggregation",
        "question": "What is the median age of users?",
        "reference_sql": (
            "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY age) "
            "FROM users"
        ),
    },
    {
        "id": "agg_04", "category": "aggregation",
        "question": (
            "Which state has the most users, and how many users does it have?"
        ),
        "reference_sql": (
            "SELECT state, COUNT(*) FROM users GROUP BY state "
            "ORDER BY 2 DESC LIMIT 1"
        ),
        "ordered": True,
    },
    {
        "id": "agg_05", "category": "aggregation",
        "question": (
            "What is the average number of orders per user among users who "
            "have placed at least one order?"
        ),
        "reference_sql": (
            "SELECT COUNT(*)::numeric / COUNT(DISTINCT user_id) FROM orders"
        ),
    },
    {
        "id": "agg_06", "category": "aggregation",
        "question": "How many users have placed more than 3 orders?",
        "reference_sql": (
            "SELECT COUNT(*) FROM (SELECT user_id FROM orders "
            "GROUP BY user_id HAVING COUNT(*) > 3) t"
        ),
    },
    {
        "id": "agg_07", "category": "aggregation",
        "question": (
            "What are the top 3 brands by number of distinct customers who "
            "bought them?"
        ),
        "reference_sql": (
            "SELECT p.brand, COUNT(DISTINCT oi.user_id) FROM order_items oi "
            "JOIN products p ON p.id = oi.product_id "
            "GROUP BY p.brand ORDER BY 2 DESC LIMIT 3"
        ),
        "ordered": True,
    },
    {
        "id": "agg_08", "category": "aggregation",
        "question": "How many users placed their first order in 2022?",
        "reference_sql": (
            "SELECT COUNT(*) FROM (SELECT user_id FROM orders "
            "GROUP BY user_id HAVING MIN(created_at) >= '2022-01-01' "
            "AND MIN(created_at) < '2023-01-01') t"
        ),
    },
    {
        "id": "agg_09", "category": "aggregation",
        "question": (
            "What is the average time between an order being created and "
            "shipped, in fractional days?"
        ),
        "reference_sql": (
            "SELECT AVG(EXTRACT(EPOCH FROM (shipped_at - created_at)) "
            "/ 86400.0) FROM orders WHERE shipped_at IS NOT NULL"
        ),
    },
    {
        "id": "agg_10", "category": "aggregation",
        "question": (
            "Which month of the year, as a number from 1 to 12, has the "
            "most orders when all years are combined?"
        ),
        "reference_sql": (
            "SELECT EXTRACT(MONTH FROM created_at) FROM orders "
            "GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1"
        ),
    },
]
