cmake_minimum_required(VERSION 3.20)
project(unirtos_app)

# 设置工具链路径（需替换为实际的unirtos工具链路径）
set(TOOLCHAIN_PREFIX "$ENV{HOME}/.unirtos/toolchain/arm-gcc/v12.2/bin/arm-none-eabi-")
set(CMAKE_C_COMPILER "${TOOLCHAIN_PREFIX}gcc")
set(CMAKE_CXX_COMPILER "${TOOLCHAIN_PREFIX}g++")
set(CMAKE_ASM_COMPILER "${TOOLCHAIN_PREFIX}gcc")
set(CMAKE_OBJCOPY "${TOOLCHAIN_PREFIX}objcopy")
set(CMAKE_OBJDUMP "${TOOLCHAIN_PREFIX}objdump")

# 设置SDK路径
set(UNIRTOS_SDK_ROOT "$ENV{HOME}/.unirtos/sdk/v2.1.0")

# 包含SDK头文件
include_directories(
    ${UNIRTOS_SDK_ROOT}/kernel/include
    ${UNIRTOS_SDK_ROOT}/drivers/include
    main/include
)

# 源文件列表
file(GLOB APP_SRC "main/src/*.c")
file(GLOB SDK_SRC 
    ${UNIRTOS_SDK_ROOT}/kernel/src/*.c
    ${UNIRTOS_SDK_ROOT}/drivers/src/*.c
)

# 生成可执行文件
add_executable(${PROJECT_NAME}.elf ${APP_SRC} ${SDK_SRC})

# 链接配置
target_link_options(${PROJECT_NAME}.elf PRIVATE -T${UNIRTOS_SDK_ROOT}/linker/link.ld)
target_link_libraries(${PROJECT_NAME}.elf PRIVATE m)

# 生成bin/hex文件
add_custom_command(TARGET ${PROJECT_NAME}.elf POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O binary ${PROJECT_NAME}.elf ${PROJECT_NAME}.bin
    COMMAND ${CMAKE_OBJCOPY} -O ihex ${PROJECT_NAME}.elf ${PROJECT_NAME}.hex
)
