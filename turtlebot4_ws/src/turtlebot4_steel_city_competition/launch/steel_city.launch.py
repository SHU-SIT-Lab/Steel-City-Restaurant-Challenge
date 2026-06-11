from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='turtlebot4_steel_city_competition',
            executable='steel_city_node.py',
            name='steel_city_node',
            output='screen'
        )
    ])
