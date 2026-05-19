#%Module1.0#####################################################################

##
## Vulkan SDK modulefile
##

proc ModulesHelp { } {
    puts stderr {Vulkan SDK}
    puts stderr {}
    puts stderr {This module sets up the Vulkan SDK environment.}
    puts stderr {}
    puts stderr {It configures VULKAN_SDK, PATH, LD_LIBRARY_PATH, and VK_ADD_LAYER_PATH.}
}

module-whatis {Name: VulkanSDK}
module-whatis {Description: Vulkan SDK environment}

set vulkan_sdk "@INSTALL_DIR@"

setenv VULKAN_SDK $vulkan_sdk

prepend-path PATH [file join $vulkan_sdk bin]
prepend-path LD_LIBRARY_PATH [file join $vulkan_sdk lib]
prepend-path VK_ADD_LAYER_PATH [file join $vulkan_sdk share vulkan explicit_layer.d]

if { [info exists env(VK_LAYER_PATH)] } {
    puts stderr {Unsetting VK_LAYER_PATH environment variable for SDK usage}
    unsetenv VK_LAYER_PATH
}
