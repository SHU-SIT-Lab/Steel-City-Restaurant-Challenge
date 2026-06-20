# Online furniture detection (OAK-D depth → Nav2 costmap)

Detect tables **and** chairs **online** from the robot's sensors — no hand-drawn
keepout masks. Tables get baked into a flat 2D map because the lidar only sees a
thin slice at scan height; this adds the OAK-D depth point cloud as a live
costmap obstacle source so the robot perceives the full furniture volume and
re-evaluates moving chairs every cycle.

## Hybrid layers (graceful degradation)

| Source | Marks | Depends on |
| --- | --- | --- |
| Static map | Walls | Saved `maps/restaurant.yaml` (unchanged) |
| 2D lidar `/scan` | Furniture **legs** at scan height | Always available |
| OAK-D depth point cloud | Table **volume/overhang** + moved **chairs** | Camera + link |

All three feed the **same** costmap. If the camera point cloud drops out (Wi-Fi,
driver), the lidar still keeps the robot off the furniture — it degrades, it
doesn't go blind. Height filtering (`min_obstacle_height`) stops the floor from
being marked.

## Files

| Path | Role |
| --- | --- |
| `configs/oakd_voxel_layer.overlay.yaml` | The overlay (lidar + OAK-D voxel/obstacle layers). Edit tuning here. |
| `scripts/nav/apply_furniture_costmap.py` | Host-side: merges the overlay into the robot's real default `nav2.yaml`. |
| `configs/nav2_furniture.yaml` | **Generated** launch-ready params (git-ignored; do not edit by hand). |

## One-time check on the Docker host

The OAK-D does **not** publish a point cloud by default — confirm the real topic:

```bash
ros2 topic list | grep -i oakd      # look for a *points* topic
ros2 topic hz /oakd/points          # is it actually publishing?
```

If there is no point cloud topic, enable it in the OAK-D/depthai config on the
robot, or run a `depth_image_proc::point_cloud_xyz` node to synthesize one from
the depth image. Without a live PointCloud2, this falls back to lidar-only.

## Apply (on the Docker host, ROS sourced, from repo root)

```bash
git pull
python3 scripts/nav/apply_furniture_costmap.py --pointcloud-topic /oakd/points
ros2 launch turtlebot4_navigation nav2.launch.py \
    params_file:=$(pwd)/configs/nav2_furniture.yaml
```

The script auto-locates TurtleBot4's installed `nav2.yaml`, deep-merges the
overlay, ensures `voxel_layer`/`obstacle_layer` are in the plugin chain, and
substitutes the topic. **Eyeball `configs/nav2_furniture.yaml` once** before the
run.

## Verify it works

1. In RViz, add the local costmap and the `voxel_layer` voxel grid.
2. Drive toward a table: voxels should appear at table-top height (not just
   legs), and the planner should route around the **whole** table footprint.
3. Move a chair into the path: it should be marked, then clear from the costmap
   after the robot re-observes the empty space.
4. Pull the point-cloud topic (`ros2 topic hz` shows nothing): the robot should
   still avoid furniture via lidar — confirming graceful degradation.

## Tuning knobs (in the overlay)

| Param | Raise to… | Lower to… |
| --- | --- | --- |
| `pcl.min_obstacle_height` | Reject more floor noise | Catch low obstacles |
| `pcl.max_obstacle_height` | See taller furniture | Ignore overhead structure |
| `pcl.obstacle_max_range` | See furniture sooner | Cut far-field depth noise |
| `voxel_layer.mark_threshold` | Need more hits to mark (less noise) | Mark on a single hit |

If chairs linger after moving, the built-in voxel layer clears on re-observation
only — for time-based decay, the upgrade path is the Spatio-Temporal Voxel Layer
(STVL), which needs adding to the Dockerfile and an image rebuild.
