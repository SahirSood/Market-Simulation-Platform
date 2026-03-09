cmake_minimum_required(VERSION 3.20)
project(market_engine CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Engine library
add_library(engine STATIC)
target_include_directories(engine PUBLIC include)

# Tests
enable_testing()
add_subdirectory(tests)
