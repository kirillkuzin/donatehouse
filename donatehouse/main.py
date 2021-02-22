from typing import Optional
import json
import asyncio

import websockets
import agorartc
from fastapi import FastAPI, Query, Form, Request, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from gtts import gTTS
from clubhouse.clubhouse import Clubhouse

from donatehouse import da
from donatehouse import settings
from donatehouse import utils


app = FastAPI()
templates = Jinja2Templates(directory='donatehouse/templates')


class ClubhouseConfig(BaseModel):
    user_id: Optional[str]
    user_token: Optional[str]
    user_device: Optional[str]
    channel_id: Optional[str]
    language: Optional[str]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        clubhouse_config = utils.read_ch_config()
        self.user_id = clubhouse_config.get('user_id')
        self.user_token = clubhouse_config.get('user_token')
        self.user_device = clubhouse_config.get('user_device')
        self.channel_id = clubhouse_config.get('channel_id')
        self.language = clubhouse_config.get('language')


class DaConfig(BaseModel):
    client_id: Optional[int]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = utils.read_da_config()
        self.client_id = config.get('client_id')


ch_config = ClubhouseConfig()
client = Clubhouse(user_id=ch_config.user_id,
                   user_token=ch_config.user_token,
                   user_device=ch_config.user_device)

da_config = DaConfig()
da = da.DonationAlertsApi(da_config.client_id,
                          settings.REDIRECT_URI,
                          settings.SCOPE)


@app.get('/index')
async def index():
    if not (ch_config.user_id
            and ch_config.user_token
            and ch_config.user_device
            and ch_config.channel_id
            and ch_config.language):
        return RedirectResponse('/enter_phone')

    if not da_config.client_id:
        return RedirectResponse('/da_config')

    return RedirectResponse(da.authorize())


@app.get('/token')
async def da_token_handler(access_token: str = Query(...)):
    da.set_access_token(access_token)
    da.get_user_info()
    await connect()


@app.get('/enter_phone', response_class=HTMLResponse)
async def enter_phone_page(request: Request):
    return templates.TemplateResponse('enter_phone.html', {"request": request})


@app.post('/clubhouse_auth', response_class=HTMLResponse)
async def clubhouse_config_page(request: Request,
                                phone_number: str = Form(...)):
    client.start_phone_number_auth(phone_number)
    return templates.TemplateResponse('clubhouse_config.html',
                                      {"request": request,
                                       'phone_number': phone_number})


@app.post('/clubhouse_config')
async def clubhouse_config_handler(phone_number: str = Form(...),
                                   code: str = Form(...),
                                   channel: str = Form(...),
                                   lang: str = Form(...)):
    data = client.complete_phone_number_auth(phone_number, code)
    print(data)
    if 'user_profile' in data:
        ch_config.user_id = str(data['user_profile']['user_id'])
        ch_config.user_token = data['auth_token']
        ch_config.user_device = client.HEADERS.get("CH-DeviceId")
        ch_config.channel_id = channel
        ch_config.language = lang

        utils.write_ch_config(str(data['user_profile']['user_id']),
                              data['auth_token'],
                              client.HEADERS.get("CH-DeviceId"),
                              channel,
                              lang)

    return RedirectResponse('/index', status_code=status.HTTP_303_SEE_OTHER)


@app.get('/da_config', response_class=HTMLResponse)
async def da_config_page(request: Request):
    return templates.TemplateResponse('da_config.html',
                                      {"request": request})


@app.post('/da_config')
async def da_config_handler(client_id: int = Form(...)):
    da_config.client_id = client_id
    da.client_id = client_id
    utils.write_da_config(client_id)
    return RedirectResponse('/index', status_code=status.HTTP_303_SEE_OTHER)


async def clubhouse_ping():
    while True:
        client.active_ping(ch_config.channel_id)
        await asyncio.sleep(300)


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

        RTC = agorartc.createRtcEngineBridge()
        event_handler = agorartc.RtcEngineEventHandlerBase()
        RTC.initEventHandler(event_handler)
        # 0xFFFFFFFE will exclude Chinese servers from Agora's servers.
        RTC.initialize(Clubhouse.AGORA_KEY,
                       None,
                       agorartc.AREA_CODE_GLOB & 0xFFFFFFFE)
        # Enhance voice quality
        RTC.setAudioProfile(agorartc.AUDIO_PROFILE_MUSIC_HIGH_QUALITY_STEREO,
                            agorartc.AUDIO_SCENARIO_GAME_STREAMING)

        channel_info = client.join_channel(ch_config.channel_id)

        await asyncio.gather(clubhouse_ping())

        channel_token = channel_info['token']
        users = channel_info['users']

        speaker_permission = False
        while not speaker_permission:
            for user in users:
                if bool(user['is_speaker']):
                    data = client.accept_speaker_invite(ch_config.channel_id,
                                                        user['user_id'])
                    if data['success']:
                        speaker_permission = True
                        break
            await asyncio.sleep(10)

        while True:
            data = await ws.recv()
            data = json.loads(data)
            print(data)
            data = data['result']['data']['data']
            username = data['username']
            message = data['message']
            text_to_speech = f'Message from {username}. {message}'
            tts_obj = gTTS(text=text_to_speech,
                           lang=ch_config.language,
                           slow=False)
            tts_obj.save('donation.mp3')

            RTC.joinChannel(channel_token,
                            ch_config.channel_id,
                            "",
                            int(ch_config.user_id))
            await asyncio.sleep(0.5)
            RTC.startAudioMixing('donation.mp3', False, True, 1)
            donation_duration = RTC.getAudioMixingDuration()
            await asyncio.sleep(donation_duration / 1000 + 0.5)
            RTC.leaveChannel()
