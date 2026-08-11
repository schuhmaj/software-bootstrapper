help([[
Google Benchmark 1.9.4 - A microbenchmark support library

This module provides access to Google Benchmark 1.9.4 installed
in /opt/google-benchmark/1.9.4/.

Version: 1.9.4
]])

whatis("Name: Google Benchmark")
whatis("Version: 1.9.4")
whatis("Category: development, performance")
whatis("Description: A microbenchmark support library")

-- Base installation directory
local benchmark_root = "/work_fast/ge25zov/modules/google-benchmark/1.9.4"
local benchmark_lib = pathJoin(benchmark_root, "lib")
local benchmark_include = pathJoin(benchmark_root, "include")

-- Set library paths
prepend_path("LD_LIBRARY_PATH", benchmark_lib)
prepend_path("LIBRARY_PATH", benchmark_lib)
prepend_path("CPATH", benchmark_include)

-- Set CMAKE paths for CMake integration
prepend_path("CMAKE_PREFIX_PATH", benchmark_root)

-- Set environment variables
setenv("GOOGLE_BENCHMARK_ROOT", benchmark_root)
setenv("GOOGLE_BENCHMARK_VERSION", "1.9.4")
