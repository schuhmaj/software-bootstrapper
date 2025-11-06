help([[
@NAME@ @VERSION@

@DESCRIPTION@

Version: @VERSION@
]])

whatis("Name: @NAME@ ")
whatis("Version: @VERSION@")
whatis("Category: @CATEGORY@")
whatis("Description: @DESCRIPTION@")
family("compiler")

local root = "@INSTALL_DIR@"
local bin = pathJoin(root, "bin")
local lib = pathJoin(root, "lib")
local lib64 = pathJoin(root, "lib64")
local include = pathJoin(root, "include")
local share = pathJoin(root, "share")

prepend_path("PATH", bin)
prepend_path("LD_LIBRARY_PATH", lib)
prepend_path("LD_LIBRARY_PATH", lib64)
prepend_path("LIBRARY_PATH", lib)
prepend_path("LIBRARY_PATH", lib64)
prepend_path("CPATH", include)
prepend_path("CMAKE_PREFIX_PATH", root)

setenv("CC", pathJoin(llvm_bin, "clang"))
setenv("CXX", pathJoin(llvm_bin, "clang++"))

conflict("gcc")
conflict("intel")
conflict("llvm")
