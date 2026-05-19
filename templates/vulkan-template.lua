local vulkan_sdk = "@INSTALL_DIR@"
setenv("VULKAN_SDK", vulkan_sdk)
prepend_path("PATH", vulkan_sdk .. "/bin")
prepend_path("LD_LIBRARY_PATH", vulkan_sdk .. "/lib/VulkanLoader/lib")
prepend_path("LD_LIBRARY_PATH", vulkan_sdk .. "/lib")
prepend_path("VK_ADD_LAYER_PATH", vulkan_sdk .. "/share/vulkan/explicit_layer.d")
if (os.getenv("VK_LAYER_PATH")) then
    LmodMessage("Unsetting VK_LAYER_PATH environment variable for SDK usage")
    unsetenv("VK_LAYER_PATH")
end
prepend_path("PKG_CONFIG_PATH", vulkan_sdk .. "/share/pkgconfig")
prepend_path("PKG_CONFIG_PATH", vulkan_sdk .. "/lib/pkgconfig")

prepend_path("CMAKE_PREFIX_PATH", vulkan_sdk)
prepend_path("CMAKE_PREFIX_PATH", vulkan_sdk .. "/lib/VulkanLoader")