# Ablation results

Model: `qwen3:8b` via `ollama`. Run on 2026-10-28.

How answers are compared (rules in `eval/ablation_lib.py`):

- Column names and column order are ignored; extra columns are allowed, but every reference column must be present with the same values.
- Row order is ignored unless the question is a top-N/ordering question (marked `ordered`). Duplicate rows are kept, so row counts must match exactly.
- Numbers (int, float, decimal) compare as floats with a tolerance of 1e-4 relative or 0.011 absolute; a percentage never matches a ratio.
- Dates and timestamps compare as ISO text; NULL matches only NULL.
- Top-N questions where ties could change the answer are avoided in the question set rather than handled by the comparator.
- Empty results: an empty reference matches only an empty result, and a zero count or NULL must match exactly. Questions designed to return nothing should be checked by hand (`--validate-reference`) because two different queries can both return nothing on one database snapshot for different reasons.

Correctness is decided only by the reference query, never by a model's opinion. Shortcuts (hardcoded SQL and critic rules) are switched off for every configuration.

Question set fingerprint: `f693b57f5628`

## Headline

| Config | Correct / total | First attempt | Wrong answers returned | Abstentions | Fixed by retry | Broken by retry | p50 / p95 latency | Tokens / question | 95% CI (final) |
|---|---|---|---|---|---|---|---|---|---|
| A | 13 / 30 (43.3%) | 13 / 30 | 15 | 2 | 0 | 0 | 7.0s / 9.8s | 1993 | 27.4% to 60.8% |
| B | 17 / 30 (56.7%) | 17 / 30 | 11 | 2 | 0 | 0 | 9.2s / 18.5s | 2292 | 39.2% to 72.6% |
| C | 20 / 30 (66.7%) | 20 / 30 | 6 | 4 | 0 | 0 | 14.3s / 37.9s | 4166 | 48.8% to 80.8% |

*First attempt* = the first SQL the model wrote. *Correct* = what the user would be shown matches the reference. *Wrong answers returned* = answered, but the rows differ from the reference. *Abstentions* = no answer was given. Latency includes any rate-limit waits. With a small question set each question moves the percentages by a couple of points, so read the counts and the interval, not small differences.

## Final accuracy by category

| Category | A | B | C |
|---|---|---|---|
| aggregation | 3/10 | 4/10 | 7/10 |
| business | 1/5 | 3/5 | 3/5 |
| dates | 4/5 | 4/5 | 4/5 |
| empty | 5/5 | 5/5 | 5/5 |
| joins | 0/5 | 1/5 | 1/5 |

## Question-by-question changes (final correctness)

- A -> B: 7 questions became correct, 3 became wrong.
- B -> C: 4 questions became correct, 1 became wrong.

## Critic verdicts in config C

Judged against the reference, on attempts that ran without a database error.

| | SQL was correct | SQL was wrong |
|---|---|---|
| Critic accepted | 20 | 6 (missed errors) |
| Critic rejected | 0 (false alarms) | 0 |

## Traces

### Config A

**h_join_01** (wrong_both): How many orders were placed by female users?

- Reference SQL: `SELECT COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.gender = 'F'`
- Reference rows: [[62701]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE gender = 'female'`  
  rows: [{'order_count': 0}]

**h_join_02** (wrong_both): Which 5 brands have the most order items?

- Reference SQL: `SELECT p.brand, COUNT(*) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.brand ORDER BY 2 DESC, 1 LIMIT 5`
- Reference rows: [['Allegra K', 6292], ['Calvin Klein', 3280], ['Carhartt', 2601]] ... (5 rows)
- Attempt 0: wrong; critic n/a  
  `SELECT product_brand, COUNT(*) AS order_item_count FROM order_items JOIN inventory_items ON order_items.product_id = inventory_items.product_id GROUP BY product_brand ORDER BY order_item_count DESC LIMIT 5`  
  rows: [{'product_brand': 'Allegra K', 'order_item_count': 120826}, {'product_brand': 'Calvin Klein', 'order_item_count': 69303}, {'product_brand': 'Carhartt', 'order_item_count': 54026}] ... (5 rows)

**h_join_03** (wrong_both): How many distinct users from Texas have placed an order?

- Reference SQL: `SELECT COUNT(DISTINCT o.user_id) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.state = 'Texas'`
- Reference rows: [[1949]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT e.user_id) FROM events e JOIN users u ON e.user_id = u.id WHERE u.state = 'Texas' AND e.event_type = 'order'`  
  rows: [{'count': 0}]

**h_join_04** (wrong_both): What is the average retail price of products in the Jeans category?

- Reference SQL: `SELECT AVG(retail_price) FROM products WHERE category = 'Jeans'`
- Reference rows: [[97.85320674568013]]
- Attempt 0: wrong; critic n/a  
  `SELECT AVG(product_retail_price) AS average_retail_price FROM inventory_items WHERE product_category = 'Jeans'`  
  rows: [{'average_retail_price': 98.6567612050972}]

**h_join_05** (wrong_both): Which distribution center name supplies the most products?

- Reference SQL: `SELECT d.name, COUNT(*) FROM products p JOIN distribution_centers d ON d.id = p.distribution_center_id GROUP BY d.name ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Chicago IL', 3929]]
- Attempt 0: wrong; critic n/a  
  `SELECT distribution_centers.name, COUNT(*) AS product_count FROM inventory_items JOIN distribution_centers ON inventory_items.product_distribution_center_id = distribution_centers.id GROUP BY distribution_centers.name ORDER BY product_count DESC LIMIT 1`  
  rows: [{'name': 'Memphis TN', 'product_count': 65116}]

**h_date_04** (wrong_both): Which month of 2022 had the most orders? Give the month number.

- Reference SQL: `SELECT EXTRACT(MONTH FROM created_at)::int FROM orders WHERE created_at >= '2022-01-01' AND created_at < '2023-01-01' GROUP BY 1 ORDER BY COUNT(*) DESC, 1 LIMIT 1`
- Reference rows: [[12]]
- Attempt 0: wrong; critic n/a error: column "event_type" does not exist
LINE 1: ...number, COUNT(*) AS order_count FROM orders WHERE event_type...
            
  `SELECT EXTRACT(MONTH FROM created_at) AS month_number, COUNT(*) AS order_count FROM orders WHERE event_type = 'order' AND created_at >= '2022-01-01' AND created_at < '2023-01-01' GROUP BY EXTRACT(MONTH FROM created_at) ORDER BY order_count DESC LIMIT 1`  
  rows: none

**h_biz_01** (wrong_both): What is the total revenue from completed order items?

- Reference SQL: `SELECT SUM(sale_price) FROM order_items WHERE status = 'Complete'`
- Reference rows: [[2715783.743071355]]
- Attempt 0: wrong; critic n/a  
  `SELECT SUM(order_items.sale_price) AS total_revenue FROM order_items WHERE status = 'completed'`  
  rows: [{'total_revenue': None}]

**h_biz_02** (wrong_both): What percentage of order items were returned?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Returned') / COUNT(*) FROM order_items`
- Reference rows: [[10.030865046572659]]
- Attempt 0: wrong; critic n/a  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN status = 'returned' THEN id END) / NULLIF(COUNT(DISTINCT id), 0) AS return_percentage FROM order_items`  
  rows: [{'return_percentage': '0E-24'}]

**h_biz_03** (wrong_both): What is the average order value, counting only completed order items?

- Reference SQL: `SELECT SUM(sale_price) / COUNT(DISTINCT order_id) FROM order_items WHERE status = 'Complete'`
- Reference rows: [[86.61681900463593]]
- Attempt 0: wrong; critic n/a  
  `SELECT AVG(order_items.sale_price) AS average_order_value FROM order_items WHERE status = 'completed'`  
  rows: [{'average_order_value': None}]

**h_biz_05** (wrong_both): What is the gross margin percentage on completed order items (sale price minus product cost, divided by sale price)?

- Reference SQL: `SELECT 100.0 * SUM(oi.sale_price - p.cost) / SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete'`
- Reference rows: [[51.9158926799233]]
- Attempt 0: wrong; critic n/a  
  `SELECT (SUM(order_items.sale_price) - SUM(inventory_items.cost)) / NULLIF(SUM(order_items.sale_price), 0) * 100 AS gross_margin_percentage FROM order_items JOIN inventory_items ON order_items.inventory_item_id = inventory_items.id WHERE order_items.status = 'completed'`  
  rows: [{'gross_margin_percentage': None}]

**h_agg_01** (wrong_both): How many users have placed more than 3 orders?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) > 3) t`
- Reference rows: [[4989]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT u.id) AS user_count
FROM users u
JOIN order_items oi ON u.id = oi.user_id
GROUP BY u.id
HAVING COUNT(oi.id) > 3`  
  rows: [{'user_count': 1}, {'user_count': 1}, {'user_count': 1}] ... (20 rows)

**h_agg_05** (wrong_both): For each department, how many products are there?

- Reference SQL: `SELECT department, COUNT(*) FROM products GROUP BY department ORDER BY 1`
- Reference rows: [['Men', 13131], ['Women', 15989]]
- Attempt 0: wrong; critic n/a  
  `SELECT product_department, COUNT(*) AS product_count FROM inventory_items GROUP BY product_department`  
  rows: [{'product_department': 'Men', 'product_count': 245080}, {'product_department': 'Women', 'product_count': 245625}]

### Config B

**h_join_01** (wrong_both): How many orders were placed by female users?

- Reference SQL: `SELECT COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.gender = 'F'`
- Reference rows: [[62701]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE gender = 'female'`  
  rows: [{'order_count': 0}]

**h_join_02** (wrong_both): Which 5 brands have the most order items?

- Reference SQL: `SELECT p.brand, COUNT(*) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.brand ORDER BY 2 DESC, 1 LIMIT 5`
- Reference rows: [['Allegra K', 6292], ['Calvin Klein', 3280], ['Carhartt', 2601]] ... (5 rows)
- Attempt 0: wrong; critic n/a error: column "product_brand" does not exist
LINE 1: SELECT product_brand, COUNT(*) AS order_item_count FROM orde...
            
  `SELECT product_brand, COUNT(*) AS order_item_count FROM order_items GROUP BY product_brand ORDER BY order_item_count DESC LIMIT 5`  
  rows: none

**h_join_03** (wrong_both): How many distinct users from Texas have placed an order?

- Reference SQL: `SELECT COUNT(DISTINCT o.user_id) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.state = 'Texas'`
- Reference rows: [[1949]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT e.user_id) FROM events e JOIN users u ON e.user_id = u.id WHERE u.state = 'Texas' AND e.event_type = 'order'`  
  rows: [{'count': 0}]

**h_join_05** (wrong_both): Which distribution center name supplies the most products?

- Reference SQL: `SELECT d.name, COUNT(*) FROM products p JOIN distribution_centers d ON d.id = p.distribution_center_id GROUP BY d.name ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Chicago IL', 3929]]
- Attempt 0: wrong; critic n/a  
  `SELECT dc.name, COUNT(*) AS product_count FROM inventory_items ii JOIN distribution_centers dc ON ii.product_distribution_center_id = dc.id GROUP BY dc.name ORDER BY product_count DESC LIMIT 1`  
  rows: [{'name': 'Memphis TN', 'product_count': 65116}]

**h_date_03** (wrong_both): How many orders were shipped in 2022?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE shipped_at >= '2022-01-01' AND shipped_at < '2023-01-01'`
- Reference rows: [[18966]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE status = 'Complete' AND shipped_at IS NOT NULL AND EXTRACT(YEAR FROM shipped_at) = 2022`  
  rows: [{'order_count': 7264}]

**h_biz_02** (wrong_both): What percentage of order items were returned?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Returned') / COUNT(*) FROM order_items`
- Reference rows: [[10.030865046572659]]
- Attempt 0: wrong; critic n/a  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN order_items.status = 'returned' THEN order_items.id END) / NULLIF(COUNT(DISTINCT order_items.id), 0) AS returned_order_items_percentage FROM order_items`  
  rows: [{'returned_order_items_percentage': '0E-24'}]

**h_biz_04** (wrong_both): How many sessions contained a purchase event?

- Reference SQL: `SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type = 'purchase'`
- Reference rows: [[181759]]
- Attempt 0: wrong; critic n/a  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN session_id END) / NULLIF(COUNT(DISTINCT session_id), 0) AS conversion_rate FROM events`  
  rows: [{'conversion_rate': '26.6603007807744379'}]

**h_agg_01** (wrong_both): How many users have placed more than 3 orders?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) > 3) t`
- Reference rows: [[4989]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT user_id) AS user_count
FROM orders
WHERE status = 'Complete'
AND user_id IN (
    SELECT user_id
    FROM orders
    WHERE status = 'Complete'
    GROUP BY user_id
    HAVING COUNT(DISTINCT order_id) > 1
)`  
  rows: [{'user_count': 3309}]

**h_agg_02** (wrong_both): What is the average number of items per order?

- Reference SQL: `SELECT AVG(num_of_item) FROM orders`
- Reference rows: [[1.4514477824094039]]
- Attempt 0: wrong; critic n/a  
  `SELECT SUM(order_items.sale_price) / COUNT(DISTINCT order_items.order_id) AS average_items_per_order FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'average_items_per_order': 86.61681900463593}]

**h_agg_06** (wrong_both): How many users have never placed an order?

- Reference SQL: `SELECT COUNT(*) FROM users u WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)`
- Reference rows: [[19956]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS user_count FROM users WHERE id NOT IN (SELECT DISTINCT user_id FROM orders WHERE status = 'Complete')`  
  rows: [{'user_count': 72297}]

**h_agg_07** (wrong_both): What is the average age of users by traffic source?

- Reference SQL: `SELECT traffic_source, AVG(age) FROM users GROUP BY traffic_source ORDER BY 1`
- Reference rows: [['Display', 40.653010858835145], ['Email', 41.12775419446129], ['Facebook', 40.99019944979367]] ... (5 rows)
- Attempt 0: wrong; critic n/a  
  `SELECT u.traffic_source, AVG(u.age) AS average_age FROM users u WHERE u.id IN (SELECT DISTINCT e.user_id FROM events e WHERE e.user_id IS NOT NULL) GROUP BY u.traffic_source`  
  rows: [{'traffic_source': 'Display', 'average_age': '40.6844047985235312'}, {'traffic_source': 'Search', 'average_age': '41.0698412698412698'}, {'traffic_source': 'Facebook', 'average_age': '40.866552609...

**h_agg_08** (wrong_both): Which product category has the highest average sale price per order item?

- Reference SQL: `SELECT p.category, AVG(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.category ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Outerwear & Coats', 145.13500438791422]]
- Attempt 0: wrong; critic n/a error: column "product_category" does not exist
LINE 1: SELECT product_category, AVG(sale_price) AS average_sale_pri...
         
  `SELECT product_category, AVG(sale_price) AS average_sale_price_per_order_item
FROM order_items
WHERE status = 'Complete'
GROUP BY product_category
ORDER BY average_sale_price_per_order_item DESC
LIMIT 1`  
  rows: none

### Config C

**h_join_01** (wrong_both): How many orders were placed by female users?

- Reference SQL: `SELECT COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.gender = 'F'`
- Reference rows: [[62701]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS order_count FROM orders WHERE gender = 'female'`  
  rows: [{'order_count': 0}]
  critic said: The SQL correctly counts the number of orders placed by female users based on the gender column in the orders table.

**h_join_02** (wrong_both): Which 5 brands have the most order items?

- Reference SQL: `SELECT p.brand, COUNT(*) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.brand ORDER BY 2 DESC, 1 LIMIT 5`
- Reference rows: [['Allegra K', 6292], ['Calvin Klein', 3280], ['Carhartt', 2601]] ... (5 rows)
- Attempt 0: wrong; critic rejected error: column "product_brand" does not exist
LINE 1: SELECT product_brand, COUNT(*) AS order_item_count FROM orde...
            
  `SELECT product_brand, COUNT(*) AS order_item_count FROM order_items GROUP BY product_brand ORDER BY order_item_count DESC LIMIT 5`  
  rows: none
  critic said: SQL execution failed: column "product_brand" does not exist
LINE 1: SELECT product_brand, COUNT(*) AS order_item_count FROM orde...
               ^

- Attempt 1: wrong; critic rejected error: column "product_brand" does not exist
LINE 1: SELECT product_brand, COUNT(*) AS order_item_count FROM orde...
            
  `SELECT product_brand, COUNT(*) AS order_item_count FROM order_items GROUP BY product_brand ORDER BY order_item_count DESC LIMIT 5`  
  rows: none
  critic said: SQL execution failed: column "product_brand" does not exist
LINE 1: SELECT product_brand, COUNT(*) AS order_item_count FROM orde...
               ^

- Attempt 2: wrong; critic rejected error: column "product_brand" does not exist
LINE 1: SELECT product_brand, COUNT(*) AS order_item_count FROM orde...
            
  `SELECT product_brand, COUNT(*) AS order_item_count FROM order_items GROUP BY product_brand ORDER BY order_item_count DESC LIMIT 5`  
  rows: none
  critic said: SQL execution failed: column "product_brand" does not exist
LINE 1: SELECT product_brand, COUNT(*) AS order_item_count FROM orde...
               ^


**h_join_03** (wrong_both): How many distinct users from Texas have placed an order?

- Reference SQL: `SELECT COUNT(DISTINCT o.user_id) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.state = 'Texas'`
- Reference rows: [[1949]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(DISTINCT e.user_id) FROM events e JOIN users u ON e.user_id = u.id WHERE u.state = 'Texas' AND e.event_type = 'order'`  
  rows: [{'count': 0}]
  critic said: The SQL correctly counts distinct users from Texas who placed an order.

**h_join_05** (wrong_both): Which distribution center name supplies the most products?

- Reference SQL: `SELECT d.name, COUNT(*) FROM products p JOIN distribution_centers d ON d.id = p.distribution_center_id GROUP BY d.name ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Chicago IL', 3929]]
- Attempt 0: wrong; critic accepted  
  `SELECT dc.name, COUNT(*) AS product_count FROM inventory_items ii JOIN distribution_centers dc ON ii.product_distribution_center_id = dc.id GROUP BY dc.name ORDER BY product_count DESC LIMIT 1`  
  rows: [{'name': 'Memphis TN', 'product_count': 65116}]
  critic said: The SQL correctly identifies the distribution center with the highest product count by joining inventory_items with distribution_centers and grouping by distribution center name.

**h_date_03** (wrong_both): How many orders were shipped in 2022?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE shipped_at >= '2022-01-01' AND shipped_at < '2023-01-01'`
- Reference rows: [[18966]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS order_count FROM orders WHERE status = 'Complete' AND shipped_at IS NOT NULL AND EXTRACT(YEAR FROM shipped_at) = 2022`  
  rows: [{'order_count': 7264}]
  critic said: The SQL correctly counts orders shipped in 2022 by filtering on the year of shipped_at and counting all rows.

**h_biz_02** (wrong_both): What percentage of order items were returned?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Returned') / COUNT(*) FROM order_items`
- Reference rows: [[10.030865046572659]]
- Attempt 0: wrong; critic accepted  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN order_items.status = 'returned' THEN order_items.id END) / NULLIF(COUNT(DISTINCT order_items.id), 0) AS return_rate FROM order_items`  
  rows: [{'return_rate': '0E-24'}]
  critic said: The SQL correctly calculates the percentage of returned order items.

**h_biz_05** (wrong_both): What is the gross margin percentage on completed order items (sale price minus product cost, divided by sale price)?

- Reference SQL: `SELECT 100.0 * SUM(oi.sale_price - p.cost) / SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete'`
- Reference rows: [[51.9158926799233]]
- Attempt 0: wrong; critic rejected error: canceling statement due to statement timeout
  
  `SELECT 100.0 * SUM(CASE WHEN status = 'Complete' THEN sale_price - (SELECT cost FROM inventory_items WHERE inventory_items.id = order_items.inventory_item_id) ELSE 0 END) / NULLIF(SUM(CASE WHEN status = 'Complete' THEN sale_price ELSE 0 END), 0) AS gross_margin_percentage FROM order_items`  
  rows: none
  critic said: SQL execution failed: canceling statement due to statement timeout

- Attempt 1: wrong; critic rejected error: canceling statement due to statement timeout
  
  `SELECT 100.0 * SUM(CASE WHEN status = 'Complete' THEN sale_price - (SELECT cost FROM inventory_items WHERE inventory_items.id = order_items.inventory_item_id) ELSE 0 END) / NULLIF(SUM(CASE WHEN status = 'Complete' THEN sale_price ELSE 0 END), 0) AS gross_margin_percentage FROM order_items`  
  rows: none
  critic said: SQL execution failed: canceling statement due to statement timeout

- Attempt 2: wrong; critic rejected error: canceling statement due to statement timeout
  
  `SELECT 100.0 * SUM(CASE WHEN status = 'Complete' THEN sale_price - (SELECT cost FROM inventory_items WHERE inventory_items.id = order_items.inventory_item_id) ELSE 0 END) / NULLIF(SUM(CASE WHEN status = 'Complete' THEN sale_price ELSE 0 END), 0) AS gross_margin_percentage FROM order_items`  
  rows: none
  critic said: SQL execution failed: canceling statement due to statement timeout


**h_agg_01** (wrong_both): How many users have placed more than 3 orders?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) > 3) t`
- Reference rows: [[4989]]
- Attempt 0: wrong; critic rejected error: column o.id does not exist
LINE 5: AND o.id IN (
            ^
HINT:  Perhaps you meant to reference the column "u.id".
  
  `SELECT COUNT(DISTINCT u.id) AS user_count
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.status = 'Complete'
AND o.id IN (
    SELECT DISTINCT order_id
    FROM order_items
    WHERE status = 'Complete'
)`  
  rows: none
  critic said: SQL execution failed: column o.id does not exist
LINE 5: AND o.id IN (
            ^
HINT:  Perhaps you meant to reference the column "u.id".

- Attempt 1: wrong; critic rejected error: column o.id does not exist
LINE 5: AND o.id IN (
            ^
HINT:  Perhaps you meant to reference the column "u.id".
  
  `SELECT COUNT(DISTINCT u.id) AS user_count
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.status = 'Complete'
AND o.id IN (
    SELECT DISTINCT order_id
    FROM order_items
    WHERE status = 'Complete'
)`  
  rows: none
  critic said: SQL execution failed: column o.id does not exist
LINE 5: AND o.id IN (
            ^
HINT:  Perhaps you meant to reference the column "u.id".

- Attempt 2: wrong; critic rejected error: column o.id does not exist
LINE 5: AND o.id IN (
            ^
HINT:  Perhaps you meant to reference the column "u.id".
  
  `SELECT COUNT(DISTINCT u.id) AS user_count
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.status = 'Complete'
AND o.id IN (
    SELECT DISTINCT order_id
    FROM order_items
    WHERE status = 'Complete'
)`  
  rows: none
  critic said: SQL execution failed: column o.id does not exist
LINE 5: AND o.id IN (
            ^
HINT:  Perhaps you meant to reference the column "u.id".


**h_agg_06** (wrong_both): How many users have never placed an order?

- Reference SQL: `SELECT COUNT(*) FROM users u WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)`
- Reference rows: [[19956]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS user_count FROM users WHERE id NOT IN (SELECT DISTINCT user_id FROM orders WHERE status = 'Complete')`  
  rows: [{'user_count': 72297}]
  critic said: The SQL correctly answers the question by counting users who have no corresponding entry in the orders table with status 'Complete'.

**h_agg_08** (wrong_both): Which product category has the highest average sale price per order item?

- Reference SQL: `SELECT p.category, AVG(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.category ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Outerwear & Coats', 145.13500438791422]]
- Attempt 0: wrong; critic rejected error: column "product_category" does not exist
LINE 1: SELECT product_category, AVG(sale_price) AS average_sale_pri...
         
  `SELECT product_category, AVG(sale_price) AS average_sale_price_per_order_item
FROM order_items
WHERE status = 'Complete'
GROUP BY product_category
ORDER BY average_sale_price_per_order_item DESC
LIMIT 1`  
  rows: none
  critic said: SQL execution failed: column "product_category" does not exist
LINE 1: SELECT product_category, AVG(sale_price) AS average_sale_pri...
               ^

- Attempt 1: wrong; critic rejected error: column "product_category" does not exist
LINE 1: SELECT product_category, AVG(sale_price) AS average_sale_pri...
         
  `SELECT product_category, AVG(sale_price) AS average_sale_price_per_order_item FROM order_items WHERE status = 'Complete' GROUP BY product_category ORDER BY average_sale_price_per_order_item DESC LIMIT 1`  
  rows: none
  critic said: SQL execution failed: column "product_category" does not exist
LINE 1: SELECT product_category, AVG(sale_price) AS average_sale_pri...
               ^

- Attempt 2: wrong; critic rejected error: column "product_category" does not exist
LINE 1: SELECT product_category, AVG(sale_price) AS average_sale_pri...
         
  `SELECT product_category, AVG(sale_price) AS average_sale_price_per_order_item FROM order_items WHERE status = 'Complete' GROUP BY product_category ORDER BY average_sale_price_per_order_item DESC LIMIT 1`  
  rows: none
  critic said: SQL execution failed: column "product_category" does not exist
LINE 1: SELECT product_category, AVG(sale_price) AS average_sale_pri...
               ^

