#!python3
from tempfile import TemporaryDirectory
import argparse
from pathlib import Path
import urllib.request
import tarfile
import platform

VULKAN_SDK_VERSION = "1.4.328.1"

def get_download_url():
    arch = platform.machine()
    system = platform.system()
    if arch != "x86_64" and system != "Linux":
        raise RuntimeError("Only Linux x86_64 is supported with this installer script!")
    return f"https://sdk.lunarg.com/sdk/download/{VULKAN_SDK_VERSION}/linux/vulkansdk-linux-x86_64-{VULKAN_SDK_VERSION}.tar.xz"


def install_vulkan(install_dir: Path, vulkan_version: str) -> Path:
    install_dir = install_dir / "VulkanSDK"
    with TemporaryDirectory() as tmp_dir:
        # Download source
        print(f"Downloading Vulkan SDK {VULKAN_SDK_VERSION}")
        source_url = get_download_url()
        archive_path = Path(tmp_dir) / "vulkan.tar.xz"
        urllib.request.urlretrieve(source_url, archive_path)

        print(f"Extracting Vulkan SDK {VULKAN_SDK_VERSION}")
        install_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path) as tar:
            tar.extractall(install_dir)

    return install_dir / VULKAN_SDK_VERSION / "x86_64"


def install_module_file(install_dir: Path, module_dir: Path, vulkan_version: str) -> None:
    template_path = Path("templates/vulkan-template.lua")
    with open(template_path, "r") as f:
        template = f.read()

    module_content = template.replace("@INSTALL_DIR@", str(install_dir.absolute()))

    module_file = module_dir / "VulkanSDK" / f"{VULKAN_SDK_VERSION}.lua"
    module_file.parent.mkdir(parents=True, exist_ok=True)
    with open(module_file, "w") as f:
        f.write(module_content)
    print(f"Created module file at {module_file}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("install_dir", type=Path)
    parser.add_argument("module_dir", nargs="?", type=Path, default=None)
    parser.add_argument("--vulkan-sdk-version", type=str, default=VULKAN_SDK_VERSION, help=f"Version of the Vulkan SDK to install. Defaults to the latest version ({VULKAN_SDK_VERSION})")
    args = parser.parse_args()

    install_dir = install_vulkan(args.install_dir, vulkan_version=args.vulkan_sdk_version)
    if args.module_dir is not None:
        install_module_file(install_dir, args.module_dir, vulkan_version=args.vulkan_sdk_version)
