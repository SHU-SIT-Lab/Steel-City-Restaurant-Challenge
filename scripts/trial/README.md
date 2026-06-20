# Trial prep checklist

Operational checklist derived from `docs/TEAM_LEAD_INTEGRATION_GUIDE.md`.
Use with `scripts/trial/` helpers on integration day.

## Team roster (fill before standup)

| Owner | Subsystem | Acceptance |
|-------|-----------|------------|
| ______ | Navigation | `scripts/trial/verify_navigation.sh` |
| ______ | Database | `python3 scripts/trial/run_db_lifecycle.py` |
| ______ | Vision | YOLO smoke at entrance + table |
| ______ | Speech/LLM | STT/TTS + take_order dialogue |
| ______ | Behaviors | `behavior_triggers.py` dry runs |
| ______ | Web App | `npm run dev` live mode (optional) |
| ______ | Integration | §12 E2E trial |

## Fallback tier (agree at start)

- **Tier 1:** Full autonomous (all acceptance tests pass)
- **Tier 2:** Manual DB for vision — `simulate_customer.py`
- **Tier 3:** Staff-assisted seating — `behavior_triggers.py take_order`
- **Tier 4:** Nav + speech only

## Kitchen briefing (critical)

Robot Firestore schema uses `tables/0` … `tables/4`. Mark ready with:

```bash
python3 scripts/trial/kitchen_mark_ready.py 0
```

Do **not** rely on webapp `t_01` schema for the autonomous loop.

## Quick commands

```bash
# Database lifecycle (§6)
python3 scripts/trial/run_db_lifecycle.py

# Simulate customer (Tier 2)
python3 scripts/trial/simulate_customer.py --count 2

# Trigger behaviors (§8)
python3 scripts/trial/behavior_triggers.py take_order --table-id 0
python3 scripts/trial/behavior_triggers.py collect_order --table-id 0
python3 scripts/trial/behavior_triggers.py reset

# Pre-flight (§15)
./scripts/trial/preflight_verify.sh
```

## E2E trial steps (§12)

0. Robot localized, nav service ready  
1. check_customer → entrance  
2. Customer detected  
3. Party size asked  
4. customers_waiting >= 1  
5. introduce_table → table  
6. Table occupied in DB  
7. take_order dialogue  
8. has_ordered in DB  
9. Kitchen mark_order_ready  
10. collect_order → barista  
11. Deliver to table  
12. order_delivered, table empty  

Run twice; use skip-ahead procedures in guide §12 if a step fails.

## Sign-off

- [ ] Navigation §4  
- [ ] Database §6  
- [ ] Vision §7  
- [ ] Speech §5  
- [ ] Behaviors §8  
- [ ] E2E §12  
- [ ] **READY FOR COMPETITION**
