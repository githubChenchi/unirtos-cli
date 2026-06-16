message(STATUS "cmake config ${CMAKE_CURRENT_SOURCE_DIR}")

# This CMakeLists is designed to be imported by SDK root CMake via add_subdirectory.
# It follows the UniRTOS external app contract (same pattern as unirtos project create).

# Application target name: from environment variable or default to 'application'
if(DEFINED ENV{UNIRTOS_APP_TARGET_NAME})
    set(target $ENV{UNIRTOS_APP_TARGET_NAME})
else()
    set(target application)
endif()
message(STATUS "UniRTOS app target name: ${target}")
add_apps_libraries($<TARGET_FILE:${target}>)
add_library(${target} STATIC)
set_target_properties(${target} PROPERTIES ARCHIVE_OUTPUT_DIRECTORY ${out_unir_lib_dir})

# Allow nested user components in common conventions.
# add_subdirectory_if_exist(app_components)

# SDK global include roots are exposed through SOURCE_TOP_DIR in SDK CMake.
target_include_directories(${target} PRIVATE 
	${SOURCE_TOP_DIR}
)
target_include_directories(${target} PUBLIC 
	${CMAKE_CURRENT_SOURCE_DIR}/main/inc
	${CMAKE_CURRENT_SOURCE_DIR}/main/src
)

file(GLOB_RECURSE APP_SRC
    ${CMAKE_CURRENT_SOURCE_DIR}/main/src/*.c
)

target_sources(${target} PRIVATE ${APP_SRC})

target_link_libraries_if(CONFIG_QOSA_LINK_SYSTEM_LIBRARIES_FUNC THEN ${target} system_os)
