from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def _discovery_client_env():
    repo_root = os.environ.get('REPO_ROOT', '/root/docker-ws')
    client_xml = os.path.join(repo_root, 'configs', 'fastdds_discovery_client.xml')
    return [
        SetEnvironmentVariable('ROS_SUPER_CLIENT', 'false'),
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '0'),
        SetEnvironmentVariable('FASTRTPS_DEFAULT_PROFILES_FILE', client_xml),
    ]


def generate_launch_description():
    map_file = os.environ.get(
        'MAP_FILE', '/root/docker-ws/maps/home.yaml')
    rviz_config = os.environ.get(
        'RVIZ_CONFIG', '/root/docker-ws/configs/competition_navigation.rviz')
    loc_params = os.environ.get(
        'LOCALIZATION_PARAMS_FILE', '/root/docker-ws/configs/localization_competition.yaml')

    pkg_share = get_package_share_directory('turtlebot4_steel_city_competition')
    localization_launch = os.path.join(
        pkg_share, 'launch', 'localization_competition_bringup.launch.py')

    loc_args = {
        'map': LaunchConfiguration('map'),
        'use_sim_time': LaunchConfiguration('use_sim_time'),
    }
    if os.path.isfile(loc_params):
        loc_args['params_file'] = loc_params

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': LaunchConfiguration('use_sim_time')}],
        condition=IfCondition(LaunchConfiguration('launch_rviz')),
    )

    return LaunchDescription([
        *_discovery_client_env(),
        DeclareLaunchArgument(
            'map',
            default_value=map_file,
            description='Path to saved map YAML (AMCL map server)',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock if true',
        ),
        DeclareLaunchArgument(
            'params_file',
            default_value=loc_params if os.path.isfile(loc_params) else '',
            description='Localization params YAML (run apply_nav2_competition.py)',
        ),
        DeclareLaunchArgument(
            'launch_rviz',
            default_value='true',
            description='Start RViz with competition_navigation.rviz',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(localization_launch),
            launch_arguments=loc_args.items(),
        ),
        rviz_node,
    ])
