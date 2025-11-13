help([[
@NAME@ @VERSION@

@DESCRIPTION@

Version: @VERSION@
]])

whatis("Name: @NAME@ ")
whatis("Version: @VERSION@")
whatis("Category: @CATEGORY@")
whatis("Description: @BRIEF_DESCRIPTION@")

local root = "@INSTALL_DIR@"
local bin = pathJoin(root, "bin")
local lib = pathJoin(root, "lib")
local include = pathJoin(root, "include")

prepend_path("PATH", bin)
prepend_path("LD_LIBRARY_PATH", lib)
prepend_path("LIBRARY_PATH", lib)
prepend_path("CPATH", include)
prepend_path("CMAKE_PREFIX_PATH", root)
