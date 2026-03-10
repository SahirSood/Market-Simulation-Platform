cmake_minimum_required(VERSION 3.20)
project(market_engine CXX)

set(CMAKE_CXX_STANDARD 17)  
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(market_engine src/main.cpp)
target_include_directories(market_engine PRIVATE include)
