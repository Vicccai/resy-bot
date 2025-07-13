from datetime import datetime
from requests import Session, HTTPError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.connection import create_connection
from urllib3.poolmanager import PoolManager
import socket
from typing import Dict, List

from resy_bot.constants import RESY_BASE_URL, ResyEndpoints
from resy_bot.logging import logging
from resy_bot.models import (
    ResyConfig,
    AuthRequestBody,
    AuthResponseBody,
    FindRequestBody,
    FindResponseBody,
    Slot,
    DetailsRequestBody,
    DetailsResponseBody,
    BookRequestBody,
    BookResponseBody,
)

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


class FastHTTPAdapter(HTTPAdapter):
    """Custom HTTP adapter optimized for speed"""
    
    def __init__(self, *args, **kwargs):
        # Pre-resolve DNS for api.resy.com
        self.resy_ip = None
        try:
            self.resy_ip = socket.gethostbyname("api.resy.com")
            logger.info(f"Pre-resolved api.resy.com to {self.resy_ip}")
        except Exception as e:
            logger.warning(f"DNS pre-resolution failed: {e}")
        
        super().__init__(*args, **kwargs)
    
    def init_poolmanager(self, *args, **kwargs):
        """Initialize with optimized connection pool"""
        kwargs['socket_options'] = [
            (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
            (socket.SOL_TCP, socket.TCP_NODELAY, 1),
        ]
        return super().init_poolmanager(*args, **kwargs)


def build_session(config: ResyConfig) -> Session:
    session = Session()
    
    # Configure HTTP adapter with aggressive optimization for first request
    adapter = FastHTTPAdapter(
        pool_connections=20,       # Increased connection pool
        pool_maxsize=50,          # Increased pool size
        max_retries=0,            # We handle retries manually for time-critical operations
        pool_block=False          # Don't block when pool is full
    )
    
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    # Set aggressive timeouts for speed - optimized for resy API
    session.timeout = (1.0, 3.0)  # Even faster timeouts: (connect timeout, read timeout)
    
    headers = {
        "Authorization": config.get_authorization(),
        "X-Resy-Auth-Token": config.token,
        "X-Resy-Universal-Auth": config.token,
        "Origin": "https://resy.com",
        "X-origin": "https://resy.com",
        "Referrer": "https://resy.com/",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",  # Enable connection reuse
        "Accept-Encoding": "gzip, deflate, br",  # Enable compression
    }

    session.headers.update(headers)

    return session


class ResyApiAccess:
    @classmethod
    def build(cls, config: ResyConfig) -> "ResyApiAccess":
        session = build_session(config)
        return cls(session)

    def __init__(self, session: Session):
        self.session = session

    def find_venue(self):
        pass

    def auth(self, body: AuthRequestBody) -> AuthResponseBody:
        auth_url = RESY_BASE_URL + ResyEndpoints.PASSWORD_AUTH.value

        resp = self.session.post(
            auth_url,
            data=body.dict(),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

        if not resp.ok:
            raise HTTPError(f"Failed to get auth: {resp.status_code}, {resp.text}")

        return AuthResponseBody(**resp.json())

    def find_booking_slots(self, params: FindRequestBody) -> List[Slot]:
        find_url = RESY_BASE_URL + ResyEndpoints.FIND.value

        logger.info(
            f"{datetime.now().isoformat()} Sending request to find booking slots"
        )

        resp = self.session.get(find_url, params=params.dict())

        logger.info(f"{datetime.now().isoformat()} Received response for ")

        if not resp.ok:
            raise HTTPError(
                f"Failed to find booking slots: {resp.status_code}, {resp.text}"
            )

        parsed_resp = FindResponseBody(**resp.json())

        return parsed_resp.results.venues[0].slots

    def get_booking_token(self, params: DetailsRequestBody) -> DetailsResponseBody:
        details_url = RESY_BASE_URL + ResyEndpoints.DETAILS.value

        resp = self.session.get(details_url, params=params.dict())

        if not resp.ok:
            raise HTTPError(
                f"Failed to get selected slot details: {resp.status_code}, {resp.text}"
            )

        return DetailsResponseBody(**resp.json())

    def _dump_book_request_body_to_dict(self, body: BookRequestBody) -> Dict:
        """
        requests lib doesn't urlencode nested dictionaries,
        so dump struct_payment_method to json and slot that in the dict
        """
        payment_method = body.struct_payment_method.json().replace(" ", "")
        body_dict = body.dict()
        body_dict["struct_payment_method"] = payment_method
        return body_dict

    def book_slot(self, body: BookRequestBody) -> str:
        book_url = RESY_BASE_URL + ResyEndpoints.BOOK.value

        body_dict = self._dump_book_request_body_to_dict(body)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://widgets.resy.com",
            "X-Origin": "https://widgets.resy.com",
            "Referrer": "https://widgets.resy.com/",
            "Cache-Control": "no-cache",
        }

        resp = self.session.post(
            book_url,
            data=body_dict,
            headers=headers,
        )

        if not resp.ok:
            raise HTTPError(f"Failed to book slot: {resp.status_code}, {resp.text}")

        logger.info(resp.json())
        parsed_resp = BookResponseBody(**resp.json())

        return parsed_resp.resy_token
