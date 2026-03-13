cmake_minimum_required(VERSION 3.20)
project(unirtos_app C ASM)

# ===================== Receive Parameters from build.py =====================
# Toolchain prefix (passed by build.py, fallback only)
if(NOT DEFINED UNIRTOS_TOOLCHAIN_PREFIX)
    set(UNIRTOS_TOOLCHAIN_PREFIX "$ENV{HOME}/.unirtos/toolchain/arm-gcc/v12.2/bin/arm-none-eabi-" CACHE STRING "Unirtos toolchain prefix")
endif()

# SDK root (contains SDK's CMakeLists.txt, mandatory from build.py)
if(NOT DEFINED UNIRTOS_SDK_ROOT)
    message(FATAL_ERROR "ERROR: UNIRTOS_SDK_ROOT not passed! Use build.py to compile.")
endif()

# ===================== Toolchain Configuration =====================
set(CMAKE_C_COMPILER "${UNIRTOS_TOOLCHAIN_PREFIX}gcc")
set(CMAKE_CXX_COMPILER "${UNIRTOS_TOOLCHAIN_PREFIX}g++")
set(CMAKE_ASM_COMPILER "${UNIRTOS_TOOLCHAIN_PREFIX}gcc")
set(CMAKE_OBJCOPY "${UNIRTOS_TOOLCHAIN_PREFIX}objcopy")
set(CMAKE_OBJDUMP "${UNIRTOS_TOOLCHAIN_PREFIX}objdump")

# Embedded compilation flags (consistent with SDK/lib)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -mcpu=cortex-m4 -mthumb -ffunction-sections -fdata-sections")
set(CMAKE_ASM_FLAGS "${CMAKE_ASM_FLAGS} -mcpu=cortex-m4 -mthumb")
set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -Wl,--gc-sections")

# ===================== Import SDK CMake Script =====================
# Import SDK's CMakeLists.txt (SDK will define its own target, e.g., unirtos_sdk)
add_subdirectory(${UNIRTOS_SDK_ROOT} ${CMAKE_BINARY_DIR}/sdk_build)
message(STATUS "INFO: Imported SDK CMake script from: ${UNIRTOS_SDK_ROOT}")

# ===================== Import All Library CMake Scripts (Dynamic) =====================
set(ALL_LIB_TARGETS "")  # Store library targets for linking

if(DEFINED UNIRTOS_LIBS)
    # Convert pipe-separated library list to CMake list
    string(REPLACE "|" ";" UNIRTOS_LIB_LIST ${UNIRTOS_LIBS})
    
    # Dynamically import each library's CMakeLists.txt
    foreach(LIB_NAME ${UNIRTOS_LIB_LIST})
        # Get library root path (contains lib's CMakeLists.txt)
        string(TOUPPER ${LIB_NAME} LIB_NAME_UPPER)
        set(LIB_PATH_VAR "UNIRTOS_LIB_${LIB_NAME_UPPER}")
        
        if(DEFINED ${LIB_PATH_VAR})
            set(LIB_ROOT ${${LIB_PATH_VAR}})
            
            # Import library's CMakeLists.txt (lib defines its own target, e.g., ${LIB_NAME})
            add_subdirectory(${LIB_ROOT} ${CMAKE_BINARY_DIR}/${LIB_NAME}_build)
            message(STATUS "INFO: Imported ${LIB_NAME} CMake script from: ${LIB_ROOT}")
            
            # Add library target to link list (assume lib defines target named ${LIB_NAME})
            list(APPEND ALL_LIB_TARGETS ${LIB_NAME})
        else()
            message(WARNING "WARNING: ${LIB_PATH_VAR} not defined (${LIB_NAME} path missing)")
        endif()
    endforeach()
endif()

# ===================== Application Source Configuration =====================
# App's own sources (only app-specific code, no SDK/lib sources)
file(GLOB_RECURSE APP_SRC "main/src/*.c" "main/src/*.s")
include_directories("main/include")

# ===================== Build Application Executable =====================
# Create app executable (only app sources)
add_executable(${PROJECT_NAME}.elf ${APP_SRC})

# Link against SDK and all libraries (use targets defined in their CMake scripts)
target_link_libraries(${PROJECT_NAME}.elf 
    PRIVATE 
    unirtos_sdk  # SDK's pre-defined target (must match SDK's CMake)
    ${ALL_LIB_TARGETS}  # All library targets (each lib defines target named ${LIB_NAME})
    m  # Math library (embedded requirement)
)

# ===================== Generate Output Files =====================
add_custom_command(TARGET ${PROJECT_NAME}.elf POST_BUILD
    # Generate bin/hex/dis files
    COMMAND ${CMAKE_OBJCOPY} -O binary ${PROJECT_NAME}.elf ${PROJECT_NAME}.bin
    COMMAND ${CMAKE_OBJCOPY} -O ihex ${PROJECT_NAME}.elf ${PROJECT_NAME}.hex
    COMMAND ${CMAKE_OBJDUMP} -D ${PROJECT_NAME}.elf > ${PROJECT_NAME}.dis
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMENT "Generating bin/hex/dis files..."
)

# ===================== Build Info =====================
message(STATUS "INFO: Unirtos SDK Root (CMake script): ${UNIRTOS_SDK_ROOT}")
message(STATUS "INFO: Linked Libraries: ${ALL_LIB_TARGETS}")
message(STATUS "INFO: Build Output Directory: ${CMAKE_BINARY_DIR}")
