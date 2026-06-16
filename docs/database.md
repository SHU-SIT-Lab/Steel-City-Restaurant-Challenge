# Database

Firestore-backed shared state for table status, orders, and entrance queue data.

## Collections

| Collection | Document ID | Purpose |
|------------|-------------|---------|
| `tables` | `0`, `1`, ... | Table status, order items, delivery flags |
| `restaurant_state` | `current` | Customers waiting at entrance (collaborator robots) |

## Setup

1. Add your Firebase service account JSON to `configs/security_key.json`.
2. Install dependencies: `conda activate steel-city-restaurant` then `pip install firebase-admin pyyaml`.
3. Seed default documents: `python scripts/database/seed.py`.
4. Verify connection: `python scripts/database/test_connection.py`.

## Usage from behaviors

```python
from scripts.database.repository import RestaurantDatabase

db = RestaurantDatabase()
table_id = db.find_table_needing_order()
if table_id is not None:
    db.save_order(table_id, items=["coffee", "sandwich"], notes="no dairy")
```

See `scripts/database/repository.py` for the full API.
