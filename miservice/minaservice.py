import json
import tempfile
import logging
from mutagen.mp3 import MP3

from .miaccount import MiAccount, get_random
import aiohttp

_LOGGER = logging.getLogger(__package__)


class MiNAService:
    def __init__(self, account: MiAccount):
        self.account = account

    async def _get_duration(self, url):
        start = 0
        end = 500
        headers = {"Range": f"bytes={start}-{end}"}
        response = aiohttp.get(self.url, headers=headers)
        array_buffer = response.content
        print(array_buffer)
        with tempfile.NamedTemporaryFile() as tmp:
            tmp.write(array_buffer)
            m = MP3(tmp)
            print(m.info.length)
        return m.info.length

    async def mina_request(self, uri, data=None):
        requestId = "app_ios_" + get_random(30)
        if data is not None:
            data["requestId"] = requestId
        else:
            uri += "&requestId=" + requestId
        headers = {
            "User-Agent": "MiHome/6.0.103 (com.xiaomi.mihome; build:6.0.103.1; iOS 14.4.0) Alamofire/6.0.103 MICO/iOSApp/appStore/6.0.103"
        }
        return await self.account.mi_request(
            "micoapi", "https://api2.mina.mi.com" + uri, data, headers
        )

    async def device_list(self, master=0):
        result = await self.mina_request("/admin/v2/device_list?master=" + str(master))
        return result.get("data") if result else None

    async def ubus_request(self, deviceId, method, path, message):
        message = json.dumps(message)
        result = await self.mina_request(
            "/remote/ubus",
            {"deviceId": deviceId, "message": message, "method": method, "path": path},
        )
        return result

    async def text_to_speech(self, deviceId, text):
        return await self.ubus_request(
            deviceId, "text_to_speech", "mibrain", {"text": text}
        )

    async def player_set_volume(self, deviceId, volume):
        return await self.ubus_request(
            deviceId,
            "player_set_volume",
            "mediaplayer",
            {"volume": volume, "media": "app_ios"},
        )

    async def player_pause(self, deviceId):
        return await self.ubus_request(
            deviceId,
            "player_play_operation",
            "mediaplayer",
            {"action": "pause", "media": "app_ios"},
        )

    async def player_play(self, deviceId):
        return await self.ubus_request(
            deviceId,
            "player_play_operation",
            "mediaplayer",
            {"action": "play", "media": "app_ios"},
        )

    async def player_get_status(self, deviceId):
        return await self.ubus_request(
            deviceId,
            "player_get_play_status",
            "mediaplayer",
            {"media": "app_ios"},
        )

    async def player_set_loop(self, deviceId, type=1):
        return await self.ubus_request(
            deviceId,
            "player_set_loop",
            "mediaplayer",
            {"media": "common", "type": type},
        )

    async def play_by_url(self, deviceId, url):
        return await self.ubus_request(
            deviceId,
            "player_play_url",
            "mediaplayer",
            {"url": url, "type": 1, "media": "app_ios"},
        )

    async def send_message(self, devices, devno, message, volume=None):  # -1/0/1...
        result = False
        for i in range(0, len(devices)):
            if (
                devno == -1
                or devno != i + 1
                or devices[i]["capabilities"].get("yunduantts")
            ):
                _LOGGER.debug(
                    "Send to devno=%d index=%d: %s", devno, i, message or volume
                )
                deviceId = devices[i]["deviceID"]
                result = (
                    True
                    if volume is None
                    else await self.player_set_volume(deviceId, volume)
                )
                if result and message:
                    result = await self.text_to_speech(deviceId, message)
                if not result:
                    _LOGGER.error("Send failed: %s", message or volume)
                if devno != -1 or not result:
                    break
        return result
