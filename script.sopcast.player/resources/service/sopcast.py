# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import stat
import shutil
import sys
import subprocess
import platform

from xbmc import Monitor, Player
from kodi_six import xbmc

CREATE_NO_WINDOW = 0x08000000


class SopCastPlayer(Player):
    def __init__(self):
        Player.__init__(self)
        self.ended = False

    def onPlayBackError(self):
        self.ended = True

    def onPlayBackEnded(self):
        self.ended = True

    def onPlayBackStopped(self):
        self.ended = True


class SopCastMonitor(Monitor):
    def __init__(self, engine, env, sop_url, localport, playerport):
        Monitor.__init__(self)
        self.player = SopCastPlayer()
        self.env = env
        if type(engine) == list:
            self.engine = engine
        else:
            self.engine = [engine]
        self.localport = localport
        self.playerport = playerport
        self.sop_url = sop_url
        self.running = False

    def run(self):
        self.start_sopcast()
        while not self.abortRequested():
            if self.waitForAbort(1) or self.player.ended:
                break
        self.stop_sopcast()

    def start_sopcast(self):
        command = self.engine + [self.sop_url, self.localport, self.playerport]
        self.sopcast = subprocess.Popen(command, env=self.env)
        self.running = True

    def stop_sopcast(self):
        try:
            # terminate does not work
            self.sopcast.kill()
            # prevent GC zombies
            self.sopcast.wait()
            self.running = False
        except OSError:
            # sopcast process already dead
            pass


class DockerSopCastMonitor(Monitor):
    def __init__(self, container, sop_url, localport, playerport):
        Monitor.__init__(self)
        self.player = SopCastPlayer()
        self.container = container
        self.localport = localport
        self.playerport = playerport
        self.sop_url = sop_url
        self.image = "sopcast_{0}".format(self.playerport)
        self.running = False

    def run(self):
        self.start_sopcast()
        while not self.abortRequested():
            if self.waitForAbort(1) or self.player.ended:
                break
        self.stop_sopcast()

    def start_sopcast(self):
        command = [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            self.image,
            "-p",
            "{0}:{0}".format(self.playerport),
            self.container,
            self.sop_url,
            self.playerport,
        ]
        self.sopcast = subprocess.Popen(command, creationflags=CREATE_NO_WINDOW)
        self.running = True

    def stop_sopcast(self):
        command_stop = ["docker", "stop", self.image]
        stop = subprocess.Popen(command_stop, creationflags=CREATE_NO_WINDOW)
        stop.wait()


def log(msg):
    xbmc.log("[SopCast] {0}".format(msg), level=xbmc.LOGNOTICE)


def is_exe(fpath):
    if os.path.isfile(fpath):
        if not os.access(fpath, os.X_OK):
            st = os.stat(fpath)
            os.chmod(fpath, st.st_mode | stat.S_IEXEC)


def test_exe(engine, env):
    process = subprocess.Popen(engine, env=env, stdout=subprocess.PIPE)
    info = process.stdout.readline()
    log(info)
    process.wait()


def get_android_old_sopcast(ADDON_DATA_DIR):
    def find_apk_id(ADDON_DATA_DIR):
        xbmcfolder = xbmc.translatePath(ADDON_DATA_DIR).split("/")
        for folder in xbmcfolder:
            if folder.count(".") >= 2 and folder != "script.sopcast.player":  # !!
                return folder

    xbmc_data_path = os.path.join("/data", "data", find_apk_id(ADDON_DATA_DIR))
    android_binary_dir = os.path.join(xbmc_data_path, "files", "script.sopcast.player")
    if not os.path.exists(android_binary_dir):
        os.makedirs(android_binary_dir)
    android_binary_path = os.path.join(android_binary_dir, "sopclient")
    if not os.path.exists(android_binary_path):
        shutil.copy2(ANDROID_OLD_SOPCLIENT, android_binary_path)
    is_exe(android_binary_path)
    return android_binary_path


if __name__ == "__main__":
    ADDON_DATA_DIR = sys.argv[1]
    RESOURCES_DIR = os.path.join(ADDON_DATA_DIR, "resources")
    BIN_DIR = os.path.join(RESOURCES_DIR, "bin")
    ANDROID_OLD = os.path.join(BIN_DIR, "android_old")
    ANDROID_OLD_SOPCLIENT = os.path.join(ANDROID_OLD, "sopclient")
    LINUX_X86 = os.path.join(BIN_DIR, "linux_x86")
    LINUX_X86_SOPCLIENT = os.path.join(LINUX_X86, "sp-sc-auth")
    LINUX_ARM = os.path.join(BIN_DIR, "linux_arm")
    LINUX_ARM_LD = os.path.join(LINUX_ARM, "lib", "ld-linux.so.2")
    LINUX_ARM_SOPCLIENT = os.path.join(LINUX_ARM, "sp-sc-auth")
    LINUX_ARM_QEMU_SOPCLIENT = os.path.join(LINUX_ARM, "qemu-i386")
    LINUX_A64_QEMU_SOPCLIENT = os.path.join(LINUX_ARM, "qemuaarch-i386")
    ENGINE = None
    DOCKER = None
    ENV = {}

    sop_url = sys.argv[2]
    localport = sys.argv[3]
    playerport = sys.argv[4]

    if xbmc.getCondVisibility("system.platform.android"):
        # android <5.0 sopclient
        ENGINE = get_android_old_sopcast(ADDON_DATA_DIR)
        test_exe(ENGINE, ENV)
    elif xbmc.getCondVisibility("system.platform.linux"):
        cpu = platform.machine()
        if "x86" in cpu:
            if os.path.exists("/usr/bin/sp-sc-auth"):
                # system installed engine
                ENGINE = ["/usr/bin/sp-sc-auth"]
                test_exe(ENGINE, ENV)
            else:
                # bundeled engine
                is_exe(LINUX_X86_SOPCLIENT)
                env = os.environ.copy()
                env["LD_LIBRARY_PATH"] = LINUX_X86
                ENV = env
                ENGINE = LINUX_X86_SOPCLIENT
                test_exe(ENGINE, ENV)
        elif "arm" in cpu:
            is_exe(LINUX_ARM_QEMU_SOPCLIENT)
            is_exe(LINUX_ARM_LD)
            ENGINE = [
                LINUX_ARM_QEMU_SOPCLIENT,
                LINUX_ARM_LD,
                "--library-path",
                os.path.join(LINUX_ARM, "lib"),
                LINUX_ARM_SOPCLIENT,
            ]
            test_exe(ENGINE, ENV)
        elif "aar" in cpu:
            is_exe(LINUX_A64_QEMU_SOPCLIENT)
            is_exe(LINUX_ARM_LD)
            ENGINE = [
                LINUX_A64_QEMU_SOPCLIENT,
                LINUX_ARM_LD,
                "--library-path",
                os.path.join(LINUX_ARM, "lib"),
                LINUX_ARM_SOPCLIENT,
            ]
            test_exe(ENGINE, ENV)
        else:
            # no engine
            pass
    elif xbmc.getCondVisibility("system.platform.windows"):
        DOCKER = "danihodovic/sopcast"

    if ENGINE:
        SopCastMonitor(ENGINE, ENV, sop_url, localport, playerport).run()
    elif DOCKER:
        DockerSopCastMonitor(DOCKER, sop_url, localport, playerport).run()
