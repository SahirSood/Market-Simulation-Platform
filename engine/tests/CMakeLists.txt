include(FetchContent)

# Download GoogleTest v1.14.0 at configure time if not already cached.
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
)

# On Windows, prevent GTest from overriding /MD or /MT compiler flags.
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

add_executable(test_engine test_engine.cpp)
target_link_libraries(test_engine PRIVATE GTest::gtest_main engine_lib)

# Auto-register each TEST() with ctest so `ctest` finds them without manual wiring.
include(GoogleTest)
gtest_discover_tests(test_engine)
