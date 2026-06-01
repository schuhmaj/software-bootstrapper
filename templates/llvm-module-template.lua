help([[
LLVM @VERSION@ - The LLVM Compiler Infrastructure

LLVM is a collection of modular and reusable compiler and toolchain
technologies. This module provides access to LLVM @VERSION@ installed
in @INSTALL_DIR@.

This module sets up the environment to use:
- Clang C/C++ compiler
- LLVM tools and utilities
- LLVM libraries and headers

Version: @VERSION@
]])

whatis("Name: LLVM")
whatis("Version: @VERSION@")
whatis("Category: compiler, development")
whatis("Description: The LLVM Compiler Infrastructure")
whatis("URL: https://llvm.org/")

-- Base installation directory
local llvm_root = "@INSTALL_DIR@"
local llvm_bin = pathJoin(llvm_root, "bin")
local llvm_lib = pathJoin(llvm_root, "lib")
local llvm_lib64 = pathJoin(llvm_root, "lib64")
local llvm_include = pathJoin(llvm_root, "include")
local llvm_share = pathJoin(llvm_root, "share")

-- Architecture-specific runtime library directory (e.g. compiler-rt, libomp)
local llvm_target_lib = pathJoin(llvm_lib, "@TARGET_TRIPLE@")

-- Check if installation exists
if not (isDir(llvm_root)) then
    LmodError("LLVM @VERSION@ installation not found in " .. llvm_root)
end

-- Set version for potential conflicts
family("compiler")

-- Add LLVM binaries to PATH
prepend_path("PATH", llvm_bin)

-- Set library paths
if (isDir(llvm_lib)) then
    prepend_path("LD_LIBRARY_PATH", llvm_lib)
    prepend_path("LIBRARY_PATH", llvm_lib)
    if (isDir(llvm_target_lib)) then
        prepend_path("LD_LIBRARY_PATH", llvm_target_lib)
        prepend_path("LIBRARY_PATH", llvm_target_lib)
    end
end

if (isDir(llvm_lib64)) then
    prepend_path("LD_LIBRARY_PATH", llvm_lib64)
    prepend_path("LIBRARY_PATH", llvm_lib64)
end

-- Set include paths
if (isDir(llvm_include)) then
    prepend_path("CPATH", llvm_include)
    prepend_path("C_INCLUDE_PATH", llvm_include)
    prepend_path("CPLUS_INCLUDE_PATH", llvm_include)
end

-- Set PKG_CONFIG_PATH for pkg-config support
local llvm_pkgconfig = pathJoin(llvm_lib, "pkgconfig")
if (isDir(llvm_pkgconfig)) then
    prepend_path("PKG_CONFIG_PATH", llvm_pkgconfig)
end

-- Alternative lib64 pkgconfig location
local llvm_pkgconfig64 = pathJoin(llvm_lib64, "pkgconfig")
if (isDir(llvm_pkgconfig64)) then
    prepend_path("PKG_CONFIG_PATH", llvm_pkgconfig64)
end

-- Set CMAKE paths for CMake integration
prepend_path("CMAKE_PREFIX_PATH", llvm_root)

-- Set MANPATH for manual pages
local llvm_man = pathJoin(llvm_share, "man")
if (isDir(llvm_man)) then
    prepend_path("MANPATH", llvm_man)
end

-- Set environment variables
setenv("LLVM_ROOT", llvm_root)
setenv("LLVM_VERSION", "@VERSION@")

-- Set compiler environment variables
setenv("CC", pathJoin(llvm_bin, "clang"))
setenv("CXX", pathJoin(llvm_bin, "clang++"))

-- Set LLVM-specific environment variables
setenv("LLVM_CONFIG", pathJoin(llvm_bin, "llvm-config"))

-- Conflict with other compiler modules
conflict("gcc")
conflict("intel")
conflict("pgi")
conflict("llvm")
