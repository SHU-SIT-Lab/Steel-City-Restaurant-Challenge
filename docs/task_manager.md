# Task manager

There is no separate task manager module. **`ReactiveCoordinator` in
`turtlebot4_run.py` is the task manager.**

It selects the highest-priority deliberative behavior every 100ms and runs one
behavior at a time. Navigation legs are executed via `navigation_handoff.drive_navigation`
after each behavior step.

See [docs/interfaces.md](interfaces.md) and [scripts/trial/README.md](../scripts/trial/README.md).
