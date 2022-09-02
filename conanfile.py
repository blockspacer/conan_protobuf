import os, shutil, glob
from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration
from conans.tools import Version
from conan.tools.files import rename
from conan.tools.microsoft import msvc_runtime_flag
from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration
import functools
import os
import textwrap

required_conan_version = ">=1.43.0"

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
    exports_sources = ["CMakeLists.txt", "protobuf.patch", "patches/*"]
    generators = "cmake", "cmake_paths", "virtualenv"
    short_paths = True
    settings = "os_build", "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_zlib": [True, False],
        "with_rtti": [True, False],
        "lite": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_zlib": False, # TODO: use our custom zlib version
        "with_rtti": True,
        "lite": False,
    }

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _build_subfolder(self):
        return "build_subfolder"

    @property
    def _is_msvc(self):
        return str(self.settings.compiler) in ["Visual Studio", "msvc"]

    @property
    def _is_clang_cl(self):
        return self.settings.compiler == 'clang' and self.settings.os == 'Windows'

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
        if self.options.shared:
            del self.options.fPIC
            
        if self.settings.compiler == "clang":
            if tools.Version(self.version) >= "3.15.4" and tools.Version(self.settings.compiler.version) < "4":
                raise ConanInvalidConfiguration("protobuf {} doesn't support clang < 4".format(self.version))

        if self.settings.os == "Windows" and self.settings.compiler == "Visual Studio":
            compiler_version = Version(self.settings.compiler.version.value)
            if compiler_version < "14":
                raise ConanInvalidConfiguration("On Windows Protobuf can only be built with "
                                           "Visual Studio 2015 or higher.")

        if self.settings.os == "Windows" and self.settings.compiler in ["Visual Studio", "clang"] and "MT" in self.settings.compiler.runtime:
            if self.options.shared:
                raise ConanInvalidConfiguration("Protobuf can't be built with shared + MT(d) runtimes")

        if self.options.shared and str(self.settings.compiler.get_safe("runtime")) in ["MT", "MTd", "static"]:
            raise ConanInvalidConfiguration("Protobuf can't be built with shared + MT(d) runtimes")

        if tools.is_apple_os(self.settings.os):
            raise ConanInvalidConfiguration("Protobuf could not be built as shared library for Mac.")

        if self.settings.compiler == "Visual Studio":
            if Version(self.settings.compiler.version) < "14":
                raise ConanInvalidConfiguration("On Windows Protobuf can only be built with "
                                                "Visual Studio 2015 or higher.")
    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
        if not self._can_disable_rtti:
            del self.options.with_rtti

    def requirements(self):
        if self.options.with_zlib:
            self.requires("zlib/1.2.11")

    @property
    def _cmake_install_base_path(self):
        return os.path.join("lib", "cmake", "protobuf")

    @property
    def _can_disable_rtti(self):
        return tools.Version(self.version) >= "3.15.4"

    def _configure_cmake(self):
        cmake = CMake(self)
        if self._is_msvc or self._is_clang_cl:
            runtime = msvc_runtime_flag(self)
            if not runtime:
                runtime = self.settings.get_safe("compiler.runtime")
            cmake.definitions["protobuf_MSVC_STATIC_RUNTIME"] = "MT" in runtime
        #if self.settings.compiler == "Visual Studio":
        #    cmake.definitions["protobuf_MSVC_STATIC_RUNTIME"] = "MT" in str(self.settings.compiler.runtime)
        if tools.Version(self.version) < "3.18.0" and self._is_clang_cl:
            cmake.definitions["CMAKE_RC_COMPILER"] = os.environ.get("RC", "llvm-rc")
        if self._can_disable_rtti:
            cmake.definitions["protobuf_DISABLE_RTTI"] = not self.options.with_rtti
        cmake.definitions["CMAKE_INSTALL_CMAKEDIR"] = self._cmake_install_base_path.replace("\\", "/")
        cmake.definitions["protobuf_BUILD_LIBPROTOC"] = True
        cmake.definitions["protobuf_BUILD_TESTS"] = False
        cmake.definitions["protobuf_WITH_ZLIB"] = self.options.with_zlib
        cmake.definitions["protobuf_BUILD_PROTOC_BINARIES"] = not self.options.lite
        cmake.definitions["protobuf_BUILD_PROTOBUF_LITE"] = self.options.lite
        cmake.configure(source_folder=self._source_subfolder + "/cmake", build_folder=self._build_subfolder, args=self.cmake_flags())
        return cmake

    def _patch_sources(self):
        # for ver. 3.12.4: upstream-pr-7761-cmake-regex-fix.patch
        # for ver. 3.12.4: upstream-issue-7567-no-export-template-define.patch
        #for patch in self.conan_data.get("patches", {}).get(self.version, []):
        #    tools.patch(**patch)

        tools.replace_in_file(
            os.path.join(self._source_subfolder, "cmake", "protobuf-config.cmake.in"),
            "@_protobuf_FIND_ZLIB@",
            "# CONAN PATCH _protobuf_FIND_ZLIB@"
        )
        tools.replace_in_file(
            os.path.join(self._source_subfolder, "cmake", "protobuf-config.cmake.in"),
            "include(\"${CMAKE_CURRENT_LIST_DIR}/protobuf-targets.cmake\")",
            "# CONAN PATCH include(\"${CMAKE_CURRENT_LIST_DIR}/protobuf-targets.cmake\")"
        )
        if 0: # TODO: FIXME
            if tools.Version(self.version) < "3.12.0":
                tools.replace_in_file(
                    os.path.join(self._source_subfolder, "cmake", "protobuf-config.cmake.in"),
                    """COMMAND  protobuf::protoc
        ARGS --${protobuf_generate_LANGUAGE}_out ${_dll_export_decl}${protobuf_generate_PROTOC_OUT_DIR} ${_protobuf_include_path} ${_abs_file}
        DEPENDS ${_abs_file} protobuf::protoc""",
                    """COMMAND "${CMAKE_COMMAND}"  #FIXME: use conan binary component
        ARGS -E env "DYLD_LIBRARY_PATH=${Protobuf_LIB_DIRS}:${CONAN_LIB_DIRS}:${Protobuf_LIB_DIRS_RELEASE}:${Protobuf_LIB_DIRS_DEBUG}:${Protobuf_LIB_DIRS_RELWITHDEBINFO}:${Protobuf_LIB_DIRS_MINSIZEREL}" protoc --${protobuf_generate_LANGUAGE}_out ${_dll_export_decl}${protobuf_generate_PROTOC_OUT_DIR} ${_protobuf_include_path} ${_abs_file}
        DEPENDS ${_abs_file} USES_TERMINAL"""
                )
            else:
                tools.replace_in_file(
                    os.path.join(self._source_subfolder, "cmake", "protobuf-config.cmake.in"),
                    """COMMAND  protobuf::protoc
        ARGS --${protobuf_generate_LANGUAGE}_out ${_dll_export_decl}${protobuf_generate_PROTOC_OUT_DIR} ${_plugin} ${_protobuf_include_path} ${_abs_file}
        DEPENDS ${_abs_file} protobuf::protoc""",
                    """COMMAND "${CMAKE_COMMAND}"  #FIXME: use conan binary component
        ARGS -E env "DYLD_LIBRARY_PATH=${Protobuf_LIB_DIRS}:${CONAN_LIB_DIRS}:${Protobuf_LIB_DIRS_RELEASE}:${Protobuf_LIB_DIRS_DEBUG}:${Protobuf_LIB_DIRS_RELWITHDEBINFO}:${Protobuf_LIB_DIRS_MINSIZEREL}" protoc --${protobuf_generate_LANGUAGE}_out ${_dll_export_decl}${protobuf_generate_PROTOC_OUT_DIR} ${_plugin} ${_protobuf_include_path} ${_abs_file}
        DEPENDS ${_abs_file} USES_TERMINAL"""
                )

        tools.replace_in_file(
            os.path.join(self._source_subfolder, "cmake", "protobuf-module.cmake.in"),
            'if(DEFINED Protobuf_SRC_ROOT_FOLDER)',
            """if(0)
if(DEFINED Protobuf_SRC_ROOT_FOLDER)""",
        )
        tools.replace_in_file(
            os.path.join(self._source_subfolder, "cmake", "protobuf-module.cmake.in"),
            '# Define upper case versions of output variables',
            'endif()',
        )

    def build(self):
        self._patch_sources()
        with tools.vcvars(self.settings, only_diff=False): # https://github.com/conan-io/conan/issues/6577
            #tools.patch(base_path=self._source_subfolder, patch_file="protobuf.patch")
            cmake = self._configure_cmake()
            cmake.build()

    def package(self):
        with tools.vcvars(self.settings, only_diff=False): # https://github.com/conan-io/conan/issues/6577
            self.output.info('self.settings.os: %s' % (self.settings.os))
            self.output.info('self.settings.build_type: %s' % (self.settings.build_type))

            self.copy("LICENSE", dst="licenses", src=self._source_subfolder)
            #self.copy("BUILD", dst="licenses", src=self._source_subfolder)
            self.copy("*", dst="cmake", src=os.path.join(self._source_subfolder, "cmake"))
            cmake = self._configure_cmake()
            cmake.install()

            # Do not add DEBUG_POSTFIX on non-Windows https://github.com/protocolbuffers/protobuf/pull/5484
            if self.settings.os == "Linux" and str(self.settings.build_type).lower() == "debug":
                shutil.copy(src=os.path.join(self.package_folder, "lib", "libprotobufd.a"),  dst=os.path.join(self.package_folder, "lib", "libprotobuf.a"))
                shutil.copy(src=os.path.join(self.package_folder, "lib", "libprotocd.a"),  dst=os.path.join(self.package_folder, "lib", "libprotoc.a"))
                files = [f for f in glob.glob(os.path.join(self.package_folder, "lib") + "/**", recursive=True)]
                for f in files:
                    self.output.info('protobuf libs: %s' % (f))

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
        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_module_file_name", "Protobuf")
        self.cpp_info.set_property("cmake_file_name", "protobuf")
        self.cpp_info.set_property("pkg_config_name", "protobuf_full_package") # unofficial, but required to avoid side effects (libprotobuf component "steals" the default global pkg_config name)

        build_modules = [
            os.path.join(self._cmake_install_base_path, "protobuf-generate.cmake"),
            os.path.join(self._cmake_install_base_path, "protobuf-module.cmake"),
            os.path.join(self._cmake_install_base_path, "protobuf-options.cmake"),
        ]
        self.cpp_info.set_property("cmake_build_modules", build_modules)

        self.cpp_info.libs = tools.collect_libs(self)
        self.cpp_info.libs.sort(reverse=True)

        self.cpp_info.includedirs.append(os.path.join(self.package_folder, "include"))
        self.cpp_info.includedirs.append(self.package_folder)
        #self.cpp_info.includedirs.append(os.path.join("include", "google"))

        self.cpp_info.lib_paths.append(os.path.join(self.package_folder, "lib"))

        self.cpp_info.bin_paths.append(os.path.join(self.package_folder, "bin"))

        bindir = os.path.join(self.package_folder, "bin")
        self.output.info("Appending PATH environment variable: {}".format(bindir))
        self.env_info.PATH.append(bindir)

        libdir = os.path.join(self.package_folder, "lib")
        self.output.info("Appending PATH environment variable: {}".format(libdir))
        self.env_info.PATH.append(libdir)

        protoc = "protoc.exe" if self.settings.os_build == "Windows" else "protoc"
        self.env_info.PROTOC_BIN = os.path.normpath(os.path.join(self.package_folder, "bin", protoc))
        self.user_info.PROTOC_BIN = self.env_info.PROTOC_BIN

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

# TODO: use self.cpp_info.components + libprotobuf + libprotoc + protoc + libprotobuf-lite
#
#        self.cpp_info.names["cmake_find_package"] = "protobuf"
#        self.cpp_info.names["cmake_find_package_multi"] = "protobuf"
#
#        lib_prefix = "lib" if (self._is_msvc or self._is_clang_cl or self.settings.compiler == "Visual Studio") else ""
#        lib_suffix = "d" if self.settings.build_type == "Debug" else ""
#
#        self.cpp_info.components["libprotobuf"].names["cmake_find_package"] = "libprotobuf"
#        self.cpp_info.components["libprotobuf"].names["cmake_find_package_multi"] = "libprotobuf"
#        self.cpp_info.components["libprotobuf"].names["pkg_config"] = "protobuf"
#        self.cpp_info.components["libprotobuf"].libs = [lib_prefix + "protobuf" + lib_suffix]
#        if self.options.with_zlib:
#            self.cpp_info.components["libprotobuf"].requires = ["zlib::zlib"]
#        if self.settings.os == "Linux":
#            self.cpp_info.components["libprotobuf"].system_libs.append("pthread")
#            if self._is_clang_x86 or "arm" in str(self.settings.arch):
#                self.cpp_info.components["libprotobuf"].system_libs.append("atomic")
#        if self.settings.os == "Windows":
#            if self.options.shared:
#                self.cpp_info.components["libprotobuf"].defines = ["PROTOBUF_USE_DLLS"]
#        if self.settings.os == "Android":
#            self.cpp_info.components["libprotobuf"].system_libs.append("log")
#
#        self.cpp_info.components["libprotobuf"].builddirs = [
#            self._cmake_install_base_path,
#        ]
#
#        self.cpp_info.components["libprotobuf"].builddirs = [self._cmake_install_base_path]
#        self.cpp_info.components["libprotobuf"].build_modules.extend([
#            os.path.join(self._cmake_install_base_path, "protobuf-generate.cmake"),
#            os.path.join(self._cmake_install_base_path, "protobuf-module.cmake"),
#            os.path.join(self._cmake_install_base_path, "protobuf-options.cmake"),
#        ])
#
#        self.cpp_info.components["libprotoc"].name = "libprotoc"
#        self.cpp_info.components["libprotoc"].libs = [lib_prefix + "protoc" + lib_suffix]
#        self.cpp_info.components["libprotoc"].requires = ["libprotobuf"]
#
#        self.cpp_info.components["protoc"].name = "protoc"
#        self.cpp_info.components["protoc"].requires.extend(["libprotoc", "libprotobuf"])
#
#        bindir = os.path.join(self.package_folder, "bin")
#        self.output.info("Appending PATH environment variable: {}".format(bindir))
#        self.env_info.PATH.append(bindir)
#
#        if self.options.lite:
#            self.cpp_info.components["libprotobuf-lite"].names["cmake_find_package"] = "libprotobuf-lite"
#            self.cpp_info.components["libprotobuf-lite"].names["cmake_find_package_multi"] = "libprotobuf-lite"
#            self.cpp_info.components["libprotobuf-lite"].names["pkg_config"] = "protobuf-lite"
#            self.cpp_info.components["libprotobuf-lite"].libs = [lib_prefix + "protobuf-lite" + lib_suffix]
#            if self.settings.os in ["Linux", "FreeBSD"]:
#                self.cpp_info.components["libprotobuf-lite"].system_libs.append("pthread")
#                if self._is_clang_x86 or "arm" in str(self.settings.arch):
#                    self.cpp_info.components["libprotobuf-lite"].system_libs.append("atomic")
#            if self.settings.os == "Windows":
#                if self.options.shared:
#                    self.cpp_info.components["libprotobuf-lite"].defines = ["PROTOBUF_USE_DLLS"]
#            if self.settings.os == "Android":
#                self.cpp_info.components["libprotobuf-lite"].system_libs.append("log")
#
#            self.cpp_info.components["libprotobuf-lite"].builddirs = [self._cmake_install_base_path]
#            self.cpp_info.components["libprotobuf-lite"].build_modules.extend([
#                os.path.join(self._cmake_install_base_path, "protobuf-generate.cmake"),
#                os.path.join(self._cmake_install_base_path, "protobuf-module.cmake"),
#                os.path.join(self._cmake_install_base_path, "protobuf-options.cmake"),
#            ])
#
#        # TODO: to remove in conan v2 once cmake_find_package* & pkg_config generators removed
#        self.cpp_info.filenames["cmake_find_package"] = "Protobuf"
#        self.cpp_info.filenames["cmake_find_package_multi"] = "protobuf"
#        self.cpp_info.names["pkg_config"] ="protobuf_full_package"
#        self.cpp_info.components["libprotobuf"].build_modules = build_modules
#        if self.options.lite:
#            self.cpp_info.components["libprotobuf-lite"].build_modules = build_modules

    # see `conan install . -g deploy` in https://docs.conan.io/en/latest/devtools/running_packages.html
    #def deploy(self):
        # self.copy("*", dst="/usr/local/bin", src="bin", keep_path=False)
    #    self.copy("*", dst="bin", src="bin", keep_path=False)
