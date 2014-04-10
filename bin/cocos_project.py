import os
import re
import json
import cocos

class Project(object):
    CPP = 'cpp'
    LUA = 'lua'
    JS = 'js'

    CONFIG = '.cocos-project.json'

    KEY_PROJ_TYPE = 'project_type'
    KEY_HAS_NATIVE = 'has_native'


    @staticmethod
    def list_for_display():
        return [x.lower() for x in Project.language_list()]

    @staticmethod
    def language_list():
        return (Project.CPP, Project.LUA, Project.JS)

    def __init__(self, project_dir):
        # parse the config file
        self.info = self._parse_project_json(project_dir)

    def _parse_project_json(self, src_dir):
        proj_path = self._find_project_dir(src_dir)
        # config file is not found
        if proj_path == None:
            raise cocos.CCPluginError("Can't find config file %s in path %s" % (Project.CONFIG, src_dir))

        project_json = os.path.join(proj_path, Project.CONFIG)
        try:
            f = open(project_json)
            project_info = json.load(f)
            f.close()
        except Exception:
            if f is not None:
                f.close()
            raise cocos.CCPluginError("Configuration file %s is broken!" % project_json)

        if project_info is None:
            raise cocos.CCPluginError("Parse configuration in file \"%s\" failed." % Project.CONFIG)

        if not project_info.has_key(Project.KEY_PROJ_TYPE):
            raise cocos.CCPluginError("Can't get value of \"%s\" in file \"%s\"." % (Project.KEY_PROJ_TYPE, Project.CONFIG))

        lang = project_info[Project.KEY_PROJ_TYPE]
        lang = lang.lower()

        # The config is invalide
        if not (lang in Project.language_list()):
            raise cocos.CCPluginError("The value of \"%s\" must be one of (%s)" % (Project.KEY_PROJ_TYPE, ', '.join(Project.list_for_display())))

        # record the dir & language of the project
        self._project_dir = proj_path
        self._project_lang = lang

        # if is script project, record whether it has native or not
        self._has_native = False
        if (self._is_script_project() and project_info.has_key(Project.KEY_HAS_NATIVE)):
            self._has_native = project_info[Project.KEY_HAS_NATIVE]

        return project_info

    def _find_project_dir(self, start_path):
        path = start_path
        while True:
            if cocos.os_is_win32():
                # windows root path, eg. c:\
                if re.match(".+:\\\\$", path):
                    break
            else:
                # unix like use '/' as root path
                if path == '/' :
                    break
            cfg_path = os.path.join(path, Project.CONFIG)
            if (os.path.exists(cfg_path) and os.path.isfile(cfg_path)):
                return path

            path = os.path.dirname(path)

        return None

    def get_project_dir(self):
        return self._project_dir

    def get_language(self):
        return self._project_lang

    def _is_native_support(self):
        return self._has_native

    def _is_script_project(self):
        return self._is_lua_project() or self._is_js_project()

    def _is_cpp_project(self):
        return self._project_lang == Project.CPP

    def _is_lua_project(self):
        return self._project_lang == Project.LUA

    def _is_js_project(self):
        return self._project_lang == Project.JS

class Platforms(object):
    ANDROID = 'android'
    IOS = 'ios'
    MAC = 'mac'
    WEB = 'web'
    WIN32 = 'win32'
    LINUX = 'linux'

    CFG_CLASS_MAP = {
        ANDROID : "cocos_project.AndroidConfig",
        IOS : "cocos_project.iOSConfig",
        MAC : "cocos_project.MacConfig",
        WEB : "cocos_project.WebConfig",
        WIN32 : "cocos_project.Win32Config",
        LINUX : "cocos_project.LinuxConfig"
    }

    @staticmethod
    def list_for_display():
        return [x.lower() for x in Platforms.list()]

    @staticmethod
    def list():
        return (Platforms.ANDROID, Platforms.IOS, Platforms.MAC, Platforms.WEB, Platforms.WIN32, Platforms.LINUX)

    def __init__(self, project, current):
        self._project = project

        proj_info = self._project.info
        self._gen_available_platforms(proj_info)

        self._current = None
        if current is not None:
            current_lower = current.lower()
            if current_lower in self._available_platforms.keys():
                self._current = current_lower

    def _filter_platforms(self, platforms):
        ret = []
        for p in platforms:
            if cocos.os_is_linux():
                if p == Platforms.WEB or p == Platforms.LINUX or p == Platforms.ANDROID:
                    ret.append(p)
            if cocos.os_is_mac():
                if p == Platforms.WEB or p == Platforms.IOS or p == Platforms.MAC or p == Platforms.ANDROID:
                    ret.append(p)
            if cocos.os_is_win32():
                if p == Platforms.WEB or p == Platforms.WIN32 or p == Platforms.ANDROID:
                    ret.append(p)

        return ret

    def _gen_available_platforms(self, proj_info):
        # generate the platform list for different projects
        if self._project._is_lua_project():
            if self._project._is_native_support():
                platform_list = [ Platforms.ANDROID, Platforms.WIN32, Platforms.IOS, Platforms.MAC, Platforms.LINUX ]
            else:
                platform_list = []
        elif self._project._is_js_project():
            if self._project._is_native_support():
                platform_list = [ Platforms.ANDROID, Platforms.WIN32, Platforms.IOS, Platforms.MAC, Platforms.WEB ]
            else:
                platform_list = [ Platforms.WEB ]
        elif self._project._is_cpp_project():
            platform_list = [ Platforms.ANDROID, Platforms.WIN32, Platforms.IOS, Platforms.MAC, Platforms.LINUX ]

        # filter the available platform list
        platform_list = self._filter_platforms(platform_list)

        # check the real available platforms
        self._available_platforms = {}
        root_path = self._project.get_project_dir()
        for p in platform_list:
            cfg_class = cocos.get_class(Platforms.CFG_CLASS_MAP[p])
            if cfg_class is None:
                continue

            cfg_key = "%s_cfg" % p
            if proj_info.has_key(cfg_key):
                cfg_obj = cfg_class(root_path, self._project._is_script_project(), proj_info[cfg_key])
            else:
                cfg_obj = cfg_class(root_path, self._project._is_script_project())

            if cfg_obj._is_available():
                self._available_platforms[p] = cfg_obj

        # don't have available platforms
        if len(self._available_platforms) == 0:
            raise cocos.CCPluginError("There isn't any available platforms")

    def get_available_platforms(self):
        return self._available_platforms

    def none_active(self):
        return self._current is None

    def is_android_active(self):
        return self._current == Platforms.ANDROID

    def is_ios_active(self):
        return self._current == Platforms.IOS

    def is_mac_active(self):
        return self._current == Platforms.MAC

    def is_web_active(self):
        return self._current == Platforms.WEB

    def is_win32_active(self):
        return self._current == Platforms.WIN32

    def is_linux_active(self):
        return self._current == Platforms.LINUX

    def get_current_config(self):
        if self.none_active():
            return None

        return self._available_platforms[self._current]

    def project_path(self):
        if self._current is None:
            return None

        cfg_obj = self._available_platforms[self._current]
        return cfg_obj.proj_path

    def _has_one(self):
        return len(self._available_platforms) == 1

    def select_one(self):
        if self._has_one():
            return self._available_platforms.keys()[0]

        raise cocos.CCPluginError("The target platform is not specified.\n" +
            "You can specify a target platform with \"-p\" or \"--platform\".\n" +
            "Available platforms : %s" % str(self._available_platforms.keys()))

class PlatformConfig(object):
    KEY_PROJ_PATH = "project_path"
    def __init__(self, proj_root_path, is_script, cfg_info = None):
        self._proj_root_path = proj_root_path
        self._is_script = is_script
        if cfg_info is None:
            self._use_default()
        else:
            self._parse_info(cfg_info)

    def _use_default(self):
        pass

    def _parse_info(self, cfg_info):
        if cfg_info.has_key(PlatformConfig.KEY_PROJ_PATH):
            self.proj_path = os.path.join(self._proj_root_path, cfg_info[PlatformConfig.KEY_PROJ_PATH])
        else:
            self.proj_path = None

    def _is_available(self):
        ret = True
        if self.proj_path is None or not os.path.isdir(self.proj_path):
            ret = False

        return ret

class AndroidConfig(PlatformConfig):

    def _use_default(self):
        if self._is_script:
            self.proj_path = os.path.join(self._proj_root_path, "frameworks", "runtime-src", "proj.android")
        else:
            self.proj_path = os.path.join(self._proj_root_path, "proj.android")

    def _parse_info(self, cfg_info):
        super(AndroidConfig, self)._parse_info(cfg_info)

    def _is_available(self):
        ret = super(AndroidConfig, self)._is_available()

        return ret

class iOSConfig(PlatformConfig):
    KEY_PROJ_FILE = "project_file"
    KEY_TARGET_NAME = "target_name"

    def _use_default(self):
        if self._is_script:
            self.proj_path = os.path.join(self._proj_root_path, "frameworks", "runtime-src", "proj.ios_mac")
        else:
            self.proj_path = os.path.join(self._proj_root_path, "proj.ios_mac")

        self.proj_file = None
        self.target_name = None

    def _parse_info(self, cfg_info):
        super(iOSConfig, self)._parse_info(cfg_info)
        if cfg_info.has_key(iOSConfig.KEY_PROJ_FILE):
            self.proj_file = cfg_info[iOSConfig.KEY_PROJ_FILE]
        else:
            self.proj_file = None

        if cfg_info.has_key(iOSConfig.KEY_TARGET_NAME):
            self.target_name = cfg_info[iOSConfig.KEY_TARGET_NAME]
        else:
            self.target_name = None

    def _is_available(self):
        ret = super(iOSConfig, self)._is_available()

        return ret

class MacConfig(PlatformConfig):

    def _use_default(self):
        if self._is_script:
            self.proj_path = os.path.join(self._proj_root_path, "frameworks", "runtime-src", "proj.ios_mac")
        else:
            self.proj_path = os.path.join(self._proj_root_path, "proj.ios_mac")

        self.proj_file = None
        self.target_name = None

    def _parse_info(self, cfg_info):
        super(MacConfig, self)._parse_info(cfg_info)
        if cfg_info.has_key(iOSConfig.KEY_PROJ_FILE):
            self.proj_file = cfg_info[iOSConfig.KEY_PROJ_FILE]
        else:
            self.proj_file = None

        if cfg_info.has_key(iOSConfig.KEY_TARGET_NAME):
            self.target_name = cfg_info[iOSConfig.KEY_TARGET_NAME]
        else:
            self.target_name = None

    def _is_available(self):
        ret = super(MacConfig, self)._is_available()

        return ret

class Win32Config(PlatformConfig):
    KEY_SLN_FILE = "sln_file"
    KEY_PROJECT_NAME = "project_name"
    KEY_BUILD_CFG_PATH = "build_cfg_path"

    def _use_default(self):
        if self._is_script:
            self.proj_path = os.path.join(self._proj_root_path, "frameworks", "runtime-src", "proj.win32")
        else:
            self.proj_path = os.path.join(self._proj_root_path, "proj.win32")

        self.sln_file = None
        self.project_name =None
        self.build_cfg_path = None

    def _parse_info(self, cfg_info):
        super(Win32Config, self)._parse_info(cfg_info)
        if cfg_info.has_key(Win32Config.KEY_SLN_FILE):
            self.sln_file = cfg_info[Win32Config.KEY_SLN_FILE]
        else:
            self.sln_file = None

        if cfg_info.has_key(Win32Config.KEY_PROJECT_NAME):
            self.project_name = cfg_info[Win32Config.KEY_PROJECT_NAME]
        else:
            self.project_name = None

        if cfg_info.has_key(Win32Config.KEY_BUILD_CFG_PATH):
            self.build_cfg_path = cfg_info[Win32Config.KEY_BUILD_CFG_PATH]
        else:
            self.build_cfg_path = None

    def _is_available(self):
        ret = super(Win32Config, self)._is_available()

        return ret

class LinuxConfig(PlatformConfig):
    KEY_CMAKE_PATH = "cmake_path"
    KEY_BUILD_DIR = "build_dir"
    KEY_PROJECT_NAME = "project_name"
    KEY_BUILD_RESULT_DIR = "build_result_dir"

    def _use_default(self):
        if self._is_script:
            self.proj_path = os.path.join(self._proj_root_path, "frameworks", "runtime-src", "proj.linux")
        else:
            self.proj_path = os.path.join(self._proj_root_path, "proj.linux")

        self.cmake_path = None
        self.build_dir = None
        self.project_name = None
        self.build_result_dir = None

    def _parse_info(self, cfg_info):
        super(LinuxConfig, self)._parse_info(cfg_info)
        if cfg_info.has_key(LinuxConfig.KEY_CMAKE_PATH):
            self.cmake_path = cfg_info[LinuxConfig.KEY_CMAKE_PATH]
        else:
            self.cmake_path = None

        if cfg_info.has_key(LinuxConfig.KEY_BUILD_DIR):
            self.build_dir = cfg_info[LinuxConfig.KEY_BUILD_DIR]
        else:
            self.build_dir = None

        if cfg_info.has_key(LinuxConfig.KEY_PROJECT_NAME):
            self.project_name = cfg_info[LinuxConfig.KEY_PROJECT_NAME]
        else:
            self.project_name = None

        if cfg_info.has_key(LinuxConfig.KEY_BUILD_RESULT_DIR):
            self.build_result_dir = cfg_info[LinuxConfig.KEY_BUILD_RESULT_DIR]
        else:
            self.build_result_dir = None

    def _is_available(self):
        ret = super(LinuxConfig, self)._is_available()

        return ret

class WebConfig(PlatformConfig):
    KEY_SUB_URL = "sub_url"
    KEY_RUN_ROOT_DIR = "run_root_dir"

    def _use_default(self):
        self.proj_path = self._proj_root_path
        self.run_root_dir = self._proj_root_path
        self.sub_url = None

    def _parse_info(self, cfg_info):
        super(WebConfig, self)._parse_info(cfg_info)
        if cfg_info.has_key(WebConfig.KEY_SUB_URL):
            self.sub_url = cfg_info[WebConfig.KEY_SUB_URL]
        else:
            self.sub_url = None

        if cfg_info.has_key(WebConfig.KEY_RUN_ROOT_DIR):
            self.run_root_dir = os.path.join(self._proj_root_path, cfg_info[WebConfig.KEY_RUN_ROOT_DIR])
        else:
            self.run_root_dir = None

    def _is_available(self):
        ret = super(WebConfig, self)._is_available()

        return ret
