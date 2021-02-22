import json

import websockets
import agorartc
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from gtts import gTTS
from clubhouse.clubhouse import Clubhouse

from donatehouse import da
from donatehouse import settings
from donatehouse import utils


app = FastAPI()
templates = Jinja2Templates(directory='templates')

da = da.DonationAlertsApi(settings.CLIENT_ID,
                          settings.REDIRECT_URI,
                          settings.SCOPE)

user_config = utils.read_config()
user_id = user_config.get('user_id')
user_token = user_config.get('user_token')
user_device = user_config.get('user_device')
client = Clubhouse(user_id=user_id,
                   user_token=user_token,
                   user_device=user_device)

RTC = agorartc.createRtcEngineBridge()
eventHandler = agorartc.RtcEngineEventHandlerBase()
RTC.initEventHandler(eventHandler)
# 0xFFFFFFFE will exclude Chinese servers from Agora's servers.
RTC.initialize(Clubhouse.AGORA_KEY,
               None,
               agorartc.AREA_CODE_GLOB & 0xFFFFFFFE)
# Enhance voice quality
RTC.setAudioProfile(agorartc.AUDIO_PROFILE_MUSIC_HIGH_QUALITY_STEREO,
                    agorartc.AUDIO_SCENARIO_GAME_STREAMING)


@app.get('/')
async def index():
    if not (user_id and user_token and user_device):
        return RedirectResponse('/config')

    utils.write_config(user_id, user_token, user_device)

    channel_info = client.join_channel(settings.CHANNEL)
    client.accept_speaker_invite(settings.CHANNEL, '0')

    channel_token = channel_info['token']
    RTC.joinChannel(channel_token, settings.CHANNEL, "", int(user_id))

    return RedirectResponse(da.authorize())


@app.get('/token')
async def token(access_token: str = Query(...)):
    da.set_access_token(access_token)
    da.get_user_info()
    await connect()


@app.get('/config', response_class=HTMLResponse)
async def config_page():
    pass


@app.post('/config')
async def update_config():
    pass


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
            text_to_speech = f'Message from {username}. {message}'
            tts_obj = gTTS(text=text_to_speech, lang='en', slow=False)
            tts_obj.save('donation.mp3')
            RTC.startAudioMixing('donation.mp3', False, True, 1)
