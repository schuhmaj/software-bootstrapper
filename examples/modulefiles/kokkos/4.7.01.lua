help([[
Kokkos 4.7.01 - Performance portable C++ programming model

This module provides access to Kokkos 4.7.01 installed on the system.

Version: 4.7.01
]])

whatis("Name: Kokkos")
whatis("Version: 4.7.01")
whatis("Category: development, parallel")
whatis("Description: Performance portable C++ programming model")

-- Base installation directory
local kokkos_root = "/work_fast/ge25zov/modules/kokkos/4.7.01"
local kokkos_bin = pathJoin(kokkos_root, "bin")
local kokkos_lib = pathJoin(kokkos_root, "lib")
local kokkos_include = pathJoin(kokkos_root, "include")


prepend_path("PATH", kokkos_bin)
prepend_path("LD_LIBRARY_PATH", kokkos_lib)
prepend_path("LIBRARY_PATH", kokkos_lib)
prepend_path("CPATH", kokkos_include)

-- Set CMAKE paths for CMake integration
prepend_path("CMAKE_PREFIX_PATH", kokkos_root)

-- Set environment variables
setenv("KOKKOS_ROOT", kokkos_root)
setenv("KOKKOS_VERSION", "4.7.01")
