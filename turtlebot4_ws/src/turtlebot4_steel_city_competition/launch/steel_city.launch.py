from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    pkg_share = get_package_share_directory('turtlebot4_steel_city_competition')
    navigation_launch = os.path.join(pkg_share, 'launch', 'navigation_server.launch.py')

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock if true',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(navigation_launch),
            launch_arguments={
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            }.items(),
        ),
        Node(
            package='turtlebot4_steel_city_competition',
            executable='turtlebot4_run.py',
            name='steel_city_node',
            output='screen',
            parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}],
        ),
    ])
