from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock if true',
        ),
        DeclareLaunchArgument(
            'waypoints_file',
            default_value='',
            description='Optional path to waypoints YAML (defaults to repo configs/waypoints.yaml)',
        ),
        Node(
            package='turtlebot4_steel_city_competition',
            executable='navigation_server.py',
            name='navigation_server',
            output='screen',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            }],
        ),
    ])
