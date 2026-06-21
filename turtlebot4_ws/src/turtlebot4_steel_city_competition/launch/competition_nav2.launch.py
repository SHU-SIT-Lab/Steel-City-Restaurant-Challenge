from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import SetRemap
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
    pkg_share = get_package_share_directory('turtlebot4_steel_city_competition')
    default_params = '/root/docker-ws/configs/nav2_competition.yaml'
    nav2_params = os.environ.get('NAV2_PARAMS_FILE', default_params)
    if not os.path.isfile(nav2_params):
        nav2_params = default_params if os.path.isfile(default_params) else ''

    nav2_launch = os.path.join(pkg_share, 'launch', 'navigation_competition.launch.py')

    remappings = [
        ('/global_costmap/scan', '/scan'),
        ('/local_costmap/scan', '/scan'),
    ]

    nav2 = GroupAction([
        *[SetRemap(src, dst) for src, dst in remappings],
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(nav2_launch),
            launch_arguments={
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'params_file': nav2_params,
                'use_composition': 'False',
            }.items(),
        ),
    ])

    return LaunchDescription([
        *_discovery_client_env(),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock if true',
        ),
        DeclareLaunchArgument(
            'params_file',
            default_value=nav2_params,
            description='Nav2 params YAML (run apply_nav2_competition.py first)',
        ),
        nav2,
    ])
