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
set_target_properties(engine_lib PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(engine_lib PUBLIC include)

# ── main executable ────────────────────────────────────────────────────────────
add_executable(market_engine src/main.cpp)
target_link_libraries(market_engine PRIVATE engine_lib)

# ── benchmark executable ────────────────────────────────────────────────────────
add_executable(benchmark src/benchmark.cpp)
target_link_libraries(benchmark PRIVATE engine_lib)

# ── pybind11 via FetchContent ───────────────────────────────────────────────────
include(FetchContent)
FetchContent_Declare(
  pybind11
  GIT_REPOSITORY https://github.com/pybind/pybind11
  GIT_TAG        v2.13.6
)
FetchContent_MakeAvailable(pybind11)

# ── Python extension module ─────────────────────────────────────────────────────
# pybind11_add_module compiles to a shared library (.pyd on Windows, .so on Linux)
# that Python can import directly: `import engine`
# We link against engine_lib so OrderBook.cpp is not compiled twice.
pybind11_add_module(engine bindings/engine_bindings.cpp)
target_link_libraries(engine PRIVATE engine_lib)
target_compile_features(engine PRIVATE cxx_std_17)

# ── tests ──────────────────────────────────────────────────────────────────────
enable_testing()
add_subdirectory(tests)
