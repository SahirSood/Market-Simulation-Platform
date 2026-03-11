cmake_minimum_required(VERSION 3.20)
project(market_engine CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── engine_lib ─────────────────────────────────────────────────────────────────
# Extract OrderBook into a static library so both the main executable and the
# test binary can link against it WITHOUT pulling in main().
# INTERVIEW NOTE: This is the standard way to make production code testable in
# CMake — never compile .cpp files into multiple targets directly; use a library.
add_library(engine_lib STATIC src/OrderBook.cpp)
target_include_directories(engine_lib PUBLIC include)

# ── main executable ────────────────────────────────────────────────────────────
add_executable(market_engine src/main.cpp)
target_link_libraries(market_engine PRIVATE engine_lib)

# ── tests ──────────────────────────────────────────────────────────────────────
enable_testing()
add_subdirectory(tests)
