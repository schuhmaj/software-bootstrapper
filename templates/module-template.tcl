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

set root "@INSTALL_DIR@"
set bin [file join $root bin]
set lib [file join $root lib]
set include [file join $root include]

prepend-path PATH $bin
prepend-path LD_LIBRARY_PATH $lib
prepend-path LIBRARY_PATH $lib
prepend-path CPATH $include
prepend-path CMAKE_PREFIX_PATH $root
