#!python3
from tempfile import TemporaryDirectory
import argparse
from pathlib import Path
import urllib.request
import tarfile
import platform
import shutil
from typing import Literal

VULKAN_SDK_VERSION: str = "1.4.350.0"
SLANG_VERSION: str = "2026.9"

ARCHITECTURE: str = platform.machine()
SYSTEM: str = platform.system()
OS_VERSION: str = platform.version()


def get_download_url():

    if ARCHITECTURE == "x86_64" and SYSTEM == "Linux":
        # Official Vulkan SDK download page
        print("Downloading from official Vulkan SDK download page for x86_64 Linux")
        return f"https://sdk.lunarg.com/sdk/download/{VULKAN_SDK_VERSION}/linux/vulkansdk-linux-x86_64-{VULKAN_SDK_VERSION}.tar.xz"
    elif ARCHITECTURE == "aarch64" and SYSTEM == "Linux" and "Ubuntu" in OS_VERSION:
        # Unofficial, but public build of the VulkanSDK for aarch64 in a GitHub CI Runner for Ubuntu 22.04
        print("Downloading from unofficial GitHub CI Runner for aarch64 Ubuntu 22.04")
        return f"https://github.com/jakoch/vulkan-sdk-arm/releases/download/{VULKAN_SDK_VERSION}/vulkansdk-ubuntu-22.04-arm-{VULKAN_SDK_VERSION}.tar.xz"
    else:
        raise RuntimeError(
            "The Script at the moment only supports Linux x86_64 and Ubuntu aarch64 systems. Please built the VulkanSDK from source yourself (maybe in a Docker Image)"
        )


def install_vulkan(
    install_dir: Path, vulkan_version: str, dry_run: bool = False
) -> Path:
    install_dir = install_dir / "VulkanSDK"
    if not dry_run:
        with TemporaryDirectory() as tmp_dir:
            # Download source
            print(f"Downloading Vulkan SDK {vulkan_version}")
            source_url = get_download_url()
            archive_path = Path(tmp_dir) / "vulkan.tar.xz"
            urllib.request.urlretrieve(source_url, archive_path)

            print(f"Extracting Vulkan SDK {vulkan_version}")
            install_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive_path) as tar:
                tar.extractall(install_dir)

    return install_dir / vulkan_version / ARCHITECTURE


def install_slang(install_dir: Path, vulkan_install_dir: Path):
    with TemporaryDirectory() as tmp_dir:
        # Download source
        print(f"Downloading Slang {SLANG_VERSION} for {ARCHITECTURE}")
        source_url = f"https://github.com/shader-slang/slang/releases/download/v{SLANG_VERSION}/slang-{SLANG_VERSION}-linux-{ARCHITECTURE}.tar.gz"
        archive_path = Path(tmp_dir) / "slang.tar.gz"
        extract_dir = Path(tmp_dir) / "slang"
        urllib.request.urlretrieve(source_url, archive_path)

        print(f"Extracting Slang {SLANG_VERSION}")
        install_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path) as tar:
            tar.extractall(extract_dir)

        shutil.copytree(
            extract_dir / "bin", vulkan_install_dir / "bin", dirs_exist_ok=True
        )
        shutil.copytree(
            extract_dir / "include",
            vulkan_install_dir / "slang" / "include",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            extract_dir / "include",
            vulkan_install_dir / "slang" / "include",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            extract_dir / "lib", vulkan_install_dir / "lib", dirs_exist_ok=True
        )
        shutil.copytree(
            extract_dir / "share", vulkan_install_dir / "share", dirs_exist_ok=True
        )


def install_module_file(
    install_dir: Path,
    module_dir: Path,
    vulkan_version: str,
    language: Literal["lua", "tcl"] = "lua",
) -> None:
    template_path = Path(f"templates/vulkan-template.{language}")
    with open(template_path, "r") as f:
        template = f.read()

    module_content = template.replace("@INSTALL_DIR@", str(install_dir.absolute()))

    module_file = (
        module_dir
        / "VulkanSDK"
        / f"{vulkan_version}{'.lua' if language == 'lua' else ''}"
    )
    module_file.parent.mkdir(parents=True, exist_ok=True)
    with open(module_file, "w") as f:
        f.write(module_content)
    print(f"Created module file at {module_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("install_dir", type=Path)
    parser.add_argument("module_dir", nargs="?", type=Path, default=None)
    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default="lua",
        choices=["lua", "tcl"],
        help="Language in which to generate the module file - either lua or tcl (defaults to lua)",
    )
    parser.add_argument(
        "--vulkan-sdk-version",
        type=str,
        default=VULKAN_SDK_VERSION,
        help=f"Version of the Vulkan SDK to install. Defaults to the latest version ({VULKAN_SDK_VERSION})",
    )
    parser.add_argument(
        "--skip-vulkan-install",
        action="store_true",
        default=False,
        help="Don't install anything. Only create module files.",
    )
    args = parser.parse_args()

    vulkan_install_dir = install_vulkan(
        install_dir=args.install_dir,
        vulkan_version=args.vulkan_sdk_version,
        dry_run=args.skip_vulkan_install,
    )
    if ARCHITECTURE == "aarch64" and SYSTEM == "Linux":
        # Only required for aarch64 Linux, the official Vulkan SDK does already include Slang
        install_slang(
            install_dir=args.install_dir, vulkan_install_dir=vulkan_install_dir
        )
    if args.module_dir is not None:
        install_module_file(
            install_dir=vulkan_install_dir,
            module_dir=args.module_dir,
            vulkan_version=args.vulkan_sdk_version,
            language=args.language,
        )
