help([[
Spdlog 1.16.0 - Fast C++ logging library

This module provides access to Spdlog 1.16.0 installed on the system.

Version: 1.16.0
]])

whatis("Name: Spdlog")
whatis("Version: 1.16.0")
whatis("Category: development, logging")
whatis("Description: Fast C++ logging library")

-- Base installation directory
local spdlog_root = "/work_fast/ge25zov/modules/spdlog/1.16.0"
local spdlog_lib = pathJoin(spdlog_root, "lib")
local spdlog_include = pathJoin(spdlog_root, "include")


prepend_path("LD_LIBRARY_PATH", spdlog_lib)
prepend_path("LIBRARY_PATH", spdlog_lib)
prepend_path("CPATH", spdlog_include)

-- Set CMAKE paths for CMake integration
prepend_path("CMAKE_PREFIX_PATH", spdlog_root)

-- Set environment variables
setenv("SPDLOG_ROOT", spdlog_root)
setenv("SPDLOG_VERSION", "1.16.0")
