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

Question set fingerprint: `c15bfb4ba4d7`

## Headline

| Config | Correct / total | First attempt | Wrong answers returned | Abstentions | Fixed by retry | Broken by retry | p50 / p95 latency | Tokens / question | 95% CI (final) |
|---|---|---|---|---|---|---|---|---|---|
| A | 16 / 30 (53.3%) | 16 / 30 | 13 | 1 | 0 | 0 | 8.6s / 18.2s | 2003 | 36.1% to 69.8% |
| B | 21 / 30 (70.0%) | 21 / 30 | 7 | 2 | 0 | 0 | 8.7s / 12.0s | 2317 | 52.1% to 83.3% |
| C | 19 / 30 (63.3%) | 20 / 30 | 10 | 1 | 0 | 1 | 11.1s / 32.5s | 4583 | 45.5% to 78.1% |

*First attempt* = the first SQL the model wrote. *Correct* = what the user would be shown matches the reference. *Wrong answers returned* = answered, but the rows differ from the reference. *Abstentions* = no answer was given. Latency includes any rate-limit waits. With a small question set each question moves the percentages by a couple of points, so read the counts and the interval, not small differences.

## Final accuracy by category

| Category | A | B | C |
|---|---|---|---|
| aggregation | 5/10 | 8/10 | 8/10 |
| business | 1/5 | 1/5 | 0/5 |
| dates | 5/5 | 5/5 | 5/5 |
| empty | 4/5 | 5/5 | 5/5 |
| joins | 1/5 | 2/5 | 1/5 |

## Question-by-question changes (final correctness)

- A -> B: 5 questions became correct, 0 became wrong.
- B -> C: 0 questions became correct, 2 became wrong.

## Critic verdicts in config C

Judged against the reference, on attempts that ran without a database error.

| | SQL was correct | SQL was wrong |
|---|---|---|
| Critic accepted | 19 | 10 (missed errors) |
| Critic rejected | 1 (false alarms) | 5 |

## Traces

### Config A

**g_join_02** (wrong_both): What is the total sale price of order items for products from the brand Allegra K?

- Reference SQL: `SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.brand = 'Allegra K'`
- Reference rows: [[90115.1000084877]]
- Attempt 0: wrong; critic n/a  
  `SELECT SUM(order_items.sale_price) AS total_sale_price FROM order_items JOIN inventory_items ON order_items.product_id = inventory_items.product_id WHERE inventory_items.product_brand = 'Allegra K'`  
  rows: [{'total_sale_price': 1751172.0306258202}]

**g_join_03** (wrong_both): How many distinct products have been ordered by users from Brazil?

- Reference SQL: `SELECT COUNT(DISTINCT oi.product_id) FROM order_items oi JOIN users u ON u.id = oi.user_id WHERE u.country = 'Brasil'`
- Reference rows: [[17313]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT product_id) AS distinct_products_ordered
FROM order_items
WHERE status = 'delivered' AND EXISTS (
    SELECT 1
    FROM users
    WHERE users.id = order_items.user_id AND users.country = 'Brazil'
)`  
  rows: [{'distinct_products_ordered': 0}]

**g_join_04** (wrong_both): What is the average sale price of order items bought by male users?

- Reference SQL: `SELECT AVG(oi.sale_price) FROM order_items oi JOIN users u ON u.id = oi.user_id WHERE u.gender = 'M'`
- Reference rows: [[63.20037702445353]]
- Attempt 0: wrong; critic n/a  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items JOIN users ON order_items.user_id = users.id WHERE users.gender = 'male'`  
  rows: [{'average_sale_price': None}]

**g_join_05** (wrong_both): Which distribution center name has the highest total retail price across its products?

- Reference SQL: `SELECT d.name, SUM(p.retail_price) FROM products p JOIN distribution_centers d ON d.id = p.distribution_center_id GROUP BY d.name ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Houston TX', 255746.1000008583]]
- Attempt 0: wrong; critic n/a  
  `SELECT dc.name, SUM(ii.product_retail_price) AS total_retail_price FROM inventory_items ii JOIN distribution_centers dc ON ii.product_distribution_center_id = dc.id GROUP BY dc.name ORDER BY total_retail_price DESC LIMIT 1`  
  rows: [{'name': 'Houston TX', 'total_retail_price': 4257835.620954514}]

**g_biz_01** (wrong_both): What percentage of orders were returned?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Returned') / COUNT(*) FROM orders`
- Reference rows: [[10.00590931595675]]
- Attempt 0: wrong; critic n/a  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN status = 'returned' THEN order_id END) / NULLIF(COUNT(DISTINCT order_id), 0) AS return_rate FROM order_items`  
  rows: [{'return_rate': '0E-24'}]

**g_biz_02** (wrong_both): What is the cancellation rate of orders, as a percentage?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Cancelled') / COUNT(*) FROM orders`
- Reference rows: [[14.860332518805999]]
- Attempt 0: wrong; critic n/a  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN orders.status = 'cancelled' THEN orders.order_id END) / NULLIF(COUNT(DISTINCT orders.order_id), 0) AS cancellation_rate FROM orders`  
  rows: [{'cancellation_rate': '0E-24'}]

**g_biz_04** (wrong_both): What is the total revenue from completed order items for products in the Men department?

- Reference SQL: `SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete' AND p.department = 'Men'`
- Reference rows: [[1449385.9812016487]]
- Attempt 0: wrong; critic n/a  
  `SELECT SUM(order_items.sale_price) AS total_revenue
FROM order_items
JOIN inventory_items ON order_items.product_id = inventory_items.product_id
WHERE inventory_items.product_department = 'Men' AND order_items.status = 'completed'`  
  rows: [{'total_revenue': None}]

**g_biz_05** (wrong_both): What is the average profit per completed order item, meaning sale price minus product cost?

- Reference SQL: `SELECT AVG(oi.sale_price - p.cost) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete'`
- Reference rows: [[30.91327092178574]]
- Attempt 0: wrong; critic n/a  
  `SELECT AVG(order_items.sale_price - inventory_items.cost) AS average_profit_per_order_item FROM order_items JOIN inventory_items ON order_items.inventory_item_id = inventory_items.id WHERE order_items.status = 'completed'`  
  rows: [{'average_profit_per_order_item': None}]

**g_empty_01** (wrong_both): How many orders contain more than 10 items?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE num_of_item > 10`
- Reference rows: [[0]]
- Attempt 0: wrong; critic n/a  
  `SELECT order_id, COUNT(*) AS item_count
FROM order_items
GROUP BY order_id
HAVING COUNT(*) > 10`  
  rows: []

**g_agg_02** (wrong_both): What is the average number of items per order for orders placed by users under 25?

- Reference SQL: `SELECT AVG(o.num_of_item) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.age < 25`
- Reference rows: [[1.44689735303729]]
- Attempt 0: wrong; critic n/a error: column order_items.num_of_item does not exist
LINE 1: SELECT AVG(order_items.num_of_item) AS average_items_per_ord...
    
  `SELECT AVG(order_items.num_of_item) AS average_items_per_order
FROM orders
JOIN order_items ON orders.order_id = order_items.order_id
WHERE orders.user_id IN (
    SELECT id
    FROM users
    WHERE age < 25
)`  
  rows: none

**g_agg_05** (wrong_both): What is the youngest age among female users?

- Reference SQL: `SELECT MIN(age) FROM users WHERE gender = 'F'`
- Reference rows: [[12]]
- Attempt 0: wrong; critic n/a  
  `SELECT MIN(age) AS youngest_age FROM users WHERE gender = 'female'`  
  rows: [{'youngest_age': None}]

**g_agg_06** (wrong_both): How many users have placed exactly one order?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) = 1) t`
- Reference rows: [[49832]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT u.id) AS user_count
FROM users u
WHERE u.id IN (
    SELECT DISTINCT user_id
    FROM order_items
    WHERE status = 'completed'
    AND user_id IS NOT NULL
    AND order_id IN (
        SELECT order_id
        FROM orders
        WHERE status = 'completed'
    )
)
AND u.id NOT IN (
    SELECT DISTINCT user_id
    FROM order_items
    WHERE status = 'completed'
    AND user_id IS NOT NULL
    AND order_id IN (
        SELECT order_id
        FROM orders
        WHERE status = 'completed'
    )
    GROUP BY user_id
    HAVING COUNT(DISTINCT order_id) > 1
)`  
  rows: [{'user_count': 0}]

### Config B

**g_join_03** (wrong_both): How many distinct products have been ordered by users from Brazil?

- Reference SQL: `SELECT COUNT(DISTINCT oi.product_id) FROM order_items oi JOIN users u ON u.id = oi.user_id WHERE u.country = 'Brasil'`
- Reference rows: [[17313]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT product_id) AS distinct_products_ordered_from_brazil
FROM order_items
WHERE user_id IN (
    SELECT users.id
    FROM users
    WHERE country = 'Brazil'
)`  
  rows: [{'distinct_products_ordered_from_brazil': 0}]

**g_join_04** (wrong_both): What is the average sale price of order items bought by male users?

- Reference SQL: `SELECT AVG(oi.sale_price) FROM order_items oi JOIN users u ON u.id = oi.user_id WHERE u.gender = 'M'`
- Reference rows: [[63.20037702445353]]
- Attempt 0: wrong; critic n/a  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items JOIN orders ON order_items.order_id = orders.order_id WHERE orders.gender = 'male' AND order_items.status = 'Complete'`  
  rows: [{'average_sale_price': None}]

**g_join_05** (wrong_both): Which distribution center name has the highest total retail price across its products?

- Reference SQL: `SELECT d.name, SUM(p.retail_price) FROM products p JOIN distribution_centers d ON d.id = p.distribution_center_id GROUP BY d.name ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Houston TX', 255746.1000008583]]
- Attempt 0: wrong; critic n/a  
  `SELECT dc.name, SUM(oi.sale_price) AS total_retail_price FROM orders o JOIN order_items oi ON o.order_id = oi.order_id JOIN products p ON oi.product_id = p.id JOIN distribution_centers dc ON p.distribution_center_id = dc.id GROUP BY dc.name ORDER BY total_retail_price DESC LIMIT 1`  
  rows: [{'name': 'Houston TX', 'total_retail_price': 1579721.8303918839}]

**g_biz_01** (wrong_both): What percentage of orders were returned?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Returned') / COUNT(*) FROM orders`
- Reference rows: [[10.00590931595675]]
- Attempt 0: wrong; critic n/a error: missing FROM-clause entry for table "e"
LINE 1: SELECT 100.0 * COUNT(DISTINCT CASE WHEN e.returned_at IS NOT...
          
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN e.returned_at IS NOT NULL THEN o.order_id END) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS return_rate FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.status = 'Complete' AND oi.status = 'Returned'`  
  rows: none

**g_biz_02** (wrong_both): What is the cancellation rate of orders, as a percentage?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Cancelled') / COUNT(*) FROM orders`
- Reference rows: [[14.860332518805999]]
- Attempt 0: wrong; critic n/a  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN e.event_type = 'cancel' THEN e.session_id END) / NULLIF(COUNT(DISTINCT e.session_id), 0) AS cancellation_rate FROM events e WHERE e.event_type = 'cancel'`  
  rows: [{'cancellation_rate': '100.0000000000000000'}]

**g_biz_04** (wrong_both): What is the total revenue from completed order items for products in the Men department?

- Reference SQL: `SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete' AND p.department = 'Men'`
- Reference rows: [[1449385.9812016487]]
- Attempt 0: wrong; critic n/a error: column order_items.product_department does not exist
LINE 1: ...r_items WHERE order_items.status = 'Complete' AND order_  
  `SELECT SUM(order_items.sale_price) AS total_revenue FROM order_items WHERE order_items.status = 'Complete' AND order_items.product_department = 'Men'`  
  rows: none

**g_biz_05** (wrong_both): What is the average profit per completed order item, meaning sale price minus product cost?

- Reference SQL: `SELECT AVG(oi.sale_price - p.cost) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete'`
- Reference rows: [[30.91327092178574]]
- Attempt 0: wrong; critic n/a  
  `SELECT SUM(order_items.sale_price) / COUNT(DISTINCT order_items.order_id) AS average_profit_per_order_item FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'average_profit_per_order_item': 86.61681900463593}]

**g_agg_05** (wrong_both): What is the youngest age among female users?

- Reference SQL: `SELECT MIN(age) FROM users WHERE gender = 'F'`
- Reference rows: [[12]]
- Attempt 0: wrong; critic n/a  
  `SELECT MIN(age) AS youngest_age FROM users WHERE gender = 'female'`  
  rows: [{'youngest_age': None}]

**g_agg_06** (wrong_both): How many users have placed exactly one order?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) = 1) t`
- Reference rows: [[49832]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS user_count FROM users WHERE id IN (SELECT DISTINCT user_id FROM orders WHERE status = 'Complete' GROUP BY user_id HAVING COUNT(*) = 1)`  
  rows: [{'user_count': 24394}]

### Config C

**g_biz_03** (broken): How many distinct users have made a purchase?

- Reference SQL: `SELECT COUNT(DISTINCT user_id) FROM events WHERE event_type = 'purchase'`
- Reference rows: [[80044]]
- Attempt 0: correct; critic rejected  
  `SELECT COUNT(DISTINCT e.user_id) FROM events e WHERE e.event_type = 'purchase'`  
  rows: [{'count': 80044}]
  critic said: The SQL counts distinct users who generated a purchase event, but the question asks for distinct users who made a purchase, not necessarily through a purchase event.
- Attempt 1: wrong; critic accepted  
  `SELECT COUNT(DISTINCT u.id) FROM users u WHERE u.id IN (SELECT DISTINCT user_id FROM order_items WHERE status = 'Complete')`  
  rows: [{'count': 27703}]
  critic said: The SQL correctly counts distinct users who have made a purchase by filtering users whose ID exists in the order_items with status 'Complete'.

**g_join_02** (wrong_both): What is the total sale price of order items for products from the brand Allegra K?

- Reference SQL: `SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE p.brand = 'Allegra K'`
- Reference rows: [[90115.1000084877]]
- Attempt 0: wrong; critic accepted  
  `SELECT SUM(order_items.sale_price) AS total_sale_price FROM order_items JOIN inventory_items ON order_items.product_id = inventory_items.product_id WHERE inventory_items.product_brand = 'Allegra K'`  
  rows: [{'total_sale_price': 1751172.0306258202}]
  critic said: The SQL correctly calculates the total sale price of order items for products from the brand 'Allegra K'.

**g_join_03** (wrong_both): How many distinct products have been ordered by users from Brazil?

- Reference SQL: `SELECT COUNT(DISTINCT oi.product_id) FROM order_items oi JOIN users u ON u.id = oi.user_id WHERE u.country = 'Brasil'`
- Reference rows: [[17313]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(DISTINCT product_id) AS distinct_products_ordered_from_brazil
FROM order_items
WHERE user_id IN (
    SELECT DISTINCT users.id
    FROM users
    WHERE country = 'Brazil'
)`  
  rows: [{'distinct_products_ordered_from_brazil': 0}]
  critic said: The SQL correctly counts distinct products ordered by users from Brazil.

**g_join_04** (wrong_both): What is the average sale price of order items bought by male users?

- Reference SQL: `SELECT AVG(oi.sale_price) FROM order_items oi JOIN users u ON u.id = oi.user_id WHERE u.gender = 'M'`
- Reference rows: [[63.20037702445353]]
- Attempt 0: wrong; critic rejected  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items JOIN orders ON order_items.order_id = orders.order_id WHERE orders.gender = 'male' AND order_items.status = 'Complete'`  
  rows: [{'average_sale_price': None}]
  critic said: The SQL does not correctly answer the question as it averages sale prices directly from order_items without properly filtering for male users and ensuring the sale price corresponds to actual complete
- Attempt 1: wrong; critic rejected  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items JOIN orders ON order_items.order_id = orders.order_id WHERE orders.gender = 'male' AND order_items.status = 'Complete'`  
  rows: [{'average_sale_price': None}]
  critic said: The SQL does not correctly answer the question as it calculates the average sale price of order items, not the average sale price of items bought by male users.
- Attempt 2: wrong; critic rejected  
  `SELECT AVG(order_items.sale_price) AS average_sale_price FROM order_items JOIN orders ON order_items.order_id = orders.order_id WHERE orders.gender = 'male' AND order_items.status = 'Complete'`  
  rows: [{'average_sale_price': None}]
  critic said: The SQL does not correctly answer the question as it averages sale prices directly from order_items without properly filtering for male users and ensuring the sale price corresponds to male users.

**g_join_05** (wrong_both): Which distribution center name has the highest total retail price across its products?

- Reference SQL: `SELECT d.name, SUM(p.retail_price) FROM products p JOIN distribution_centers d ON d.id = p.distribution_center_id GROUP BY d.name ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Houston TX', 255746.1000008583]]
- Attempt 0: wrong; critic accepted  
  `SELECT dc.name, SUM(oi.sale_price) AS total_retail_price
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.id
JOIN distribution_centers dc ON p.distribution_center_id = dc.id
WHERE oi.status = 'delivered'
GROUP BY dc.name
ORDER BY total_retail_price DESC
LIMIT 1`  
  rows: []
  critic said: The SQL correctly answers the question by calculating the total retail price per distribution center and returning the one with the highest value.

**g_biz_01** (wrong_both): What percentage of orders were returned?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Returned') / COUNT(*) FROM orders`
- Reference rows: [[10.00590931595675]]
- Attempt 0: wrong; critic rejected error: missing FROM-clause entry for table "e"
LINE 1: SELECT 100.0 * COUNT(DISTINCT CASE WHEN e.returned_at IS NOT...
          
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN e.returned_at IS NOT NULL THEN o.order_id END) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS return_rate FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.status = 'Complete' AND oi.returned_at IS NOT NULL`  
  rows: none
  critic said: SQL execution failed: missing FROM-clause entry for table "e"
LINE 1: SELECT 100.0 * COUNT(DISTINCT CASE WHEN e.returned_at IS NOT...
                                                ^

- Attempt 1: wrong; critic rejected  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN o.returned_at IS NOT NULL THEN o.order_id END) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS return_rate FROM orders o WHERE o.status = 'Complete' AND o.returned_at IS NOT NULL`  
  rows: [{'return_rate': None}]
  critic said: The SQL does not correctly calculate the percentage of returned orders as it incorrectly filters orders with returned_at IS NOT NULL in the WHERE clause, which excludes them from the denominator.
- Attempt 2: wrong; critic accepted  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN o.returned_at IS NOT NULL THEN o.order_id END) / NULLIF(COUNT(DISTINCT o.order_id), 0) AS return_rate FROM orders o WHERE o.status = 'Complete'`  
  rows: [{'return_rate': '0E-24'}]
  critic said: The SQL correctly calculates the percentage of returned orders among complete orders.

**g_biz_02** (wrong_both): What is the cancellation rate of orders, as a percentage?

- Reference SQL: `SELECT 100.0 * COUNT(*) FILTER (WHERE status = 'Cancelled') / COUNT(*) FROM orders`
- Reference rows: [[14.860332518805999]]
- Attempt 0: wrong; critic accepted  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN e.event_type = 'cancellation' THEN e.session_id END) / NULLIF(COUNT(DISTINCT e.session_id), 0) AS cancellation_rate FROM events e`  
  rows: [{'cancellation_rate': '0E-24'}]
  critic said: The SQL calculates the cancellation rate as a percentage, which answers the question.

**g_biz_04** (wrong_both): What is the total revenue from completed order items for products in the Men department?

- Reference SQL: `SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete' AND p.department = 'Men'`
- Reference rows: [[1449385.9812016487]]
- Attempt 0: wrong; critic rejected error: column order_items.product_department does not exist
LINE 1: ...r_items WHERE order_items.status = 'Complete' AND order_  
  `SELECT SUM(order_items.sale_price) AS total_revenue FROM order_items WHERE order_items.status = 'Complete' AND order_items.product_department = 'Men'`  
  rows: none
  critic said: SQL execution failed: column order_items.product_department does not exist
LINE 1: ...r_items WHERE order_items.status = 'Complete' AND order_item...
                                                  
- Attempt 1: wrong; critic accepted  
  `SELECT SUM(order_items.sale_price) AS total_revenue FROM order_items WHERE order_items.status = 'Complete' AND order_items.product_id = ANY (SELECT product_id FROM products WHERE department = 'Men')`  
  rows: [{'total_revenue': 2715783.743071355}]
  critic said: The SQL correctly calculates the total revenue from completed order items for products in the Men department.

**g_biz_05** (wrong_both): What is the average profit per completed order item, meaning sale price minus product cost?

- Reference SQL: `SELECT AVG(oi.sale_price - p.cost) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete'`
- Reference rows: [[30.91327092178574]]
- Attempt 0: wrong; critic rejected  
  `SELECT SUM(order_items.sale_price) / COUNT(DISTINCT order_items.order_id) AS average_profit_per_order
FROM order_items
WHERE order_items.status = 'Complete'`  
  rows: [{'average_profit_per_order': 86.61681900463593}]
  critic said: The SQL does not calculate profit per completed order item; it calculates the sum of sale prices divided by the count of order IDs, which is not equivalent to profit per item.
- Attempt 1: wrong; critic accepted  
  `SELECT SUM(order_items.sale_price - inventory_items.cost) / COUNT(DISTINCT order_items.order_id) AS average_profit_per_order FROM order_items JOIN inventory_items ON order_items.inventory_item_id = inventory_items.id WHERE order_items.status = 'Complete'`  
  rows: [{'average_profit_per_order': 44.967894797210015}]
  critic said: The SQL calculates the average profit per completed order by dividing total profit by distinct order IDs, which aligns with the question's request for average profit per completed order item.

**g_agg_05** (wrong_both): What is the youngest age among female users?

- Reference SQL: `SELECT MIN(age) FROM users WHERE gender = 'F'`
- Reference rows: [[12]]
- Attempt 0: wrong; critic accepted  
  `SELECT MIN(age) AS youngest_age FROM users WHERE gender = 'female'`  
  rows: [{'youngest_age': None}]
  critic said: The SQL correctly answers the question by finding the minimum age among female users.

**g_agg_06** (wrong_both): How many users have placed exactly one order?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) = 1) t`
- Reference rows: [[49832]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS user_count FROM users WHERE id IN (SELECT DISTINCT user_id FROM orders WHERE status = 'Complete' GROUP BY user_id HAVING COUNT(*) = 1)`  
  rows: [{'user_count': 24394}]
  critic said: The SQL correctly counts the number of users who have placed exactly one order.
