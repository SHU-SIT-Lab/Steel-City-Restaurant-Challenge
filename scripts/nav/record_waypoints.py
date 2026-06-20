#!/usr/bin/env python3
"""Graphical waypoint helper: camera, POI management, teleop, and navigation."""

from __future__ import annotations

import argparse
import math
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple

import cv2
import rclpy
import tkinter as tk
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseWithCovarianceStamped, TwistStamped
from PIL import Image, ImageTk
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image as RosImage
from tkinter import filedialog, messagebox, simpledialog, ttk
from turtlebot4_steel_city_competition.srv import NavigateToWaypoint

from waypoint_store import default_waypoints_path, load_waypoints, save_waypoints

CAMERA_TOPIC = "/oakd/rgb/preview/image_raw"
AMCL_POSE_TOPIC = "/amcl_pose"
SLAM_POSE_TOPIC = "/pose"
AMCL_POSE_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)
CMD_VEL_TOPIC = "/cmd_vel"
NAV_SERVICE = "/navigation/navigate_to_waypoint"


@dataclass
class RobotPose:
    x: float
    y: float
    yaw: float


def quaternion_to_yaw(qx: float, qy: float, qz: float, qw: float) -> float:
    return math.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))


class HelperRosBridge(Node):
    """ROS I/O for the waypoint GUI: pose, camera, teleop, navigation service."""

    def __init__(self) -> None:
        super().__init__("waypoint_recorder_bridge")
        self._bridge = CvBridge()
        self._camera_enabled = False
        self._latest_frame = None
        self._latest_pose: Optional[RobotPose] = None
        self._pose_received = False
        self._pose_source: Optional[str] = None
        self._nav_client = self.create_client(NavigateToWaypoint, NAV_SERVICE)
        self._cmd_vel_pub = self.create_publisher(TwistStamped, CMD_VEL_TOPIC, 10)
        self._camera_sub = None
        self.create_subscription(
            PoseWithCovarianceStamped,
            AMCL_POSE_TOPIC,
            self._amcl_pose_callback,
            AMCL_POSE_QOS,
        )
        self.create_subscription(
            PoseWithCovarianceStamped,
            SLAM_POSE_TOPIC,
            self._slam_pose_callback,
            10,
        )

    def _update_pose(self, msg: PoseWithCovarianceStamped, source: str) -> None:
        orientation = msg.pose.pose.orientation
        self._latest_pose = RobotPose(
            x=msg.pose.pose.position.x,
            y=msg.pose.pose.position.y,
            yaw=quaternion_to_yaw(
                orientation.x,
                orientation.y,
                orientation.z,
                orientation.w,
            ),
        )
        self._pose_received = True
        self._pose_source = source

    def _amcl_pose_callback(self, msg: PoseWithCovarianceStamped) -> None:
        self._update_pose(msg, "AMCL (/amcl_pose)")

    def _slam_pose_callback(self, msg: PoseWithCovarianceStamped) -> None:
        self._update_pose(msg, "SLAM (/pose)")

    def _camera_callback(self, msg: RosImage) -> None:
        if not self._camera_enabled:
            return
        try:
            self._latest_frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:
            self.get_logger().warn(f"Camera conversion failed: {exc}")

    def set_camera_enabled(self, enabled: bool) -> None:
        self._camera_enabled = enabled
        if enabled and self._camera_sub is None:
            self._camera_sub = self.create_subscription(
                RosImage,
                CAMERA_TOPIC,
                self._camera_callback,
                10,
            )
        if not enabled:
            self._latest_frame = None

    def get_latest_frame(self):
        return self._latest_frame

    def get_current_pose(self) -> Optional[RobotPose]:
        return self._latest_pose

    def has_pose(self) -> bool:
        return self._pose_received and self._latest_pose is not None

    def get_pose_source(self) -> Optional[str]:
        return self._pose_source

    def navigation_service_available(self) -> bool:
        return self._nav_client.service_is_ready()

    def wait_for_navigation_service(self, timeout_sec: float = 2.0) -> bool:
        return self._nav_client.wait_for_service(timeout_sec=timeout_sec)

    def navigate_to(self, destination: str) -> Tuple[bool, str]:
        if not self.wait_for_navigation_service(timeout_sec=5.0):
            return False, "Navigation service unavailable."

        request = NavigateToWaypoint.Request()
        request.destination = destination
        future = self._nav_client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        if not future.done() or future.result() is None:
            return False, "Navigation service call failed."

        response = future.result()
        return response.success, response.message

    def publish_cmd_vel(self, linear_x: float, angular_z: float) -> None:
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.twist.linear.x = linear_x
        msg.twist.angular.z = angular_z
        self._cmd_vel_pub.publish(msg)

    def stop(self) -> None:
        self.publish_cmd_vel(0.0, 0.0)


def start_ros_spin(
    node: HelperRosBridge,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> threading.Thread:
    def _spin() -> None:
        try:
            rclpy.spin(node)
        except Exception as exc:
            if on_error:
                on_error(exc)

    thread = threading.Thread(target=_spin, daemon=True)
    thread.start()
    return thread


class WaypointRecorderApp:
    def __init__(self, root: tk.Tk, waypoints_path: Path) -> None:
        self.root = root
        self.root.title("Steel City Waypoint Recorder")
        self.waypoints_path = waypoints_path
        self.waypoints = load_waypoints(waypoints_path)
        self.images_dir = Path.cwd() / "robot-images"
        self.linear_speed = 0.2
        self.angular_speed = 0.8
        self._pressed_keys: set[str] = set()
        self._camera_photo = None

        rclpy.init()
        self.ros = HelperRosBridge()
        start_ros_spin(self.ros)

        self._build_ui()
        self._refresh_waypoint_list()
        self._bind_keys()
        self._ensure_keyboard_focus()
        self.root.after(100, self._update_loop)

    def _ensure_keyboard_focus(self) -> None:
        self.root.focus_force()
        self.root.lift()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=2)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        camera_frame = ttk.LabelFrame(left, text="Robot camera", padding=6)
        camera_frame.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self.camera_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            camera_frame,
            text="Enable camera",
            variable=self.camera_enabled,
            command=self._toggle_camera,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(camera_frame, text="Capture image", command=self._capture_image).grid(
            row=0, column=1, sticky="e", padx=(8, 0)
        )
        camera_frame.columnconfigure(0, weight=1)

        self.camera_label = ttk.Label(camera_frame, text="Waiting for camera...", anchor="center")
        self.camera_label.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        camera_frame.rowconfigure(1, weight=1)

        poi_frame = ttk.LabelFrame(right, text="Points of interest", padding=6)
        poi_frame.grid(row=0, column=0, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        path_row = ttk.Frame(poi_frame)
        path_row.grid(row=0, column=0, sticky="ew")
        poi_frame.columnconfigure(0, weight=1)
        ttk.Label(path_row, text="Waypoints file:").grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar(value=str(self.waypoints_path))
        self.path_entry = ttk.Entry(path_row, textvariable=self.path_var)
        self.path_entry.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        ttk.Button(path_row, text="Browse", command=self._browse_waypoints).grid(row=1, column=1, padx=(4, 0))
        path_row.columnconfigure(0, weight=1)

        self.poi_list = tk.Listbox(poi_frame, height=10, exportselection=False)
        self.poi_list.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.poi_list.bind("<<ListboxSelect>>", self._on_poi_select)
        poi_frame.rowconfigure(1, weight=1)

        self.pose_var = tk.StringVar(value="Select a point of interest")
        ttk.Label(poi_frame, textvariable=self.pose_var).grid(row=2, column=0, sticky="w", pady=(6, 0))

        btn_row = ttk.Frame(poi_frame)
        btn_row.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(btn_row, text="Save current pose", command=self._save_current_pose).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(btn_row, text="Add", command=self._add_poi).grid(row=0, column=1, padx=(0, 4))
        ttk.Button(btn_row, text="Delete", command=self._delete_poi).grid(row=0, column=2, padx=(0, 4))
        ttk.Button(btn_row, text="Reload", command=self._reload_waypoints).grid(row=0, column=3)

        nav_frame = ttk.LabelFrame(right, text="Navigate", padding=6)
        nav_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.nav_var = tk.StringVar()
        self.nav_combo = ttk.Combobox(nav_frame, textvariable=self.nav_var, state="readonly")
        self.nav_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(nav_frame, text="Go", command=self._navigate_selected).grid(row=0, column=1, padx=(4, 0))
        nav_frame.columnconfigure(0, weight=1)
        self.nav_status = tk.StringVar(value="Navigation idle")
        ttk.Label(nav_frame, textvariable=self.nav_status).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        teleop_frame = ttk.LabelFrame(right, text="Manual teleop", padding=6)
        teleop_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.teleop_frame = teleop_frame
        self.speed_var = tk.StringVar(value=self._speed_label())
        ttk.Label(teleop_frame, textvariable=self.speed_var).grid(row=0, column=0, sticky="w")
        self.focus_banner = ttk.Label(
            teleop_frame,
            text="Click here for keyboard focus",
            cursor="hand2",
            relief="ridge",
            padding=4,
        )
        self.focus_banner.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        help_text = (
            "Arrow keys: drive\n"
            "Page Up / Page Down: speed\n"
            "Space: stop"
        )
        ttk.Label(teleop_frame, text=help_text, justify="left").grid(row=2, column=0, sticky="w", pady=(6, 0))

        status_frame = ttk.LabelFrame(right, text="Status", padding=6)
        status_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.status_var = tk.StringVar(value="Starting...")
        ttk.Label(status_frame, textvariable=self.status_var, justify="left").grid(row=0, column=0, sticky="w")

        self.ros.set_camera_enabled(self.camera_enabled.get())

    def _speed_label(self) -> str:
        return f"Speed: linear={self.linear_speed:.2f} m/s, angular={self.angular_speed:.2f} rad/s"

    def _bind_keys(self) -> None:
        sequences = (
            "<KeyPress-Up>", "<KeyPress-Down>", "<KeyPress-Left>", "<KeyPress-Right>",
            "<KeyRelease-Up>", "<KeyRelease-Down>", "<KeyRelease-Left>", "<KeyRelease-Right>",
            "<KeyPress-Prior>", "<KeyPress-Next>", "<KeyPress-space>",
        )
        for sequence in sequences:
            self.root.bind_all(sequence, self._on_key)
        self.focus_banner.bind("<Button-1>", lambda _e: self._ensure_keyboard_focus())
        self.root.bind("<Map>", lambda _e: self._ensure_keyboard_focus())

    def _is_typing_in_entry(self, event: tk.Event) -> bool:
        widget = event.widget
        return widget is self.path_entry or widget.winfo_class() in {"Entry", "TEntry"}

    def _on_key(self, event: tk.Event) -> Optional[str]:
        if self._is_typing_in_entry(event):
            return None

        key = event.keysym
        if event.type == tk.EventType.KeyPress:
            if key in {"Up", "Down", "Left", "Right"}:
                self._pressed_keys.add(key)
            elif key in {"Prior", "Next"}:
                self._adjust_speed(increase=key == "Prior")
            elif key == "space":
                self._pressed_keys.clear()
                self.ros.stop()
        elif event.type == tk.EventType.KeyRelease and key in self._pressed_keys:
            self._pressed_keys.discard(key)
            if not self._pressed_keys:
                self.ros.stop()
        return "break"

    def _adjust_speed(self, increase: bool) -> None:
        step_linear = 0.05
        step_angular = 0.1
        if increase:
            self.linear_speed = min(0.6, self.linear_speed + step_linear)
            self.angular_speed = min(2.0, self.angular_speed + step_angular)
        else:
            self.linear_speed = max(0.05, self.linear_speed - step_linear)
            self.angular_speed = max(0.2, self.angular_speed - step_angular)
        self.speed_var.set(self._speed_label())

    def _apply_teleop(self) -> None:
        linear = 0.0
        angular = 0.0
        if "Up" in self._pressed_keys:
            linear += self.linear_speed
        if "Down" in self._pressed_keys:
            linear -= self.linear_speed
        if "Left" in self._pressed_keys:
            angular += self.angular_speed
        if "Right" in self._pressed_keys:
            angular -= self.angular_speed
        if linear or angular:
            self.ros.publish_cmd_vel(linear, angular)
        elif not self._pressed_keys:
            self.ros.stop()

    def _toggle_camera(self) -> None:
        self.ros.set_camera_enabled(self.camera_enabled.get())

    def _capture_image(self) -> None:
        frame = self.ros.get_latest_frame()
        if frame is None:
            messagebox.showwarning("Capture", "No camera frame available.")
            return
        self.images_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = self.images_dir / f"capture_{timestamp}.png"
        cv2.imwrite(str(output), frame)
        messagebox.showinfo("Capture", f"Saved image to {output}")

    def _browse_waypoints(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select waypoints YAML",
            filetypes=[("YAML files", "*.yaml"), ("All files", "*.*")],
            initialdir=str(self.waypoints_path.parent),
        )
        if selected:
            self.waypoints_path = Path(selected)
            self.path_var.set(str(self.waypoints_path))
            self._reload_waypoints()

    def _refresh_waypoint_list(self) -> None:
        self.poi_list.delete(0, tk.END)
        for name in sorted(self.waypoints):
            self.poi_list.insert(tk.END, name)
        self.nav_combo["values"] = sorted(self.waypoints.keys())
        if self.waypoints and not self.nav_var.get():
            first = sorted(self.waypoints.keys())[0]
            self.nav_var.set(first)

    def _on_poi_select(self, _event=None) -> None:
        selection = self.poi_list.curselection()
        if not selection:
            return
        name = self.poi_list.get(selection[0])
        entry = self.waypoints.get(name, {})
        self.pose_var.set(
            f"{name}: x={entry.get('x', 0.0):.3f}, "
            f"y={entry.get('y', 0.0):.3f}, yaw={entry.get('yaw', 0.0):.3f}"
        )
        self.nav_var.set(name)

    def _save_current_pose(self) -> None:
        selection = self.poi_list.curselection()
        if not selection:
            messagebox.showwarning("Save pose", "Select a point of interest first.")
            return
        pose = self.ros.get_current_pose()
        if pose is None:
            messagebox.showerror("Save pose", "No pose available. Is localization running?")
            return
        name = self.poi_list.get(selection[0])
        self.waypoints[name] = {"x": pose.x, "y": pose.y, "yaw": pose.yaw}
        save_waypoints(self.waypoints_path, self.waypoints)
        self._refresh_waypoint_list()
        self.pose_var.set(
            f"{name}: x={pose.x:.3f}, y={pose.y:.3f}, yaw={pose.yaw:.3f}"
        )
        messagebox.showinfo("Save pose", f"Updated {name!r} in {self.waypoints_path}")

    def _add_poi(self) -> None:
        name = simpledialog.askstring("Add point", "Point of interest name:")
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if name in self.waypoints:
            messagebox.showerror("Add point", f"{name!r} already exists.")
            return
        pose = self.ros.get_current_pose()
        if pose is None:
            messagebox.showerror("Add point", "No pose available. Is localization running?")
            return
        self.waypoints[name] = {"x": pose.x, "y": pose.y, "yaw": pose.yaw}
        save_waypoints(self.waypoints_path, self.waypoints)
        self._refresh_waypoint_list()
        messagebox.showinfo("Add point", f"Added {name!r}.")

    def _delete_poi(self) -> None:
        selection = self.poi_list.curselection()
        if not selection:
            messagebox.showwarning("Delete point", "Select a point of interest first.")
            return
        name = self.poi_list.get(selection[0])
        if not messagebox.askyesno("Delete point", f"Delete {name!r}?"):
            return
        del self.waypoints[name]
        save_waypoints(self.waypoints_path, self.waypoints)
        self._refresh_waypoint_list()
        self.pose_var.set("Select a point of interest")

    def _reload_waypoints(self) -> None:
        self.waypoints_path = Path(self.path_var.get())
        self.waypoints = load_waypoints(self.waypoints_path)
        self._refresh_waypoint_list()

    def _navigate_selected(self) -> None:
        destination = self.nav_var.get().strip()
        if not destination:
            messagebox.showwarning("Navigate", "Select a destination.")
            return
        self.nav_status.set(f"Navigating to {destination!r}...")
        self.root.update_idletasks()
        success, message = self.ros.navigate_to(destination)
        self.nav_status.set(message)
        if not success:
            messagebox.showerror("Navigate", message)

    def _update_status(self) -> None:
        pose_ok = self.ros.has_pose()
        nav_ok = self.ros.navigation_service_available()
        pose = self.ros.get_current_pose()
        pose_source = self.ros.get_pose_source() or "missing"
        pose_text = "unknown"
        if pose is not None:
            pose_text = f"x={pose.x:.2f}, y={pose.y:.2f}, yaw={pose.yaw:.2f}"

        teleop_text = "idle"
        if self._pressed_keys:
            teleop_text = "publishing TwistStamped"

        camera_text = "on" if self.camera_enabled.get() and self.ros.get_latest_frame() is not None else "waiting"

        lines = [
            f"Pose: {'OK' if pose_ok else 'missing'} [{pose_source}] ({pose_text})",
            f"Navigation service: {'ready' if nav_ok else 'waiting'}",
            f"Teleop: {teleop_text}",
            f"Camera: {camera_text}",
        ]
        if not pose_ok:
            lines.append("Hint: start localization on saved map (competition) or SLAM (mapping)")
        if not nav_ok:
            lines.append("Hint: launch navigation_server after Nav2 is up")
        self.status_var.set("\n".join(lines))

    def _update_camera(self) -> None:
        if not self.camera_enabled.get():
            return
        frame = self.ros.get_latest_frame()
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        image = image.resize((640, 360))
        self._camera_photo = ImageTk.PhotoImage(image=image)
        self.camera_label.configure(image=self._camera_photo, text="")

    def _update_loop(self) -> None:
        self._apply_teleop()
        self._update_status()
        self._update_camera()
        self.root.after(100, self._update_loop)

    def shutdown(self) -> None:
        self.ros.stop()
        self.ros.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Record restaurant waypoints with a GUI.")
    parser.add_argument(
        "--waypoints",
        type=Path,
        default=default_waypoints_path(),
        help="Path to waypoints YAML file",
    )
    args = parser.parse_args()

    root = tk.Tk()
    root.geometry("1100x700")
    app = WaypointRecorderApp(root, args.waypoints)

    def _on_close() -> None:
        app.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
