cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD openspand_card)
list(APPEND PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/boards)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)
project(openspand_bringup C CXX ASM)
set(CMAKE_C_STANDARD 11)
pico_sdk_init()

add_executable(openspand_bringup main.c board.c tests.c sdcard.c dvi.c)
target_include_directories(openspand_bringup PRIVATE ${CMAKE_CURRENT_LIST_DIR}/..)
set_source_files_properties(main.c board.c tests.c sdcard.c dvi.c
  PROPERTIES COMPILE_OPTIONS "-Wall;-Wextra")
target_link_libraries(openspand_bringup
  pico_stdlib hardware_clocks hardware_dma hardware_i2c hardware_pio
  hardware_pll hardware_spi hardware_watchdog)

# GPIO0 and 1 are Z80 D0 and D1 on this card: stdio must never go to a UART.
pico_enable_stdio_uart(openspand_bringup 0)
pico_enable_stdio_usb(openspand_bringup 1)
pico_set_program_name(openspand_bringup "OpenSpand Card v0.2 bring-up")
pico_add_extra_outputs(openspand_bringup)
