# Integration interfaces

Authoritative contracts between subsystems. See also
[docs/TEAM_LEAD_INTEGRATION_GUIDE.md](TEAM_LEAD_INTEGRATION_GUIDE.md) (local, gitignored).

## Navigation

All robot movement uses one ROS service:

```
Service:  /navigation/navigate_to_waypoint
Type:     turtlebot4_steel_city_competition/srv/NavigateToWaypoint
Request:  string destination   # key from configs/waypoints.yaml
Response: bool success, string message
```

**Consumers:** ROS behaviors (via `NavigationClient` in `turtlebot4_run.py`),
`scripts/speech/tools.py`, waypoint GUI (`scripts/nav/record_waypoints.py`).

**Do not** call Nav2 or publish goals directly from behavior code.

Behaviors publish nav intent via `shared_state`:

| Key | Set by | Meaning |
|-----|--------|---------|
| `target_location` | `set_navigation_target()` | Current leg: `entrance`, `barista`, `table_N` |
| `next_target_location` | multi-leg behaviors | Second leg after first completes |
| `current_table_id` | table behaviors | Vision context at a table |
| `delivery_table_id` | collect_order | Table being delivered to |

Coordinator runs `drive_navigation()` after each behavior step.

## Speech

| Interface | Method | Used by |
|-----------|--------|---------|
| STT | `get_next_utterance(timeout)` | behaviors via `speech_utils.ask()` |
| TTS | `generate_speech` / `speak` | behaviors via `speech_utils.say()` |
| LLM | `OrderTaker.chat(text)` | `take_order` |

## Database (robot schema)

Firestore collections: `tables/{0..4}`, `restaurant_state/current`.

Kitchen **must** mark ready on robot schema: `RestaurantDatabase.mark_order_ready(table_id)`.

Webapp schema (`tables/t_01`, etc.) is separate — use `scripts/trial/kitchen_mark_ready.py`
for autonomous demo.

## Canonical waypoint names

`entrance`, `barista`, `table_1` … `table_5`, `docking_station`

Not: `kitchen_bar`, `table 1`, `Table 1`
