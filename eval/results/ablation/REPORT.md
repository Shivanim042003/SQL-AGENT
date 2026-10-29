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

Question set fingerprint: `2bf45cd73ab2`

## Headline

| Config | Correct / total | First attempt | Wrong answers returned | Abstentions | Fixed by retry | Broken by retry | p50 / p95 latency | Tokens / question | 95% CI (final) |
|---|---|---|---|---|---|---|---|---|---|
| A | 19 / 42 (45.2%) | 19 / 42 | 22 | 1 | 0 | 0 | 50.5s / 59.1s | 1936 | 31.2% to 60.1% |
| B | 20 / 42 (47.6%) | 20 / 42 | 18 | 4 | 0 | 0 | 70.9s / 75.6s | 2236 | 33.4% to 62.3% |
| C | 24 / 42 (57.1%) | 20 / 42 | 15 | 3 | 4 | 0 | 85.2s / 420.0s | 4865 | 42.2% to 70.9% |

*First attempt* = the first SQL the model wrote. *Correct* = what the user would be shown matches the reference. *Wrong answers returned* = answered, but the rows differ from the reference. *Abstentions* = no answer was given. Latency includes any rate-limit waits. With a small question set each question moves the percentages by a couple of points, so read the counts and the interval, not small differences.

## Final accuracy by category

| Category | A | B | C |
|---|---|---|---|
| aggregation | 3/10 | 4/10 | 6/10 |
| business | 3/10 | 5/10 | 6/10 |
| dates | 6/9 | 6/9 | 6/9 |
| empty | 5/5 | 3/5 | 5/5 |
| joins | 2/8 | 2/8 | 1/8 |

## Question-by-question changes (final correctness)

- A -> B: 5 questions became correct, 4 became wrong.
- B -> C: 6 questions became correct, 2 became wrong.

## Critic verdicts in config C

Judged against the reference, on attempts that ran without a database error.

| | SQL was correct | SQL was wrong |
|---|---|---|
| Critic accepted | 24 | 15 (missed errors) |
| Critic rejected | 0 (false alarms) | 9 |

## Traces

### Config A

**join_01** (wrong_both): How many orders were placed by users from California?

- Reference SQL: `SELECT COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.state = 'California'`
- Reference rows: [[4619]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE user_id IN (SELECT id FROM users WHERE state = 'California') AND status = 'placed'`  
  rows: [{'order_count': 0}]

**join_02** (wrong_both): What are the top 5 product categories by total sale price of order items?

- Reference SQL: `SELECT p.category, SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.category ORDER BY 2 DESC LIMIT 5`
- Reference rows: [['Outerwear & Coats', 1301570.7193508148], ['Jeans', 1253644.2118606567], ['Sweaters', 842651.470293045]] ... (5 rows)
- Attempt 0: wrong; critic n/a  
  `SELECT product_category, SUM(sale_price) AS total_sale_price FROM order_items JOIN inventory_items ON order_items.product_id = inventory_items.product_id GROUP BY product_category ORDER BY total_sale_price DESC LIMIT 5`  
  rows: [{'product_category': 'Outerwear & Coats', 'total_sale_price': 25945298.814029694}, {'product_category': 'Jeans', 'total_sale_price': 25271690.07058525}, {'product_category': 'Sweaters', 'total_sal...

**join_05** (wrong_both): How many order items were for products stocked at the Memphis TN distribution center?

- Reference SQL: `SELECT COUNT(*) FROM order_items oi JOIN products p ON p.id = oi.product_id JOIN distribution_centers d ON d.id = p.distribution_center_id WHERE d.name = 'Memphis TN'`
- Reference rows: [[24139]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_items_count
FROM order_items
JOIN inventory_items ON order_items.inventory_item_id = inventory_items.id
JOIN distribution_centers ON inventory_items.product_distribution_center_id = distribution_centers.id
WHERE distribution_centers.name = 'Memphis TN' AND order_items.status = 'completed'`  
  rows: [{'order_items_count': 0}]

**join_06** (wrong_both): Which 3 user traffic sources have the most orders, and how many orders does each have?

- Reference SQL: `SELECT u.traffic_source, COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id GROUP BY u.traffic_source ORDER BY 2 DESC LIMIT 3`
- Reference rows: [['Search', 87768], ['Organic', 18963], ['Facebook', 7242]]
- Attempt 0: wrong; critic n/a  
  `SELECT e.traffic_source, COUNT(*) AS order_count
FROM events e
JOIN order_items oi ON e.user_id = oi.user_id
WHERE e.event_type = 'order'
GROUP BY e.traffic_source
ORDER BY order_count DESC
LIMIT 3`  
  rows: []

**join_07** (wrong_both): How many users have never placed an order?

- Reference SQL: `SELECT COUNT(*) FROM users u WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)`
- Reference rows: [[19956]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS user_count FROM users WHERE id NOT IN (SELECT DISTINCT user_id FROM order_items WHERE status = 'delivered')`  
  rows: [{'user_count': 100000}]

**join_08** (wrong_both): What is the average sale price of order items for products in the Women department?

- Reference SQL: `SELECT AVG(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.department = 'Women'`
- Reference rows: [[55.9470458611899]]
- Attempt 0: wrong; critic n/a  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items JOIN inventory_items ON order_items.product_id = inventory_items.product_id WHERE inventory_items.product_department = 'Women'`  
  rows: [{'average_sale_price': 56.05091706349343}]

**date_03** (wrong_both): How many events occurred on March 15, 2023?

- Reference SQL: `SELECT COUNT(*) FROM events WHERE created_at >= '2023-03-15' AND created_at < '2023-03-16'`
- Reference rows: [[1787]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS event_count FROM events WHERE created_at >= '2023-03-15' AND created_at < '2023-04-15'`  
  rows: [{'event_count': 59550}]

**date_04** (wrong_both): How many orders were created in February 2020?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE created_at >= '2020-02-01' AND created_at < '2020-03-01'`
- Reference rows: [[492]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE created_at >= '2020-02-01' AND created_at < '2020-03-01' AND status = 'created'`  
  rows: [{'order_count': 0}]

**date_07** (wrong_both): How many orders were shipped in December 2021?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE shipped_at >= '2021-12-01' AND shipped_at < '2022-01-01'`
- Reference rows: [[1209]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE shipped_at >= '2021-12-01' AND shipped_at < '2022-01-01' AND status = 'shipped'`  
  rows: [{'order_count': 0}]

**biz_01** (wrong_both): What is the average order value?

- Reference SQL: `SELECT SUM(sale_price) / COUNT(DISTINCT order_id) FROM order_items WHERE status = 'Complete'`
- Reference rows: [[86.61681900463593]]
- Attempt 0: wrong; critic n/a  
  `SELECT AVG(order_items.sale_price) AS average_order_value FROM order_items`  
  rows: [{'average_order_value': 59.568543575559886}]

**biz_02** (wrong_both): What is the repeat purchase rate?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE completed > 1) / COUNT(*) FROM (SELECT user_id, COUNT(*) FILTER (WHERE status = 'Complete') AS completed FROM orders GROUP BY user_id) t`
- Reference rows: [[4.133976313027834]]
- Attempt 0: wrong; critic n/a  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN e1.event_type = 'purchase' THEN e1.session_id END) / NULLIF(COUNT(DISTINCT e1.session_id), 0) AS repeat_purchase_rate FROM events e1 JOIN events e2 ON e1.session_id = e2.session_id WHERE e1.event_type = 'purchase' AND e2.event_type = 'purchase' AND e1.id < e2.id`  
  rows: [{'repeat_purchase_rate': None}]

**biz_03** (wrong_both): What is the cart abandonment rate?

- Reference SQL: `WITH s AS (SELECT session_id, BOOL_OR(event_type = 'cart') AS carted, BOOL_OR(event_type = 'purchase') AS bought FROM events GROUP BY session_id) SELECT 100.0 * COUNT(*) FILTER (WHERE carted AND NOT bought) / NULLIF(COUNT(*) FILTER (WHERE carted), 0) FROM s`
- Reference rows: [[57.940372003906084]]
- Attempt 0: wrong; critic n/a  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN event_type = 'purchase' THEN session_id END) / NULLIF(COUNT(DISTINCT session_id), 0) AS cart_abandonment_rate FROM events WHERE event_type = 'add_to_cart'`  
  rows: [{'cart_abandonment_rate': None}]

### Config B

**join_01** (wrong_both): How many orders were placed by users from California?

- Reference SQL: `SELECT COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.state = 'California'`
- Reference rows: [[4619]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE user_id IN (SELECT id FROM users WHERE state = 'California') AND status = 'Complete'`  
  rows: [{'order_count': 1143}]

**join_02** (wrong_both): What are the top 5 product categories by total sale price of order items?

- Reference SQL: `SELECT p.category, SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.category ORDER BY 2 DESC LIMIT 5`
- Reference rows: [['Outerwear & Coats', 1301570.7193508148], ['Jeans', 1253644.2118606567], ['Sweaters', 842651.470293045]] ... (5 rows)
- Attempt 0: wrong; critic n/a error: column "sale_price" does not exist
LINE 1: SELECT product_category, SUM(sale_price) AS total_sale_price...
               
  `SELECT product_category, SUM(sale_price) AS total_sale_price FROM inventory_items GROUP BY product_category ORDER BY total_sale_price DESC LIMIT 5`  
  rows: none

**join_04** (wrong_both): What is the average age of users who have placed at least one order?

- Reference SQL: `SELECT AVG(age) FROM users WHERE id IN (SELECT DISTINCT user_id FROM orders)`
- Reference rows: [[41.026472939883064]]
- Attempt 0: wrong; critic n/a  
  `SELECT AVG(u.age) AS average_age FROM users u WHERE u.id IN (SELECT DISTINCT user_id FROM order_items WHERE status = 'Complete')`  
  rows: [{'average_age': '40.9969317402447388'}]

**join_06** (wrong_both): Which 3 user traffic sources have the most orders, and how many orders does each have?

- Reference SQL: `SELECT u.traffic_source, COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id GROUP BY u.traffic_source ORDER BY 2 DESC LIMIT 3`
- Reference rows: [['Search', 87768], ['Organic', 18963], ['Facebook', 7242]]
- Attempt 0: wrong; critic n/a  
  `SELECT e.traffic_source, COUNT(*) AS order_count
FROM events e
JOIN order_items oi ON e.user_id = oi.user_id
WHERE e.event_type = 'order' AND oi.status = 'Complete'
GROUP BY e.traffic_source
ORDER BY order_count DESC
LIMIT 3`  
  rows: []

**join_07** (wrong_both): How many users have never placed an order?

- Reference SQL: `SELECT COUNT(*) FROM users u WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)`
- Reference rows: [[19956]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS user_count FROM users WHERE id NOT IN (SELECT DISTINCT user_id FROM orders WHERE status = 'Complete')`  
  rows: [{'user_count': 72297}]

**join_08** (wrong_both): What is the average sale price of order items for products in the Women department?

- Reference SQL: `SELECT AVG(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.department = 'Women'`
- Reference rows: [[55.9470458611899]]
- Attempt 0: wrong; critic n/a  
  `SELECT AVG(sale_price) AS average_sale_price FROM order_items WHERE status = 'Complete'`  
  rows: [{'average_sale_price': 59.54490874764531}]

**date_03** (wrong_both): How many events occurred on March 15, 2023?

- Reference SQL: `SELECT COUNT(*) FROM events WHERE created_at >= '2023-03-15' AND created_at < '2023-03-16'`
- Reference rows: [[1787]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS event_count FROM events WHERE created_at >= '2023-03-15' AND created_at < '2023-04-15'`  
  rows: [{'event_count': 59550}]

**date_04** (wrong_both): How many orders were created in February 2020?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE created_at >= '2020-02-01' AND created_at < '2020-03-01'`
- Reference rows: [[492]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE created_at >= '2020-02-01' AND created_at < '2020-03-01' AND status = 'Complete'`  
  rows: [{'order_count': 113}]

**date_09** (wrong_both): For each calendar year, how many orders were created? Return the year as a number.

- Reference SQL: `SELECT EXTRACT(YEAR FROM created_at), COUNT(*) FROM orders GROUP BY 1`
- Reference rows: [[None, 3063], [2024.0, 6067], [2020.0, 8642]] ... (7 rows)
- Attempt 0: wrong; critic n/a  
  `SELECT EXTRACT(YEAR FROM created_at) AS year, COUNT(*) AS order_count FROM orders WHERE status = 'Complete' GROUP BY EXTRACT(YEAR FROM created_at)`  
  rows: [{'year': None, 'order_count': 765}, {'year': '2024', 'order_count': 1502}, {'year': '2020', 'order_count': 2186}] ... (7 rows)

**biz_02** (wrong_both): What is the repeat purchase rate?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE completed > 1) / COUNT(*) FROM (SELECT user_id, COUNT(*) FILTER (WHERE status = 'Complete') AS completed FROM orders GROUP BY user_id) t`
- Reference rows: [[4.133976313027834]]
- Attempt 0: wrong; critic n/a error: missing FROM-clause entry for table "e1"
LINE 1: SELECT 100.0 * COUNT(DISTINCT CASE WHEN e1.user_id IS NOT NU...
         
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN e1.user_id IS NOT NULL THEN u.id END) / NULLIF(COUNT(DISTINCT u.id), 0) AS repeat_purchase_rate FROM users u LEFT JOIN (SELECT DISTINCT user_id, order_id FROM orders WHERE status = 'Complete') o1 ON u.id = o1.user_id LEFT JOIN (SELECT DISTINCT user_id FROM orders WHERE status = 'Complete') o2 ON u.id = o2.user_id WHERE o1.user_id IS NOT NULL AND o2.user_id IS NOT NULL`  
  rows: none

**biz_03** (wrong_both): What is the cart abandonment rate?

- Reference SQL: `WITH s AS (SELECT session_id, BOOL_OR(event_type = 'cart') AS carted, BOOL_OR(event_type = 'purchase') AS bought FROM events GROUP BY session_id) SELECT 100.0 * COUNT(*) FILTER (WHERE carted AND NOT bought) / NULLIF(COUNT(*) FILTER (WHERE carted), 0) FROM s`
- Reference rows: [[57.940372003906084]]
- Attempt 0: wrong; critic n/a  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN e1.event_type = 'cart' THEN e1.session_id END) / NULLIF(COUNT(DISTINCT e1.session_id), 0) AS cart_abandonment_rate FROM events e1 WHERE e1.event_type = 'cart' AND NOT EXISTS (SELECT 1 FROM events e2 WHERE e2.session_id = e1.session_id AND e2.event_type = 'purchase')`  
  rows: [{'cart_abandonment_rate': '100.0000000000000000'}]

**biz_06** (wrong_both): What is the total profit from completed order items, using the product catalog cost (products.cost)?

- Reference SQL: `SELECT SUM(oi.sale_price - p.cost) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete'`
- Reference rows: [[1409923.3734717271]]
- Attempt 0: wrong; critic n/a  
  `SELECT SUM(order_items.sale_price) AS total_profit FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'total_profit': 2715783.743071355}]

### Config C

**biz_06** (fixed): What is the total profit from completed order items, using the product catalog cost (products.cost)?

- Reference SQL: `SELECT SUM(oi.sale_price - p.cost) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete'`
- Reference rows: [[1409923.3734717271]]
- Attempt 0: wrong; critic rejected  
  `SELECT SUM(order_items.sale_price) AS total_profit FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'total_profit': 2715783.743071355}]
  critic said: The SQL does not calculate profit using the product catalog cost; it sums sale prices instead of calculating profit as sale_price minus cost.
- Attempt 1: correct; critic accepted  
  `SELECT SUM(order_items.sale_price - products.cost) AS total_profit FROM order_items JOIN products ON order_items.product_id = products.id WHERE order_items.status = 'Complete'`  
  rows: [{'total_profit': 1409923.3734717271}]
  critic said: The SQL correctly calculates total profit from completed order items using the product catalog cost.

**empty_04** (fixed): What is the average sale price of order items for products in the category 'Spacesuits'?

- Reference SQL: `SELECT AVG(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.category = 'Spacesuits'`
- Reference rows: [[None]]
- Attempt 0: wrong; critic rejected  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'average_sale_price': 59.54490874764531}]
  critic said: The SQL does not filter for products in the 'Spacesuits' category, so it does not answer the question.
- Attempt 1: correct; critic accepted  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items JOIN inventory_items ON order_items.product_id = inventory_items.product_id WHERE inventory_items.product_category = 'Spacesuits' AND order_items.status = 'Complete'`  
  rows: [{'average_sale_price': None}]
  critic said: The SQL correctly calculates the average sale price of order items for products in the 'Spacesuits' category.

**empty_05** (fixed): Which products have a retail price below zero?

- Reference SQL: `SELECT id FROM products WHERE retail_price < 0`
- Reference rows: []
- Attempt 0: wrong; critic rejected error: column "product_id" does not exist
LINE 1: SELECT product_id, product_name, product_retail_price FROM p...
               
  `SELECT product_id, product_name, product_retail_price FROM products WHERE product_retail_price < 0`  
  rows: none
  critic said: SQL execution failed: column "product_id" does not exist
LINE 1: SELECT product_id, product_name, product_retail_price FROM p...
               ^

- Attempt 1: correct; critic accepted  
  `SELECT id AS product_id, name AS product_name, retail_price AS product_retail_price FROM products WHERE retail_price < 0`  
  rows: []
  critic said: The SQL correctly answers the question by filtering products with a retail price below zero.

**agg_06** (fixed): How many users have placed more than 3 orders?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) > 3) t`
- Reference rows: [[4989]]
- Attempt 0: wrong; critic rejected  
  `SELECT COUNT(DISTINCT user_id) AS user_count
FROM orders
WHERE status = 'Complete' AND user_id IN (
    SELECT DISTINCT user_id
    FROM orders
    WHERE status = 'Complete'
    GROUP BY user_id
    HAVING COUNT(*) > 1
)`  
  rows: [{'user_count': 3309}]
  critic said: The SQL does not correctly answer the question. It counts users with more than one order, not users who placed more than 3 orders.
- Attempt 1: correct; critic accepted  
  `SELECT COUNT(DISTINCT user_id) AS user_count FROM orders WHERE user_id IN (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) > 3)`  
  rows: [{'user_count': 4989}]
  critic said: The SQL correctly counts the number of distinct users who have placed more than 3 orders.

**join_01** (wrong_both): How many orders were placed by users from California?

- Reference SQL: `SELECT COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.state = 'California'`
- Reference rows: [[4619]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS order_count FROM orders WHERE user_id IN (SELECT id FROM users WHERE state = 'California') AND status = 'Complete'`  
  rows: [{'order_count': 1143}]
  critic said: The SQL correctly counts the number of orders placed by users from California, assuming 'orders' table has 'user_id' and 'status' fields as referenced.

**join_02** (wrong_both): What are the top 5 product categories by total sale price of order items?

- Reference SQL: `SELECT p.category, SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.category ORDER BY 2 DESC LIMIT 5`
- Reference rows: [['Outerwear & Coats', 1301570.7193508148], ['Jeans', 1253644.2118606567], ['Sweaters', 842651.470293045]] ... (5 rows)
- Attempt 0: wrong; critic rejected error: column "sale_price" does not exist
LINE 1: SELECT product_category, SUM(sale_price) AS total_sale_price...
               
  `SELECT product_category, SUM(sale_price) AS total_sale_price FROM inventory_items GROUP BY product_category ORDER BY total_sale_price DESC LIMIT 5`  
  rows: none
  critic said: SQL execution failed: column "sale_price" does not exist
LINE 1: SELECT product_category, SUM(sale_price) AS total_sale_price...
                                     ^

- Attempt 1: wrong; critic accepted  
  `SELECT product_category, SUM(order_items.sale_price) AS total_sale_price FROM order_items JOIN inventory_items ON order_items.product_id = inventory_items.id GROUP BY product_category ORDER BY total_sale_price DESC LIMIT 5`  
  rows: [{'product_category': 'Intimates', 'total_sale_price': 854511.1507217884}, {'product_category': 'Tops & Tees', 'total_sale_price': 791472.4309318066}, {'product_category': 'Jeans', 'total_sale_pric...
  critic said: The SQL correctly answers the question by aggregating total sale price per product category and ordering them in descending order.

**join_03** (wrong_both): How many distinct users have bought a product from the brand Calvin Klein?

- Reference SQL: `SELECT COUNT(DISTINCT oi.user_id) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.brand = 'Calvin Klein'`
- Reference rows: [[3199]]
- Attempt 0: wrong; critic rejected error: column oi.product_brand does not exist
LINE 1: ..._id = oi.user_id WHERE oi.status = 'Complete' AND oi.product...
        
  `SELECT COUNT(DISTINCT e.user_id) FROM events e JOIN order_items oi ON e.user_id = oi.user_id WHERE oi.status = 'Complete' AND oi.product_brand = 'Calvin Klein'`  
  rows: none
  critic said: SQL execution failed: column oi.product_brand does not exist
LINE 1: ..._id = oi.user_id WHERE oi.status = 'Complete' AND oi.product...
                                                             ^

- Attempt 1: wrong; critic rejected error: column oi.product_brand does not exist
LINE 1: ..._id = oi.user_id WHERE oi.status = 'Complete' AND oi.product...
        
  `SELECT COUNT(DISTINCT e.user_id) FROM events e JOIN order_items oi ON e.user_id = oi.user_id WHERE oi.status = 'Complete' AND oi.product_brand = 'Calvin Klein'`  
  rows: none
  critic said: SQL execution failed: column oi.product_brand does not exist
LINE 1: ..._id = oi.user_id WHERE oi.status = 'Complete' AND oi.product...
                                                             ^

- Attempt 2: wrong; critic rejected error: column oi.product_brand does not exist
LINE 1: ..._id = oi.user_id WHERE oi.status = 'Complete' AND oi.product...
        
  `SELECT COUNT(DISTINCT e.user_id) FROM events e JOIN order_items oi ON e.user_id = oi.user_id WHERE oi.status = 'Complete' AND oi.product_brand = 'Calvin Klein'`  
  rows: none
  critic said: SQL execution failed: column oi.product_brand does not exist
LINE 1: ..._id = oi.user_id WHERE oi.status = 'Complete' AND oi.product...
                                                             ^


**join_04** (wrong_both): What is the average age of users who have placed at least one order?

- Reference SQL: `SELECT AVG(age) FROM users WHERE id IN (SELECT DISTINCT user_id FROM orders)`
- Reference rows: [[41.026472939883064]]
- Attempt 0: wrong; critic accepted  
  `SELECT AVG(u.age) AS average_age FROM users u WHERE u.id IN (SELECT DISTINCT user_id FROM order_items WHERE status = 'Complete')`  
  rows: [{'average_age': '40.9969317402447388'}]
  critic said: The SQL correctly calculates the average age of users who have placed at least one order.

**join_06** (wrong_both): Which 3 user traffic sources have the most orders, and how many orders does each have?

- Reference SQL: `SELECT u.traffic_source, COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id GROUP BY u.traffic_source ORDER BY 2 DESC LIMIT 3`
- Reference rows: [['Search', 87768], ['Organic', 18963], ['Facebook', 7242]]
- Attempt 0: wrong; critic rejected  
  `SELECT e.traffic_source, COUNT(*) AS order_count
FROM events e
JOIN order_items oi ON e.user_id = oi.user_id
WHERE e.event_type = 'order' AND oi.status = 'Complete'
GROUP BY e.traffic_source
ORDER BY order_count DESC
LIMIT 3`  
  rows: []
  critic said: The SQL does not correctly answer the question as it references 'order_items' and 'event_type = 'order'', which are not mentioned in the user question.
- Attempt 1: wrong; critic rejected  
  `SELECT e.traffic_source, COUNT(*) AS order_count
FROM events e
JOIN order_items oi ON e.user_id = oi.user_id
WHERE e.event_type = 'order' AND oi.status = 'Complete'
GROUP BY e.traffic_source
ORDER BY order_count DESC
LIMIT 3`  
  rows: []
  critic said: The SQL does not correctly answer the question as it references 'order_items' and 'event_type = 'order'', which are not mentioned in the user question.
- Attempt 2: wrong; critic accepted  
  `SELECT e.traffic_source, COUNT(*) AS order_count
FROM events e
JOIN order_items oi ON e.user_id = oi.user_id
WHERE oi.status = 'Complete'
GROUP BY e.traffic_source
ORDER BY order_count DESC
LIMIT 3`  
  rows: [{'traffic_source': 'Email', 'order_count': 556907}, {'traffic_source': 'Adwords', 'order_count': 375256}, {'traffic_source': 'Facebook', 'order_count': 128366}]
  critic said: The SQL correctly answers the question by counting orders associated with traffic sources and returning the top 3.

**join_07** (wrong_both): How many users have never placed an order?

- Reference SQL: `SELECT COUNT(*) FROM users u WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id)`
- Reference rows: [[19956]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS user_count FROM users WHERE id NOT IN (SELECT DISTINCT user_id FROM orders WHERE status = 'Complete')`  
  rows: [{'user_count': 72297}]
  critic said: The SQL correctly answers the question by counting users who have no corresponding entries in the orders table with status 'Complete'.

**join_08** (wrong_both): What is the average sale price of order items for products in the Women department?

- Reference SQL: `SELECT AVG(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.department = 'Women'`
- Reference rows: [[55.9470458611899]]
- Attempt 0: wrong; critic rejected  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'average_sale_price': 59.54490874764531}]
  critic said: The SQL does not filter for products in the Women department, so it does not answer the question.
- Attempt 1: wrong; critic accepted  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items JOIN inventory_items ON order_items.product_id = inventory_items.product_id WHERE inventory_items.product_department = 'Women' AND order_items.status = 'Complete'`  
  rows: [{'average_sale_price': 55.364239104860715}]
  critic said: The SQL correctly calculates the average sale price of order items for products in the Women department.

**date_03** (wrong_both): How many events occurred on March 15, 2023?

- Reference SQL: `SELECT COUNT(*) FROM events WHERE created_at >= '2023-03-15' AND created_at < '2023-03-16'`
- Reference rows: [[1787]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS event_count FROM events WHERE created_at >= '2023-03-15' AND created_at < '2023-04-15'`  
  rows: [{'event_count': 59550}]
  critic said: The SQL correctly counts events that occurred on March 15, 2023, using a half-open interval.
