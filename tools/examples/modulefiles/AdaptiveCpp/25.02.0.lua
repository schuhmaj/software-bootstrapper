help([[
AdaptiveCpp 25.02.0 - SYCL and C++ parallel programming

This module provides access to AdaptiveCpp 25.02.0 installed
in /opt/AdaptiveCpp/25.02.0/.

Version: 25.02.0
]])

whatis("Name: AdaptiveCpp")
whatis("Version: 25.02.0")
whatis("Category: development, parallel")
whatis("Description: SYCL and C++ parallel programming")

-- Base installation directory
local adaptivecpp_root = "/work_fast/ge25zov/modules/AdaptiveCpp/25.02.0"
local adaptivecpp_bin = pathJoin(adaptivecpp_root, "bin")
local adaptivecpp_lib = pathJoin(adaptivecpp_root, "lib")
local adaptivecpp_include = pathJoin(adaptivecpp_root, "include")

prepend_path("PATH", adaptivecpp_bin)
prepend_path("LD_LIBRARY_PATH", adaptivecpp_lib)
prepend_path("LIBRARY_PATH", adaptivecpp_lib)
prepend_path("CPATH", adaptivecpp_include)

-- Set CMAKE paths for CMake integration
prepend_path("CMAKE_PREFIX_PATH", adaptivecpp_root)

-- Set environment variables
setenv("ADAPTIVECPP_ROOT", adaptivecpp_root)
setenv("ADAPTIVECPP_VERSION", "25.02.0")
