help([[
Slang 2025.17.1 - Performance portable C++ programming model

This module provides access to Slang 2025.17.1 installed
in /opt/slang/.

Version: 2025.17.1
]])

whatis("Name: Slang")
whatis("Version: 2025.17.1")
whatis("Category: development, parallel")
whatis("Description: Performance portable C++ programming model")

-- Base installation directory
local slang_root = "/opt/slang"
local slang_bin = pathJoin(slang_root, "bin")
local slang_lib = pathJoin(slang_root, "lib")
local slang_include = pathJoin(slang_root, "include")


prepend_path("PATH", slang_bin)
prepend_path("LD_LIBRARY_PATH", slang_lib)
prepend_path("LIBRARY_PATH", slang_lib)
prepend_path("CPATH", slang_include)

-- Set CMAKE paths for CMake integration
prepend_path("CMAKE_PREFIX_PATH", slang_root)

-- Set environment variables
setenv("SLANG_ROOT", slang_root)
setenv("SLANG_VERSION", "2025.17.1")
