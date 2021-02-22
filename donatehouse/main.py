import json
import configparser

import websockets
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from gtts import gTTS

from donatehouse.da import DonationAlertsApi
from donatehouse import settings

from clubhouse.clubhouse import Clubhouse

# Set some global variables
try:
    import agorartc
    RTC = agorartc.createRtcEngineBridge()
    eventHandler = agorartc.RtcEngineEventHandlerBase()
    RTC.initEventHandler(eventHandler)
    # 0xFFFFFFFE will exclude Chinese servers from Agora's servers.
    RTC.initialize(Clubhouse.AGORA_KEY, None, agorartc.AREA_CODE_GLOB & 0xFFFFFFFE)
    # Enhance voice quality
    if RTC.setAudioProfile(
            agorartc.AUDIO_PROFILE_MUSIC_HIGH_QUALITY_STEREO,
            agorartc.AUDIO_SCENARIO_GAME_STREAMING
        ) < 0:
        print("[-] Failed to set the high quality audio profile")
except ImportError:
    RTC = None


def read_config(filename='setting.ini'):
    """ (str) -> dict of str
    Read Config
    """
    config = configparser.ConfigParser()
    config.read(filename)
    if "Account" in config:
        return dict(config['Account'])
    return dict()


app = FastAPI()
da = DonationAlertsApi(settings.CLIENT_ID,
                       settings.REDIRECT_URI,
                       settings.SCOPE)
user_config = read_config()
user_id = user_config.get('user_id')
user_token = user_config.get('user_token')
user_device = user_config.get('user_device')
client = Clubhouse(
            user_id=user_id,
            user_token=user_token,
            user_device=user_device
        )
channel_info = client.join_channel(settings.CHANNEL)
# import time
# time.sleep(10)
client.accept_speaker_invite(settings.CHANNEL, '0')
token = channel_info['token']
RTC.joinChannel(token, settings.CHANNEL, "", int(user_id))


@app.get('/')
async def index():
    return RedirectResponse(da.authorize())


@app.get('/token')
async def token(access_token: str = Query(...)):
    da.set_access_token(access_token)
    da.get_user_info()
    await connect()


async def connect():
    async with websockets.connect(settings.CENTRIFUGO_WS) as ws:
        await ws.send(json.dumps(da.ws_authorize()))
        data = await ws.recv()
        data = json.loads(data)
        da.set_centrifugo_client_id(data['result']['client'])
        da.subscribe()
        await ws.send(json.dumps(da.ws_connect()))
        await ws.recv()
        await ws.recv()
        while True:
            data = await ws.recv()
            data = json.loads(data)
            data = data['result']['data']['data']
            username = data['username']
            message = data['message']
            mytext = f'Message from {username}. {message}'
            myobj = gTTS(text=mytext, lang='en', slow=False)
            myobj.save('donation.mp3')
            RTC.startAudioMixing('donation.mp3', False, True, 1)
