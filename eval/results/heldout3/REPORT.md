# Ablation results

Model: `qwen3:8b` via `ollama`. Run on 2026-10-29.

How answers are compared (rules in `eval/ablation_lib.py`):

- Column names and column order are ignored; extra columns are allowed, but every reference column must be present with the same values.
- Row order is ignored unless the question is a top-N/ordering question (marked `ordered`). Duplicate rows are kept, so row counts must match exactly.
- Numbers (int, float, decimal) compare as floats with a tolerance of 1e-4 relative or 0.011 absolute; a percentage never matches a ratio.
- Dates and timestamps compare as ISO text; NULL matches only NULL.
- Top-N questions where ties could change the answer are avoided in the question set rather than handled by the comparator.
- Empty results: an empty reference matches only an empty result, and a zero count or NULL must match exactly. Questions designed to return nothing should be checked by hand (`--validate-reference`) because two different queries can both return nothing on one database snapshot for different reasons.

Correctness is decided only by the reference query, never by a model's opinion. Shortcuts (hardcoded SQL and critic rules) are switched off for every configuration.

Question set fingerprint: `11b7b3f29611`

## Headline

| Config | Correct / total | First attempt | Wrong answers returned | Abstentions | Fixed by retry | Broken by retry | p50 / p95 latency | Tokens / question | 95% CI (final) |
|---|---|---|---|---|---|---|---|---|---|
| A | 18 / 30 (60.0%) | 18 / 30 | 11 | 1 | 0 | 0 | 8.4s / 13.2s | 2178 | 42.3% to 75.4% |
| B | 15 / 30 (50.0%) | 15 / 30 | 12 | 3 | 0 | 0 | 9.7s / 25.2s | 2504 | 33.2% to 66.8% |
| C | 16 / 30 (53.3%) | 14 / 30 | 14 | 0 | 2 | 0 | 12.0s / 39.9s | 4827 | 36.1% to 69.8% |

*First attempt* = the first SQL the model wrote. *Correct* = what the user would be shown matches the reference. *Wrong answers returned* = answered, but the rows differ from the reference. *Abstentions* = no answer was given. Latency includes any rate-limit waits. With a small question set each question moves the percentages by a couple of points, so read the counts and the interval, not small differences.

## Final accuracy by category

| Category | A | B | C |
|---|---|---|---|
| aggregation | 5/10 | 5/10 | 6/10 |
| business | 5/5 | 1/5 | 2/5 |
| dates | 3/5 | 2/5 | 1/5 |
| empty | 4/5 | 5/5 | 5/5 |
| joins | 1/5 | 2/5 | 2/5 |

## Question-by-question changes (final correctness)

- A -> B: 3 questions became correct, 6 became wrong.
- B -> C: 2 questions became correct, 1 became wrong.

## Critic verdicts in config C

Judged against the reference, on attempts that ran without a database error.

| | SQL was correct | SQL was wrong |
|---|---|---|
| Critic accepted | 16 | 14 (missed errors) |
| Critic rejected | 0 (false alarms) | 5 |

## Traces

### Config A

**v_join_02** (wrong_both): What is the total sale price of cancelled order items for products in the Jeans category?

- Reference SQL: `SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Cancelled' AND p.category = 'Jeans'`
- Reference rows: [[189582.40021133423]]
- Attempt 0: wrong; critic n/a  
  `SELECT SUM(order_items.sale_price) AS total_sale_price
FROM order_items
JOIN inventory_items ON order_items.product_id = inventory_items.product_id
WHERE order_items.status = 'Cancelled'
  AND inventory_items.product_category = 'Jeans'`  
  rows: [{'total_sale_price': 3840517.0145378113}]

**v_join_03** (wrong_both): How many users from China have placed at least one order?

- Reference SQL: `SELECT COUNT(DISTINCT o.user_id) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.country = 'China'`
- Reference rows: [[27387]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT u.id) FROM users u WHERE u.country = 'China' AND u.id IN (SELECT DISTINCT user_id FROM order_items WHERE status = 'Complete')`  
  rows: [{'count': 9477}]

**v_join_04** (wrong_both): Which product category has the most order items?

- Reference SQL: `SELECT p.category, COUNT(*) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.category ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Intimates', 13474]]
- Attempt 0: wrong; critic n/a  
  `SELECT product_category, COUNT(*) AS order_item_count FROM inventory_items GROUP BY product_category ORDER BY order_item_count DESC LIMIT 1`  
  rows: [{'product_category': 'Intimates', 'order_item_count': 36353}]

**v_join_05** (wrong_both): How many distinct brands have been bought by female users?

- Reference SQL: `SELECT COUNT(DISTINCT p.brand) FROM order_items oi JOIN users u ON u.id = oi.user_id JOIN products p ON p.id = oi.product_id WHERE u.gender = 'F'`
- Reference rows: [[1894]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT product_brand) AS distinct_brands
FROM inventory_items
WHERE product_brand IS NOT NULL
AND product_id IN (
    SELECT DISTINCT inventory_item_id
    FROM order_items
    WHERE status = 'Complete'
    AND user_id IN (
        SELECT id
        FROM users
        WHERE gender = 'F'
    )
)`  
  rows: [{'distinct_brands': 642}]

**v_date_03** (wrong_both): How many orders were shipped in November 2022?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE shipped_at >= '2022-11-01' AND shipped_at < '2022-12-01'`
- Reference rows: [[1924]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE shipped_at >= '2022-11-01' AND shipped_at < '2022-12-01' AND status = 'Shipped'`  
  rows: [{'order_count': 896}]

**v_date_05** (wrong_both): How many orders were created on or before 2021-12-31?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE created_at < '2022-01-01'`
- Reference rows: [[27884]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE created_at <= '2021-12-31'::timestamp with time zone`  
  rows: [{'order_count': 27843}]

**v_empty_01** (wrong_both): How many users have the traffic source Pinterest?

- Reference SQL: `SELECT COUNT(*) FROM users WHERE traffic_source = 'Pinterest'`
- Reference rows: [[0]]
- Attempt 0: wrong; critic n/a error: column "user_id" does not exist
LINE 1: SELECT COUNT(DISTINCT user_id) AS user_count FROM users WHER...
                  
  `SELECT COUNT(DISTINCT user_id) AS user_count FROM users WHERE traffic_source = 'Pinterest'`  
  rows: none

**v_agg_02** (wrong_both): Which traffic source has the most users?

- Reference SQL: `SELECT traffic_source, COUNT(*) FROM users GROUP BY traffic_source ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Search', 70075]]
- Attempt 0: wrong; critic n/a  
  `SELECT e.traffic_source, COUNT(DISTINCT e.user_id) AS user_count FROM events e GROUP BY e.traffic_source ORDER BY user_count DESC LIMIT 1`  
  rows: [{'traffic_source': 'Email', 'user_count': 52255}]

**v_agg_04** (wrong_both): How many distinct users have had more than one session?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM events WHERE user_id IS NOT NULL GROUP BY user_id HAVING COUNT(DISTINCT session_id) > 1) t`
- Reference rows: [[45048]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT e.user_id) AS distinct_users_with_more_than_one_session
FROM events e
GROUP BY e.user_id
HAVING COUNT(DISTINCT e.session_id) > 1`  
  rows: [{'distinct_users_with_more_than_one_session': 1}, {'distinct_users_with_more_than_one_session': 1}, {'distinct_users_with_more_than_one_session': 1}] ... (20 rows)

**v_agg_05** (wrong_both): How many products are there in each category?

- Reference SQL: `SELECT category, COUNT(*) FROM products GROUP BY category ORDER BY 1`
- Reference rows: [['Accessories', 1559], ['Active', 1432], ['Blazers & Jackets', 561]] ... (20 rows)
- Attempt 0: wrong; critic n/a  
  `SELECT product_category, COUNT(*) AS product_count FROM inventory_items GROUP BY product_category`  
  rows: [{'product_category': 'Accessories', 'product_count': 26367}, {'product_category': 'Active', 'product_count': 24651}, {'product_category': 'Blazers & Jackets', 'product_count': 8708}] ... (20 rows)

**v_agg_06** (wrong_both): Which 5 states have the most orders?

- Reference SQL: `SELECT u.state, COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id GROUP BY u.state ORDER BY 2 DESC, 1 LIMIT 5`
- Reference rows: [['Guangdong', 6665], ['England', 5059], ['California', 4619]] ... (5 rows)
- Attempt 0: wrong; critic n/a  
  `SELECT e.state, COUNT(*) AS order_count FROM events e JOIN order_items oi ON e.user_id = oi.user_id WHERE e.event_type = 'purchase' GROUP BY e.state ORDER BY order_count DESC LIMIT 5`  
  rows: [{'state': 'Guangdong', 'order_count': 33123}, {'state': 'England', 'order_count': 25591}, {'state': 'California', 'order_count': 22152}] ... (5 rows)

**v_agg_08** (wrong_both): How many users have placed more than one order?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING COUNT(*) > 1) t`
- Reference rows: [[30212]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT u.id) AS user_count
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.status = 'Complete' AND o.num_of_item > 1`  
  rows: [{'user_count': 9076}]

### Config B

**v_join_03** (wrong_both): How many users from China have placed at least one order?

- Reference SQL: `SELECT COUNT(DISTINCT o.user_id) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.country = 'China'`
- Reference rows: [[27387]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) FROM users WHERE country = 'China' AND id IN (SELECT DISTINCT user_id FROM orders WHERE status = 'Complete')`  
  rows: [{'count': 9477}]

**v_join_04** (wrong_both): Which product category has the most order items?

- Reference SQL: `SELECT p.category, COUNT(*) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.category ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Intimates', 13474]]
- Attempt 0: wrong; critic n/a  
  `SELECT product_category, COUNT(*) AS order_item_count FROM inventory_items GROUP BY product_category ORDER BY order_item_count DESC LIMIT 1`  
  rows: [{'product_category': 'Intimates', 'order_item_count': 36353}]

**v_join_05** (wrong_both): How many distinct brands have been bought by female users?

- Reference SQL: `SELECT COUNT(DISTINCT p.brand) FROM order_items oi JOIN users u ON u.id = oi.user_id JOIN products p ON p.id = oi.product_id WHERE u.gender = 'F'`
- Reference rows: [[1894]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT product_brand) AS distinct_brands
FROM inventory_items
WHERE product_brand IS NOT NULL
AND EXISTS (
    SELECT 1
    FROM orders o
    JOIN users u ON o.user_id = u.id
    WHERE o.status = 'Complete'
    AND u.gender = 'F'
    AND o.user_id = inventory_items.product_id
)`  
  rows: [{'distinct_brands': 1186}]

**v_date_01** (wrong_both): How many users joined in the second half of 2022?

- Reference SQL: `SELECT COUNT(*) FROM users WHERE created_at >= '2022-07-01' AND created_at < '2023-01-01'`
- Reference rows: [[9755]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) FROM users WHERE created_at >= '2022-07-01' AND created_at < '2022-12-31'`  
  rows: [{'count': 9709}]

**v_date_03** (wrong_both): How many orders were shipped in November 2022?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE shipped_at >= '2022-11-01' AND shipped_at < '2022-12-01'`
- Reference rows: [[1924]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE status = 'Shipped' AND shipped_at >= '2022-11-01' AND shipped_at < '2022-12-01'`  
  rows: [{'order_count': 896}]

**v_date_05** (wrong_both): How many orders were created on or before 2021-12-31?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE created_at < '2022-01-01'`
- Reference rows: [[27884]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(*) AS order_count FROM orders WHERE created_at <= '2021-12-31' AND status = 'Complete'`  
  rows: [{'order_count': 6981}]

**v_biz_01** (wrong_both): What is the average sale price of completed order items?

- Reference SQL: `SELECT AVG(sale_price) FROM order_items WHERE status = 'Complete'`
- Reference rows: [[59.54490874764531]]
- Attempt 0: wrong; critic n/a  
  `SELECT SUM(order_items.sale_price) / COUNT(DISTINCT order_items.order_id) AS average_sale_price FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'average_sale_price': 86.61681900463593}]

**v_biz_03** (wrong_both): What is the total revenue from completed order items for products in the Jeans category?

- Reference SQL: `SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete' AND p.category = 'Jeans'`
- Reference rows: [[314433.3105430603]]
- Attempt 0: wrong; critic n/a  
  `SELECT SUM(order_items.sale_price) AS total_revenue FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'total_revenue': 2715783.743071355}]

**v_biz_04** (wrong_both): How many distinct sessions contained a cart event?

- Reference SQL: `SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type = 'cart'`
- Reference rows: [[432146]]
- Attempt 0: wrong; critic n/a error: canceling statement due to statement timeout
  
  `SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type = 'cart' AND session_id NOT IN (SELECT DISTINCT session_id FROM events WHERE event_type = 'purchase')`  
  rows: none

**v_biz_05** (wrong_both): What is the average number of events per session?

- Reference SQL: `SELECT COUNT(*)::float / COUNT(DISTINCT session_id) FROM events`
- Reference rows: [[3.567188698645709]]
- Attempt 0: wrong; critic n/a error: canceling statement due to statement timeout
  
  `SELECT COUNT(DISTINCT session_id) AS total_sessions, COUNT(DISTINCT session_id) FILTER (WHERE session_id IN (SELECT session_id FROM events WHERE event_type = 'purchase')) AS purchased_sessions, 100.0 * COUNT(DISTINCT session_id) FILTER (WHERE session_id IN (SELECT session_id FROM events WHERE event_type = 'purchase')) / NULLIF(COUNT(DISTINCT session_id), 0) AS conversion_rate FROM events`  
  rows: none

**v_agg_04** (wrong_both): How many distinct users have had more than one session?

- Reference SQL: `SELECT COUNT(*) FROM (SELECT user_id FROM events WHERE user_id IS NOT NULL GROUP BY user_id HAVING COUNT(DISTINCT session_id) > 1) t`
- Reference rows: [[45048]]
- Attempt 0: wrong; critic n/a  
  `SELECT COUNT(DISTINCT e.user_id) AS distinct_users_with_more_than_one_session
FROM events e
JOIN (
    SELECT session_id, COUNT(*) AS session_event_count
    FROM events
    GROUP BY session_id
    HAVING COUNT(*) > 1
) sub ON e.session_id = sub.session_id`  
  rows: [{'distinct_users_with_more_than_one_session': 80044}]

**v_agg_05** (wrong_both): How many products are there in each category?

- Reference SQL: `SELECT category, COUNT(*) FROM products GROUP BY category ORDER BY 1`
- Reference rows: [['Accessories', 1559], ['Active', 1432], ['Blazers & Jackets', 561]] ... (20 rows)
- Attempt 0: wrong; critic n/a  
  `SELECT product_category, COUNT(*) AS product_count FROM inventory_items GROUP BY product_category`  
  rows: [{'product_category': 'Accessories', 'product_count': 26367}, {'product_category': 'Active', 'product_count': 24651}, {'product_category': 'Blazers & Jackets', 'product_count': 8708}] ... (20 rows)

### Config C

**v_biz_04** (fixed): How many distinct sessions contained a cart event?

- Reference SQL: `SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type = 'cart'`
- Reference rows: [[432146]]
- Attempt 0: wrong; critic rejected error: canceling statement due to statement timeout
  
  `SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type = 'cart' AND session_id NOT IN (SELECT DISTINCT session_id FROM events WHERE event_type = 'purchase')`  
  rows: none
  critic said: SQL execution failed: canceling statement due to statement timeout

- Attempt 1: wrong; critic rejected  
  `SELECT COUNT(DISTINCT e.session_id) FROM events e WHERE e.event_type = 'cart' AND e.session_id IN (SELECT DISTINCT session_id FROM events WHERE event_type = 'purchase')`  
  rows: [{'count': 181759}]
  critic said: The SQL does not answer the question correctly because it counts sessions that contained both a cart event and a purchase event, rather than sessions that contained a cart event.
- Attempt 2: correct; critic accepted  
  `SELECT COUNT(DISTINCT session_id) FROM events WHERE event_type = 'cart'`  
  rows: [{'count': 432146}]
  critic said: The SQL correctly counts distinct sessions that contained a 'cart' event.

**v_agg_07** (fixed): What is the average retail price of products in the Women department?

- Reference SQL: `SELECT AVG(retail_price) FROM products WHERE department = 'Women'`
- Reference rows: [[55.93970299050523]]
- Attempt 0: wrong; critic rejected error: column "product_retail_price" does not exist
LINE 1: SELECT AVG(product_retail_price) AS average_retail_price FRO...
     
  `SELECT AVG(product_retail_price) AS average_retail_price FROM products WHERE department = 'Women'`  
  rows: none
  critic said: SQL execution failed: column "product_retail_price" does not exist
LINE 1: SELECT AVG(product_retail_price) AS average_retail_price FRO...
                   ^

- Attempt 1: correct; critic accepted  
  `SELECT AVG(product_retail_price) AS average_retail_price FROM inventory_items WHERE product_department = 'Women'`  
  rows: [{'average_retail_price': 55.9425104053029}]
  critic said: The SQL correctly calculates the average retail price of products in the Women department.

**v_join_03** (wrong_both): How many users from China have placed at least one order?

- Reference SQL: `SELECT COUNT(DISTINCT o.user_id) FROM orders o JOIN users u ON u.id = o.user_id WHERE u.country = 'China'`
- Reference rows: [[27387]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) FROM users WHERE country = 'China' AND id IN (SELECT DISTINCT user_id FROM orders WHERE status = 'Complete')`  
  rows: [{'count': 9477}]
  critic said: The SQL correctly answers the question by counting users from China who have at least one completed order.

**v_join_04** (wrong_both): Which product category has the most order items?

- Reference SQL: `SELECT p.category, COUNT(*) FROM order_items oi JOIN products p ON p.id = oi.product_id GROUP BY p.category ORDER BY 2 DESC, 1 LIMIT 1`
- Reference rows: [['Intimates', 13474]]
- Attempt 0: wrong; critic accepted  
  `SELECT product_category, COUNT(*) AS order_item_count FROM inventory_items GROUP BY product_category ORDER BY order_item_count DESC LIMIT 1`  
  rows: [{'product_category': 'Intimates', 'order_item_count': 36353}]
  critic said: The SQL correctly identifies the product category with the most order items by counting order items per category and ordering descending.

**v_join_05** (wrong_both): How many distinct brands have been bought by female users?

- Reference SQL: `SELECT COUNT(DISTINCT p.brand) FROM order_items oi JOIN users u ON u.id = oi.user_id JOIN products p ON p.id = oi.product_id WHERE u.gender = 'F'`
- Reference rows: [[1894]]
- Attempt 0: wrong; critic rejected  
  `SELECT COUNT(DISTINCT product_brand) AS distinct_brands
FROM inventory_items
WHERE product_brand IS NOT NULL
AND EXISTS (
    SELECT 1
    FROM orders o
    JOIN users u ON o.user_id = u.id
    WHERE o.status = 'Complete'
    AND u.gender = 'F'
    AND o.user_id = inventory_items.product_id
)`  
  rows: [{'distinct_brands': 1186}]
  critic said: The SQL does not correctly answer the question as it incorrectly joins users to inventory_items via product_id, which is not a user identifier, and the logic for associating users with brands is inval
- Attempt 1: wrong; critic accepted  
  `SELECT COUNT(DISTINCT ii.product_brand) AS distinct_brands
FROM inventory_items ii
JOIN order_items oi ON ii.id = oi.inventory_item_id
JOIN orders o ON oi.order_id = o.order_id
JOIN users u ON o.user_id = u.id
WHERE o.status = 'Complete'
AND u.gender = 'F'
AND ii.product_brand IS NOT NULL`  
  rows: [{'distinct_brands': 1711}]
  critic said: The SQL correctly counts the number of distinct brands bought by female users.

**v_date_01** (wrong_both): How many users joined in the second half of 2022?

- Reference SQL: `SELECT COUNT(*) FROM users WHERE created_at >= '2022-07-01' AND created_at < '2023-01-01'`
- Reference rows: [[9755]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS user_count FROM users WHERE created_at >= '2022-07-01' AND created_at < '2022-12-31'`  
  rows: [{'user_count': 9709}]
  critic said: The SQL correctly counts users who joined in the second half of 2022.

**v_date_02** (wrong_both): How many events happened between January 1 and January 7, 2023, including both days?

- Reference SQL: `SELECT COUNT(*) FROM events WHERE created_at >= '2023-01-01' AND created_at < '2023-01-08'`
- Reference rows: [[11481]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS event_count FROM events WHERE created_at >= '2023-01-01' AND created_at < '2023-02-01'`  
  rows: [{'event_count': 52010}]
  critic said: The SQL correctly answers the question by counting events within the specified date range.

**v_date_03** (wrong_both): How many orders were shipped in November 2022?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE shipped_at >= '2022-11-01' AND shipped_at < '2022-12-01'`
- Reference rows: [[1924]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS order_count FROM orders WHERE status = 'Shipped' AND shipped_at BETWEEN '2022-11-01' AND '2022-11-30'`  
  rows: [{'order_count': 872}]
  critic said: The SQL correctly counts orders shipped in November 2022.

**v_date_05** (wrong_both): How many orders were created on or before 2021-12-31?

- Reference SQL: `SELECT COUNT(*) FROM orders WHERE created_at < '2022-01-01'`
- Reference rows: [[27884]]
- Attempt 0: wrong; critic accepted  
  `SELECT COUNT(*) AS order_count FROM orders WHERE created_at <= '2021-12-31' AND status = 'Complete'`  
  rows: [{'order_count': 6981}]
  critic said: The SQL correctly answers the question by counting completed orders created on or before 2021-12-31.

**v_biz_01** (wrong_both): What is the average sale price of completed order items?

- Reference SQL: `SELECT AVG(sale_price) FROM order_items WHERE status = 'Complete'`
- Reference rows: [[59.54490874764531]]
- Attempt 0: wrong; critic accepted  
  `SELECT SUM(order_items.sale_price) / COUNT(DISTINCT order_items.order_id) AS average_sale_price FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'average_sale_price': 86.61681900463593}]
  critic said: The SQL calculates the average sale price of completed order items, which answers the question.

**v_biz_03** (wrong_both): What is the total revenue from completed order items for products in the Jeans category?

- Reference SQL: `SELECT SUM(oi.sale_price) FROM order_items oi JOIN products p ON p.id = oi.product_id WHERE oi.status = 'Complete' AND p.category = 'Jeans'`
- Reference rows: [[314433.3105430603]]
- Attempt 0: wrong; critic rejected  
  `SELECT SUM(order_items.sale_price) AS total_revenue FROM order_items WHERE order_items.status = 'Complete'`  
  rows: [{'total_revenue': 2715783.743071355}]
  critic said: The SQL does not account for the product category filter (Jeans) or ensure that only completed order items are included.
- Attempt 1: wrong; critic accepted  
  `SELECT SUM(order_items.sale_price) AS total_revenue FROM order_items JOIN inventory_items ON order_items.product_id = inventory_items.product_id WHERE inventory_items.product_category = 'Jeans' AND order_items.status = 'Complete'`  
  rows: [{'total_revenue': 6274335.412281036}]
  critic said: The SQL correctly calculates the total revenue from completed order items for products in the Jeans category.

**v_biz_05** (wrong_both): What is the average number of events per session?

- Reference SQL: `SELECT COUNT(*)::float / COUNT(DISTINCT session_id) FROM events`
- Reference rows: [[3.567188698645709]]
- Attempt 0: wrong; critic rejected  
  `SELECT 100.0 * COUNT(DISTINCT CASE WHEN e1.session_id IS NOT NULL THEN e.session_id END) / NULLIF(COUNT(DISTINCT e.session_id), 0) AS average_events_per_session FROM events e LEFT JOIN (SELECT DISTINCT session_id FROM events WHERE event_type = 'purchase') e1 ON e.session_id = e1.session_id`  
  rows: [{'average_events_per_session': '26.6603007807744379'}]
  critic said: The SQL calculates an average number of events per session, but it incorrectly filters sessions to only those with purchase events, which is not required by the question.
- Attempt 1: wrong; critic accepted  
  `SELECT 100.0 * COUNT(*) / NULLIF(COUNT(DISTINCT session_id), 0) AS average_events_per_session FROM events`  
  rows: [{'average_events_per_session': '356.7188698645709114'}]
  critic said: The SQL correctly calculates the average number of events per session by dividing the total count of events by the count of distinct sessions.
