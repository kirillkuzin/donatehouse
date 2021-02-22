import requests


class DonationAlertsApi:
    DONATION_ALERTS_URL = 'https://www.donationalerts.com'
    AUTHORIZE_URL = f'{DONATION_ALERTS_URL}/oauth/authorize'

    def __init__(self, client_id: int, redirect_uri: str, scope: str):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.access_token = None
        self.headers = {}
        self.socket_connection_token = None
        self.centrifugo_client_id = None
        self.user_id = None
        self.channel = None
        self.channel_connection_token = None

    def authorize(self):
        params = {'client_id': self.client_id,
                  'redirect_uri': self.redirect_uri,
                  'response_type': 'token',
                  'scope': self.scope}
        query = '&'.join([f'{key}={value}' for key, value in params.items()])
        return f'{self.AUTHORIZE_URL}?{query}'

    def set_access_token(self, access_token: str):
        self.access_token = access_token
        self.headers.update({'Authorization': f'Bearer {self.access_token}'})

    def get_user_info(self):
        response = requests.get(
            f'{self.DONATION_ALERTS_URL}/api/v1/user/oauth',
            headers=self.headers
        )
        data = response.json()['data']
        self.socket_connection_token = data['socket_connection_token']
        self.user_id = data['id']
        self.channel = f'$alerts:donation_{self.user_id}'

    def ws_authorize(self):
        return {'params': {'token': self.socket_connection_token}, 'id': 1}

    def set_centrifugo_client_id(self, client_id: str):
        self.centrifugo_client_id = client_id

    def subscribe(self):
        body = {'channels': [self.channel],
                'client': self.centrifugo_client_id}
        response = requests.post(
            f'{self.DONATION_ALERTS_URL}/api/v1/centrifuge/subscribe',
            json=body,
            headers=self.headers
        )
        data = response.json()['channels']
        self.channel_connection_token = data[0]['token']

    def ws_connect(self):
        return {'params': {'channel': self.channel,
                           'token': self.channel_connection_token},
                'method': 1,
                'id': 2}
