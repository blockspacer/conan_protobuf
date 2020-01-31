import os
from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration
from conans.tools import Version

# see https://github.com/conan-io/conan-center-index/blob/master/recipes/protobuf/3.9.x/conanfile.py
class ProtobufConan(ConanFile):
    name = "protobuf"
    version = "v3.9.1"
    description = "Protocol Buffers - Google's data interchange format"
    topics = ("conan", "protobuf", "protocol-buffers", "protocol-compiler", "serialization", "rpc", "protocol-compiler")
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/protocolbuffers/protobuf"
    repo_url = 'https://github.com/protocolbuffers/protobuf.git'
    license = "BSD-3-Clause"
    exports_sources = ["CMakeLists.txt", "protobuf.patch"]
    generators = "cmake", "cmake_paths", "virtualenv"
    short_paths = True
    settings = "os_build", "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "with_zlib": [True, False], "fPIC": [True, False], "lite": [True, False]}
    default_options = {"with_zlib": False, "shared": False, "fPIC": True, "lite": False}

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _build_subfolder(self):
        return "build_subfolder"

    @property
    def _is_clang_x86(self):
        return self.settings.compiler == "clang" and self.settings.arch == "x86"

    def cmake_flags(self):

        # Generate the CMake flags to ensure the UE4-bundled version of zlib is used
        #from ue4util import Utility
        #zlib = self.deps_cpp_info["zlib"]
        return [
            "-DBUILD_SHARED_LIBS=OFF",
            #"-Dprotobuf_BUILD_TESTS=OFF",
            #"-Dprotobuf_MSVC_STATIC_RUNTIME=OFF",
            #"-DZLIB_INCLUDE_DIR=" + zlib.include_paths[0],
            #"-DZLIB_LIBRARY=" + Utility.resolve_file(zlib.lib_paths[0], zlib.libs[0])
        ]

    def source(self):
        #tools.get(**self.conan_data["sources"][self.version])
        #extracted_folder = self.name + "-" + self.version
        #os.rename(extracted_folder, self._source_subfolder)
        self.run('git clone --progress --depth 1 --branch {} --recursive --recurse-submodules {} {}'.format(self.version, self.repo_url, self._source_subfolder))

        # Prevent libprotobuf-lite from being included in our built package
        tools.replace_in_file(
            self._source_subfolder + "/cmake/install.cmake",
            "set(_protobuf_libraries libprotobuf-lite libprotobuf)",
            "set(_protobuf_libraries libprotobuf)"
        )

    def configure(self):
        if self.settings.os == "Windows" and self.settings.compiler == "Visual Studio":
            del self.options.fPIC
            compiler_version = Version(self.settings.compiler.version.value)
            if compiler_version < "14":
                raise ConanInvalidConfiguration("On Windows Protobuf can only be built with "
                                           "Visual Studio 2015 or higher.")

    def requirements(self):
        if self.options.with_zlib:
            self.requires("zlib/1.2.11")

    def _configure_cmake(self):
        cmake = CMake(self)
        cmake.definitions["protobuf_BUILD_TESTS"] = False
        cmake.definitions["protobuf_WITH_ZLIB"] = self.options.with_zlib
        cmake.definitions["protobuf_BUILD_PROTOC_BINARIES"] = not self.options.lite
        cmake.definitions["protobuf_BUILD_PROTOBUF_LITE"] = self.options.lite
        if self.settings.compiler == "Visual Studio":
            cmake.definitions["protobuf_MSVC_STATIC_RUNTIME"] = "MT" in self.settings.compiler.runtime
        cmake.configure(source_folder=self._source_subfolder + "/cmake", build_folder=self._build_subfolder, args=self.cmake_flags())
        return cmake

    def build(self):
        #tools.patch(base_path=self._source_subfolder, patch_file="protobuf.patch")
        cmake = self._configure_cmake()
        cmake.build()

    def package(self):
        self.copy("LICENSE", dst="licenses", src=self._source_subfolder)
        #self.copy("BUILD", dst="licenses", src=self._source_subfolder)
        self.copy("*", dst="cmake", src=os.path.join(self._source_subfolder, "cmake"))
        cmake = self._configure_cmake()
        cmake.install()

        #self.copy("*.h", dst="include", src=os.path.join(self._source_subfolder, "include"))
        #self.copy("*.proto", dst="include", src=os.path.join(self._source_subfolder, "include"))
        #self.copy("protobuf-config.cmake", os.path.join(self._source_subfolder, "cmake"), ".")

        #self.copy("*.h", dst="include", src=os.path.join(self.package_folder, "include"))
        #self.copy("*.proto", dst="include", src=os.path.join(self.package_folder, "include"))
        #self.copy("protobuf-config.cmake", os.path.join(self.package_folder, "cmake"), ".")

        #lib/cmake/protobuf/
        #self.copy("*", os.path.join(self.package_folder), "cmake")
        #self.copy("*protobuf*.cmake", os.path.join(self.package_folder, "cmake"), ".")

        #tools.rmdir(os.path.join(self.package_folder, "lib", "cmake"))
        #tools.rmdir(os.path.join(self.package_folder, "cmake"))
        tools.rmdir(os.path.join(self.package_folder, "lib", "pkgconfig"))

    def package_id(self):
        del self.info.settings.compiler
        del self.info.settings.arch
        self.info.include_build_settings()

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
        self.cpp_info.libs.sort(reverse=True)

        bindir = os.path.join(self.package_folder, "bin")
        self.output.info("Appending PATH environment variable: {}".format(bindir))
        self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))

        protoc = "protoc.exe" if self.settings.os_build == "Windows" else "protoc"
        self.env_info.PROTOC_BIN = os.path.normpath(os.path.join(self.package_folder, "bin", protoc))

        #js_embed = "js_embed.exe" if self.settings.os_build == "Windows" else "js_embed"
        #self.env_info.JS_EMBED_BIN = os.path.normpath(os.path.join(self.package_folder, "bin", js_embed))

        if self.settings.os == "Linux":
            self.cpp_info.libs.append("pthread")
            if self._is_clang_x86 or "arm" in str(self.settings.arch):
                self.cpp_info.libs.append("atomic")

        if self.settings.os == "Windows":
            if self.options.shared:
                self.cpp_info.defines = ["PROTOBUF_USE_DLLS"]
        self.cpp_info.names["cmake_find_package"] = "Protobuf"
        self.cpp_info.names["cmake_find_package_multi"] = "Protobuf"

    # see `conan install . -g deploy` in https://docs.conan.io/en/latest/devtools/running_packages.html
    def deploy(self):
        # self.copy("*", dst="/usr/local/bin", src="bin", keep_path=False)
        self.copy("*", dst="bin", src="bin", keep_path=False)
