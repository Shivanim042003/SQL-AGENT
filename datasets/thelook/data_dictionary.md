# Data Dictionary -- TheLook eCommerce

Written from direct verification against the real loaded database, not
external documentation -- every table, column, row count, and foreign key
relationship below was checked against actual data during this project's
build, not assumed from the dataset's public schema.

## users
100,000 rows. Customer demographics: `first_name`, `last_name`, `email`,
`age`, `gender`, location (`state`, `street_address`, `postal_code`, `city`,
`country`, `latitude`, `longitude`), `traffic_source` (original acquisition
channel), `created_at`. Primary key `id` -- confirmed unique, zero nulls.

## orders
125,226 rows. One row per order: `order_id`, `user_id`, `status`, `gender`,
`created_at`, `shipped_at`, `delivered_at`, `returned_at`, `num_of_item`.
`order_id` confirmed unique, zero nulls. Every `user_id` confirmed to match
a real row in `users` -- zero orphaned orders.

Status lifecycle timestamps are real and load correctly as
`timestamp with time zone` -- no type-fixing needed after load, despite an
early exploratory pass suggesting some might infer as numeric due to high
null rates (`returned_at` 89.99% null, `delivered_at` 64.96% null,
`shipped_at` 34.95% null). That inference issue only affected chunked
*exploration* sampling, not the actual load.

## order_items
181,759 rows. One row per item within an order -- an order with 3 products
has 3 rows here. `order_id`, `user_id`, `product_id`, `inventory_item_id`,
its own separate `status`/`shipped_at`/`delivered_at`/`returned_at` lifecycle
(distinct from the order-level one -- a whole order can show one status
while an individual item within it shows another), `sale_price`.

Every foreign key confirmed clean: `order_id`, `user_id`, `product_id`, and
`inventory_item_id` all match real rows in their respective tables, zero
orphans across 181,759 rows.

## products
29,120 rows. Catalog: `category`, `name`, `brand`, `department`,
`retail_price`, `sku`, `distribution_center_id`, and its own `cost` column.
`id` confirmed unique, zero nulls.

**Note:** `cost` also exists independently on `inventory_items`, duplicated
rather than only living in one place. For margin-related questions,
`products.cost` is the catalog-level expected cost; `inventory_items.cost`
is the actual cost recorded per physical unit -- decide explicitly which is
authoritative for a given question rather than assuming they're always identical.

## inventory_items
490,705 rows. Individual physical inventory units: `product_id`,
`created_at`, `sold_at` (62.96% null -- unsold inventory), `cost`, plus
duplicated copies of several product fields (`product_category`,
`product_name`, `product_brand`, `product_retail_price`, `product_department`,
`product_sku`) for query convenience, and `product_distribution_center_id`.
Every `product_id` confirmed to match a real row in `products`.

## distribution_centers
10 rows -- genuinely tiny compared to every other table. Warehouse/
fulfillment locations: `id`, `name` (e.g. "Memphis TN", "Chicago IL"),
`latitude`, `longitude`. No nulls, no duplicates.

## events
2,431,963 rows -- by far the largest table (roughly 5x `inventory_items`,
the next largest). Web/clickstream log: `id`, `user_id`, `sequence_number`
(order within a session), `session_id`, `created_at`, `ip_address`, `city`,
`state`, `postal_code`, `browser`, `traffic_source` (per-session, can differ
from the user's original acquisition channel on `users.traffic_source`),
`uri`, `event_type`.

Real `event_type` values, confirmed against the live database: `cancel`,
`cart`, `department`, `home`, `product`, `purchase`.

**`user_id` is 46.29% null -- confirmed to be anonymous, pre-login browsing
activity, not a data quality defect.** Every non-null `user_id` matches a
real row in `users` with zero exceptions -- the null rate is the complete
explanation, nothing else is hiding in the populated values. Any question
joining `events` to `users` by `user_id` will structurally exclude close to
half of all events; use `session_id` instead wherever the question doesn't
specifically require identifying a known user.

`city` is separately 0.95% null, unrelated to the `user_id` null pattern.

---
*Every table, row count, and relationship above was directly verified
against the live database during this project -- not assumed from the
dataset's original documentation.*
