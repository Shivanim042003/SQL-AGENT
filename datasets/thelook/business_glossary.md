# Business Glossary -- TheLook eCommerce

Definitions used throughout this project. The Retriever cites this file
directly when answering definitional questions, so precision here matters --
an ambiguous definition becomes an ambiguous answer downstream.

## Average order value (AOV)
Sum of `order_items.sale_price` for orders with `status = 'Complete'`,
divided by the count of distinct `order_id`s. Uses `order_items.status`
(the item-level status), not `orders.status` -- the two can disagree for a
given order, and this definition should be applied consistently once actual
queries are written against it.

## Repeat purchase rate
Percentage of users (`users.id`) with more than one order at
`status = 'Complete'`, out of all users with at least one order of any
status. Simpler than a dataset with a customer_id/customer_unique_id split
-- one id per real person here, confirmed via the `orders.user_id ->
users.id` relationship having zero orphans.

## Active user
A user who placed at least one order in the trailing 90 days from the
reference date, based on `orders.created_at`.

## Churned user
A user who was active (per the definition above) in some prior 90-day
window but has placed no order in the current one.

## Conversion rate
Percentage of sessions (`events.session_id`) that include at least one
event with `event_type = 'purchase'`, out of all distinct sessions.
Deliberately keyed on `session_id`, not `user_id` -- `events.user_id` is
46.29% null (anonymous, pre-login browsing), so a `user_id`-based definition
would silently exclude nearly half of all sessions from ever being counted.

Real `event_type` values, confirmed against the live database: `cancel`,
`cart`, `department`, `home`, `product`, `purchase`. `department` and
`product` are browsing/navigation events; `cart` and `purchase` are the two
that matter for funnel tracking.

## Cart abandonment rate
Percentage of sessions that reach an `event_type = 'cart'` event but never
reach an `event_type = 'purchase'` event within that same session. Same
reasoning as conversion rate: keyed on `session_id` specifically to remain
accurate across anonymous and identified sessions alike.

## Order-level vs. item-level status
`orders.status` and `order_items.status` are tracked independently, not
duplicated data. A single order can show one overall status while an
individual item within it shows a different one (e.g. a mostly-fulfilled
order with one returned item). Any question about "order status" should
specify which level it means; when ambiguous, item-level (`order_items.status`)
is generally more precise for financial questions (AOV, revenue), since
`sale_price` lives at the item level.

## Cost vs. retail price
`products.retail_price` is the catalog price a customer pays.
`products.cost` and `inventory_items.cost` both exist independently --
the former is the catalog-level expected cost, the latter the cost recorded
per physical inventory unit. Margin questions should specify which is meant
rather than assuming they're interchangeable.

---
*Verified against the real loaded database, including confirming every
relevant foreign key relationship has zero orphaned rows. Refine further
once the agent's actual query results are validated against these
definitions in practice.*
