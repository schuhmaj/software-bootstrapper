-- Copyright (c) 2015-2023 LunarG, Inc.
--
-- Source this file into an existing shell to setup your environment.
-- See docs for in depth documentation:
-- https://vulkan.lunarg.com/doc/sdk/latest/linux/getting_started.html


local vulkan_sdk = "@INSTALL_DIR@"
setenv("VULKAN_SDK", vulkan_sdk)
prepend_path("PATH", vulkan_sdk .. "/bin")
prepend_path("LD_LIBRARY_PATH", vulkan_sdk .. "/lib")
prepend_path("VK_ADD_LAYER_PATH", vulkan_sdk .. "/share/vulkan/explicit_layer.d")
if (os.getenv("VK_LAYER_PATH")) then
    LmodMessage("Unsetting VK_LAYER_PATH environment variable for SDK usage")
    unsetenv("VK_LAYER_PATH")
end
