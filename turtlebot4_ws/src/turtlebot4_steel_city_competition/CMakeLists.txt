cmake_minimum_required(VERSION 3.8)
project(turtlebot4_steel_city_competition)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/NavigateToWaypoint.srv"
)

install(PROGRAMS
  src/turtlebot4_run.py
  src/helpers/retrieve_camera.py
  src/helpers/retrieve_mic.py
  src/helpers/send_audio.py
  src/actions/obj_detection.py
  src/actions/speech_to_text.py
  src/actions/text_to_speech.py
  src/behaviors/behaviors.py
  src/behaviors/database_bridge.py
  src/behaviors/check_customer_behavior.py
  src/behaviors/check_empty_table_behavior.py
  src/behaviors/collect_order_behavior.py
  src/behaviors/introduce_table_behavior.py
  src/behaviors/mark_order_ready_behavior.py
  src/behaviors/take_order_behavior.py
  src/behaviors/update_customer_number_behavior.py
  src/publishers/mic_publisher.py
  src/subscribers/speaker_subscriber.py
  src/navigation/navigation_server.py
  DESTINATION lib/${PROJECT_NAME})

install(DIRECTORY src/navigation
  DESTINATION lib/${PROJECT_NAME}
  FILES_MATCHING PATTERN "*.py")

install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_export_dependencies(rosidl_default_runtime)
ament_package()
