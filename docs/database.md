# Database

Firestore-backed shared state for table status, orders, and entrance queue data.

## Collections

| Collection | Document ID | Purpose |
|------------|-------------|---------|
| `tables` | `0`, `1`, ... | Table status, order items, delivery flags |
| `restaurant_state` | `current` | Customers waiting at entrance (collaborator robots) |

## Order lifecycle

| Step | Behavior | Repository call | Firestore change |
|------|----------|-----------------|------------------|
| Seat customer | `introduce_table` | `assign_table()` | `status=occupied`, `has_ordered=false` |
| Take order | `take_order` | `save_order()` | `has_ordered=true`, `order_ready=false` |
| Mark ready | `mark_order_ready` | `mark_order_ready()` | `order_ready=true` |
| Deliver | `collect_order` | `mark_order_delivered()` | table reset to empty |

There is no separate kitchen team in this project. `mark_order_ready` behavior
simulates the kitchen step by promoting pending orders to ready in Firestore so
`collect_order` can pick them up.

## Setup

1. Add your Firebase service account JSON to `configs/security_key.json`.
2. Install dependencies: `conda activate steel-city-restaurant` then `pip install firebase-admin pyyaml`.
3. Seed default documents: `python scripts/database/seed.py`.
4. Verify connection and full order loop: `python scripts/database/test_connection.py`.

## Usage from behaviors

```python
from scripts.database.repository import RestaurantDatabase

db = RestaurantDatabase()
table_id = db.find_table_needing_order()
if table_id is not None:
    db.save_order(table_id, items=["coffee", "sandwich"], notes="no dairy")

pending = db.find_table_with_pending_order()
if pending is not None:
    db.mark_order_ready(pending)
```

See `scripts/database/repository.py` for the full API.
