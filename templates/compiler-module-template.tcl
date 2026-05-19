#%Module1.0#####################################################################

proc ModulesHelp { } {
    puts stderr {@NAME@ @VERSION@}
    puts stderr {}
    puts stderr {@DESCRIPTION@}
    puts stderr {}
    puts stderr {Version: @VERSION@}
}

module-whatis {Name: @NAME@}
module-whatis {Version: @VERSION@}
module-whatis {Category: @CATEGORY@}
module-whatis {Description: @BRIEF_DESCRIPTION@}

family compiler

set root "@INSTALL_DIR@"
set bin [file join $root bin]
set lib [file join $root lib]
set lib64 [file join $root lib64]
set include [file join $root include]
set share [file join $root share]

prepend-path PATH $bin
prepend-path LD_LIBRARY_PATH $lib
prepend-path LD_LIBRARY_PATH $lib64
prepend-path LIBRARY_PATH $lib
prepend-path LIBRARY_PATH $lib64
prepend-path CPATH $include
prepend-path CMAKE_PREFIX_PATH $root

setenv CC [file join $bin clang]
setenv CXX [file join $bin clang++]

conflict gcc
conflict intel
conflict llvm
