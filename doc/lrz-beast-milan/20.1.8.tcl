#%Module1.0#####################################################################

proc ModulesHelp { } {
    puts stderr {
LLVM 20.1.8 - The LLVM Compiler Infrastructure

LLVM is a collection of modular and reusable compiler and toolchain
technologies. This module provides access to LLVM 20.1.8 installed
on an x86_64 system.

This module sets up the environment to use:
- Clang C/C++ compiler
- LLVM tools and utilities
- LLVM libraries and headers

Version: 20.1.8
    }
}

module-whatis "Name: LLVM"
module-whatis "Version: 20.1.8"
module-whatis "Category: compiler, development"
module-whatis "Description: The LLVM Compiler Infrastructure"
module-whatis "URL: https://llvm.org/"

# Base installation directory
set llvm_root "/home/ge25zov2/modules_milan/modules_install/llvm/20.1.8"

set llvm_bin     "$llvm_root/bin"
set llvm_lib     "$llvm_root/lib"
set llvm_lib64   "$llvm_root/lib64"
set llvm_include "$llvm_root/include"
set llvm_share   "$llvm_root/share"

# Check if installation exists
if { ![file isdirectory $llvm_root] } {
    puts stderr "ERROR: LLVM 20.1.8 installation not found in $llvm_root"
    break
}

# Add LLVM binaries to PATH
prepend-path PATH $llvm_bin

# Set library paths
if { [file isdirectory $llvm_lib] } {
    prepend-path LD_LIBRARY_PATH $llvm_lib
    prepend-path LIBRARY_PATH $llvm_lib

    set llvm_target_lib "$llvm_lib/x86_64-unknown-linux-gnu"
    if { [file isdirectory $llvm_target_lib] } {
        prepend-path LD_LIBRARY_PATH $llvm_target_lib
        prepend-path LIBRARY_PATH $llvm_target_lib
    }
}

if { [file isdirectory $llvm_lib64] } {
    prepend-path LD_LIBRARY_PATH $llvm_lib64
    prepend-path LIBRARY_PATH $llvm_lib64
}

# Set include paths
if { [file isdirectory $llvm_include] } {
    prepend-path CPATH $llvm_include
    prepend-path C_INCLUDE_PATH $llvm_include
    prepend-path CPLUS_INCLUDE_PATH $llvm_include
}

# Set PKG_CONFIG_PATH for pkg-config support
set llvm_pkgconfig "$llvm_lib/pkgconfig"
if { [file isdirectory $llvm_pkgconfig] } {
    prepend-path PKG_CONFIG_PATH $llvm_pkgconfig
}

# Alternative lib64 pkgconfig location
set llvm_pkgconfig64 "$llvm_lib64/pkgconfig"
if { [file isdirectory $llvm_pkgconfig64] } {
    prepend-path PKG_CONFIG_PATH $llvm_pkgconfig64
}

# Set CMAKE paths for CMake integration
prepend-path CMAKE_PREFIX_PATH $llvm_root

# Set MANPATH for manual pages
set llvm_man "$llvm_share/man"
if { [file isdirectory $llvm_man] } {
    prepend-path MANPATH $llvm_man
}

# Set environment variables
setenv LLVM_ROOT $llvm_root
setenv LLVM_VERSION "20.1.8"

# Set compiler environment variables
setenv CC "$llvm_bin/clang"
setenv CXX "$llvm_bin/clang++"

# Set LLVM-specific environment variables
setenv LLVM_CONFIG "$llvm_bin/llvm-config"

# Conflict with other compiler modules
conflict gcc
conflict intel
conflict pgi
conflict llvm
