"""API & mock data
https://requests.readthedocs.io/en/latest/user/quickstart/
https://developers.home-assistant.io/docs/integration_fetching_data
https://3.python-requests.org/user/advanced/
"""

import logging
import requests
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse, parse_qs
from .const import HTTP_TIMEOUT

_LOGGER = logging.getLogger(__name__)

MOCK_EAN_ELECTRICITY = "000000000123456789"
MOCK_EAN_GAS = "123456789000000000"

MOCK_DATA_METERS = {
    'meters': [{
            'ean': MOCK_EAN_ELECTRICITY, 
            'energyType': 'Electricity', 
            'sources': [{'sourceProvider': 'SAP'}, {'sourceProvider': 'BasicMonitoring', 'status': 'Eligible'}]
        }, {
            'ean': MOCK_EAN_GAS, 
            'energyType': 'Gas', 
            'sources': [{'sourceProvider': 'SAP'}, {'sourceProvider': 'BasicMonitoring', 'status': 'Eligible'}]
        }
    ]
}

MOCK_DATA = {
    MOCK_EAN_ELECTRICITY: {
        "productName":"Luminus Elektriciteit",
        "disclaimer":"De vermelde prijzen en eventuele promoties zijn incl. 6% BTW, de tariefformules zijn exclusief btw. ...de prijzen en promoties.",
        "activeMeterType":"dual",
        "prices":{
            "single":{
                "fixed":{"rate":25},
                "single":{"rate":9.31,"formula":"0.0010881 x Belpex RLP M [67.52] + 0.014342"},
                "injectionSingle":{"rate":2.62,"formula":"0.0006444 x Belpex M INJ [65.33] - 0.0159"}
            },
            "dual":{
                "fixed":{"rate":25},
                "dualDay":{"rate":10.93,"formula":"0.001261 x Belpex RLP M [67.52] + 0.0179388"},
                "dualNight":{"rate":7.99,"formula":"0.000943 x Belpex RLP M [67.52] + 0.0116652"},
                "injectionDualDay":{"rate":3.6,"formula":"0.0007944 x Belpex M INJ [65.33] - 0.0159"},
                "injectionDualNight":{"rate":1.12,"formula":"0.0004144 x Belpex M INJ [65.33] - 0.0159"}
            },
            "singleExclusiveNight":{
                "fixed":{"rate":25},
                "single":{"rate":9.31,"formula":"0.0010881 x Belpex RLP M [67.52] + 0.014342"},
                "exclusiveNight":{"rate":7.99,"formula":"0.000943 x Belpex RLP M [67.52] + 0.0116652"},
                "injectionSingle":{"rate":2.62,"formula":"0.0006444 x Belpex M INJ [65.33] - 0.0159"}
            },
            "dualExclusiveNight":{
                "fixed":{"rate":25},
                "dualDay":{"rate":10.93,"formula":"0.001261 x Belpex RLP M [67.52] + 0.0179388"},
                "dualNight":{"rate":7.99,"formula":"0.000943 x Belpex RLP M [67.52] + 0.0116652"},
                "exclusiveNight":{"rate":7.99,"formula":"0.000943 x Belpex RLP M [67.52] + 0.0116652"},
                "injectionDualDay":{"rate":3.6,"formula":"0.0007944 x Belpex M INJ [65.33] - 0.0159"},
                "injectionDualNight":{"rate":1.12,"formula":"0.0004144 x Belpex M INJ [65.33] - 0.0159"}
            }
        },"promotionsContent":[]
    },
    MOCK_EAN_GAS: {
        "productName":"Luminus Gas",
        "disclaimer":"De vermelde prijzen en eventuele promoties zijn incl. 6% BTW, de tariefformules zijn exclusief btw. ... de prijzen en promoties.",
        "activeMeterType":"single",
        "prices":{
            "single":{
                "fixed":{"rate":20},
                "single":{"rate":4.4,"formula":"0.001 x TTF DAH RLP M [36.167] + 0.0053"}
            }
        },"promotionsContent":[]
    }
}
    
defHeaders = { 
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'nl,en-US;q=0.7,en;q=0.3',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests' : '1',
    'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0'
}

class API:
    
    def __init__(self, user: str, pwd: str, mock: bool = False) -> None:
        self.user = user
        self.pwd = pwd
        self.session = requests.Session()
        self.session.headers.update(defHeaders)
        self.mock = mock
        self.mock_data = deepcopy(MOCK_DATA)
        self.mock_data_meters = deepcopy(MOCK_DATA_METERS)        
        self.isLoggedIn = False        

    def get_meters(self) -> list[dict[str, Any]]:
        if self.mock:
            return self.mock_data_meters;
        return self.get_data('https://www.luminus.be/myluminus/api/meter-readings/available-sources')
        
    def get_meter(self, ean: str) -> list[dict[str, Any]]:
        if self.mock:
            return self.mock_data[ean]
        return self.get_data(f"https://www.luminus.be/myluminus/api/price-information/{ean}")
        
    def get_data(self, url: str) -> list[dict[str, Any]]:
        try:
            r = self.session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=False)
            if(r.status_code == requests.codes.forbidden):
                self.isLoggedIn = False
                self.login()
                r = self.session.get(url, timeout=HTTP_TIMEOUT, allow_redirects=False)
                
            if(r.status_code != requests.codes.ok):
                _LOGGER.warning("Luminus response error", r.url, r.status_code, r.text)
                self.isLoggedIn = False
                raise APIConnectionError("Error connecting to api")
            return r.json()
        except requests.exceptions.ConnectTimeout as err:
            raise APIConnectionError("Timeout connecting to api") from err
        except Exception as err:
            raise APIConnectionError(err)
        
    def login(self):
        
        if self.mock or self.isLoggedIn:
        #if self.mock:
            return
            
        _LOGGER.debug('Luminus Login called!')
        r = self.session.get(f"https://www.luminus.be/myluminus/nl/", timeout=30)
        u = urlparse(r.history[-1].headers['location'])
        q = parse_qs(u.query)
        s = q['state'][0]

        authUriQry = { 'state': s}
        idHeaders = { 
            'Origin': 'https://login.luminus.be', 
            'Referer': 'https://login.luminus.be/u/login/identifier?state=' + s
        }        
        idReqBody = { 
            'state': s, 
            'username': self.user, 
            'js-available': 'false', 
            'webauthn-available' : 'false', 
            'is-brave': 'false', 
            'webauthn-platform-available' : 'false', 
            'action': 'default' 
        }
        idReq = self.session.post('https://login.luminus.be/u/login/identifier', params=authUriQry, data=idReqBody, timeout=30, headers=idHeaders)
        if(idReq.status_code != requests.codes.ok):
            raise APIAuthError()
            
        authHeaders = { 
            'Origin': 'https://login.luminus.be', 
            'Referer': 'https://login.luminus.be/u/login/password?state=' + s
        }
        authReqBody = { 
            'state': s, 
            'username': self.user, 
            'password': self.pwd,
            'action': 'default' 
        }
        authReq = self.session.post('https://login.luminus.be/u/login/password', params=authUriQry, data=authReqBody, timeout=30, headers=authHeaders)       
        self.isLoggedIn = authReq.status_code == requests.codes.ok
        if(authReq.status_code != requests.codes.ok):
            raise APIAuthError()
            
        _LOGGER.info('Luminus logged in!')

    def logout(self):

        if self.mock or not self.isLoggedIn:
            return
        try:
            _LOGGER.warning("Logout LUMINUS")
            r = self.session.get(f"https://www.luminus.be/myluminus/api/auth/logout", timeout=HTTP_TIMEOUT)
            self.isLoggedIn = False
            return r.json()
        except requests.exceptions.ConnectTimeout as err:
            raise APIConnectionError("Timeout connecting to api") from err


class APIAuthError(Exception):
    """Exception class for auth error."""


class APIConnectionError(Exception):
    """Exception class for connection error."""
