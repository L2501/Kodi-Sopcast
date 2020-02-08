# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import sys
from kodi_six import xbmc, xbmcgui, xbmcaddon, xbmcplugin
from routing import Plugin

import re
import socket
import requests
from contextlib import closing

addon = xbmcaddon.Addon()
plugin = Plugin()
plugin.name = addon.getAddonInfo("name")

ADDON_DATA_DIR = xbmc.translatePath(addon.getAddonInfo("path"))
RESOURCES_DIR = os.path.join(ADDON_DATA_DIR, "resources")
XBMC_SOP_SCRIPT = os.path.join(RESOURCES_DIR, "service", "sopcast.py")
SOP_SCRIPT = None


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@plugin.route("/")
def root():
    sop_url = plugin.args.get("url", [""])[-1]
    if sop_url:
        timeout = int(plugin.args.get("timeout", ["90"])[-1])
        localport = int(plugin.args.get("localport", [find_free_port()])[-1])
        playerport = int(plugin.args.get("playerport", [find_free_port()])[-1])
        player_url = "http://127.0.0.1:{0}".format(playerport)

        # Linux, Android <=4.4: run sopcast binary
        # Windows: Run docker sopcast container
        # Other: External player
        if xbmc.getCondVisibility("system.platform.android"):
            OS_VERSION = xbmc.getInfoLabel("System.OSVersionInfo")
            API_LEVEL = int(re.search("API level (\d+)", OS_VERSION).group(1))
            if API_LEVEL < 20:
                SOP_SCRIPT = XBMC_SOP_SCRIPT
            else:
                APKS = ["org.sopcast.android", "com.devaward.soptohttp", "com.trimarts.soptohttp"]
                for EXTERNAL_SOP in APKS:
                    if os.path.exists(os.path.join("/data", "data", EXTERNAL_SOP)):
                        SOP_ACTIVITY = """XBMC.StartAndroidActivity("{0}","android.intent.action.VIEW","",{1})""".format(EXTERNAL_SOP, url)
                        break
                xbmc.executebuiltin(SOP_ACTIVITY)
        elif xbmc.getCondVisibility("system.platform.linux"):
            SOP_SCRIPT = XBMC_SOP_SCRIPT
        elif xbmc.getCondVisibility("system.platform.windows"):
            SOP_SCRIPT = XBMC_SOP_SCRIPT

        if SOP_SCRIPT:
            LIVE = False
            xbmc.executebuiltin(
                "RunScript({0},{1},{2},{3},{4})".format(
                    SOP_SCRIPT, ADDON_DATA_DIR, sop_url, localport, playerport
                )
            )
            pDialog = xbmcgui.DialogProgress()
            pDialog.create(plugin.name)
            session = requests.session()
            for i in range(timeout):
                pDialog.update(int(i / float(timeout) * 100))
                if pDialog.iscanceled():
                    break
                try:
                    _r = session.get(player_url, stream=True, timeout=1)
                    _r.raise_for_status()
                    LIVE = True
                    break
                except Exception:
                    xbmc.sleep(1000)

            session.close()
            pDialog.close()

            if LIVE:
                li = xbmcgui.ListItem(path=player_url)
                xbmcplugin.setResolvedUrl(plugin.handle, True, li)
            else:
                xbmcplugin.setResolvedUrl(plugin.handle, False, xbmcgui.ListItem())
        else:
            li = xbmcgui.ListItem(path=sop_url)
            xbmcplugin.setResolvedUrl(plugin.handle, True, li)


if __name__ == "__main__":
    plugin.run(sys.argv)
