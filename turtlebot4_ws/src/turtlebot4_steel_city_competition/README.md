# turtlebot4_steel_city_competition

This package is a scaffold for the TurtleBot4 restaurant workflow.
It is meant to be filled in step by step.

## Simple Idea

- `turtlebot4_run.py` starts the system.
- `behaviors/` contains the planning behaviors.
- `actions/` contains the robot action nodes.
- The runner chooses one behavior with the highest priority.
- The behavior file is only a template until the TODOs are replaced.

## What to edit

### Behaviors

These files define the behavior templates:

- `src/behaviors/check_customer_behavior.py`
- `src/behaviors/check_empty_table_behavior.py`
- `src/behaviors/introduce_table_behavior.py`
- `src/behaviors/take_order_behavior.py`
- `src/behaviors/collect_order_behavior.py`
- `src/behaviors/update_customer_number_behavior.py`

Each behavior currently contains TODO comments for the logic you need to write.

### Actions

These files are the action nodes used by the behaviors:

- `src/actions/obj_detection.py`
- `src/actions/speech_to_text.py`
- `src/actions/text_to_speech.py`

## TODO locations

### `src/actions/obj_detection.py`

- Update `table_empty` and `customer_present` from the callback.
- Replace `todo_detect_objects()` with real object detection.
- Fill in `check_customer()`.
- Fill in `check_table()`.

### `src/actions/speech_to_text.py`

- Replace `todo_run_whisper()` with real speech-to-text logic.

### `src/actions/text_to_speech.py`

- Replace `todo_run_tts()` with real text-to-speech logic.

### `src/behaviors/check_customer_behavior.py`

- Navigation to entrance.
- Vision check for new customers.
- Database update for new customer found.

### `src/behaviors/check_empty_table_behavior.py`

- Navigation to tables.
- Vision check for empty tables.
- Database update for table status.

### `src/behaviors/introduce_table_behavior.py`

- Navigation to entrance.
- Ask customer to follow.
- Table assignment update.
- Navigation to assigned table.
- Tell customer to sit and order.

### `src/behaviors/take_order_behavior.py`

- Find table with customers who have not ordered.
- Go to the table.
- Ask if they are ready to order.
- Collect order.
- Update database with the order.

### `src/behaviors/collect_order_behavior.py`

- Go to barista.
- Ask whether the order is ready.
- Go to the table.
- Ask whether the customer is done.
- Update database when order is delivered.

### `src/behaviors/update_customer_number_behavior.py`

- Go to the entrance.
- Ask how many customers are waiting.
- Update the collaborator database.

## Notes

- This is a scaffold, so some code may fail until the TODOs are finished.
- The priority system is handled in `turtlebot4_run.py`.
- Only one behavior is set to active priority at a time.

## Build / Run

If you are using ROS 2, build and source the workspace as usual for your setup, then run the package entry point from `turtlebot4_run.py`.
