help([[
Google Test 1.17.0 - Google's C++ testing and mocking framework

This module provides access to Google Test 1.17.0 installed
in /opt/googletest/1.17.0/.

Version: 1.17.0
]])

whatis("Name: Google Test")
whatis("Version: 1.17.0")
whatis("Category: development, testing")
whatis("Description: Google's C++ testing and mocking framework")

-- Base installation directory
local googletest_root = "/work_fast/ge25zov/modules/googletest/1.17.0"
local googletest_lib = pathJoin(googletest_root, "lib")
local googletest_include = pathJoin(googletest_root, "include")

prepend_path("LD_LIBRARY_PATH", googletest_lib)
prepend_path("LIBRARY_PATH", googletest_lib)
prepend_path("CPATH", googletest_include)

-- Set CMAKE paths for CMake integration
prepend_path("CMAKE_PREFIX_PATH", googletest_root)

-- Set environment variables
setenv("GOOGLETEST_ROOT", googletest_root)
setenv("GOOGLETEST_VERSION", "1.17.0")
