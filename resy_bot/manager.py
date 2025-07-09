from datetime import date, datetime, timedelta
import time
import asyncio
import aiohttp
import json

from resy_bot.logging import logging
from resy_bot.errors import NoSlotsError, ExhaustedRetriesError
from resy_bot.constants import (
    N_RETRIES,
    RESY_BASE_URL,
    SECONDS_TO_WAIT_BETWEEN_RETRIES,
    ResyEndpoints,
)
from resy_bot.models import (
    BookRequestBody,
    BookResponseBody,
    DetailsRequestBody,
    DetailsResponseBody,
    FindResponseBody,
    PaymentMethod,
    ResyConfig,
    ReservationRequest,
    TimedReservationRequest,
    ReservationRetriesConfig,
)
from resy_bot.model_builders import (
    build_find_request_body,
    build_get_slot_details_body,
    build_book_request_body,
)
from resy_bot.api_access import ResyApiAccess
from resy_bot.selectors import AbstractSelector, SimpleSelector
from requests import HTTPError

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


class ResyManager:
    @classmethod
    def build(cls, config: ResyConfig) -> "ResyManager":
        api_access = ResyApiAccess.build(config)
        selector = SimpleSelector()
        retry_config = ReservationRetriesConfig(
            seconds_between_retries=SECONDS_TO_WAIT_BETWEEN_RETRIES,
            n_retries=N_RETRIES,
        )
        return cls(config, api_access, selector, retry_config)

    def __init__(
        self,
        config: ResyConfig,
        api_access: ResyApiAccess,
        slot_selector: AbstractSelector,
        retry_config: ReservationRetriesConfig,
    ):
        self.config = config
        self.api_access = api_access
        self.selector = slot_selector
        self.retry_config = retry_config

    def get_venue_id(self, address: str):
        """
        TODO: get venue id from string address
            will use geolocator to get lat/long
        :return:
        """
        pass

    def make_reservation(self, reservation_request: ReservationRequest) -> str:
        body = build_find_request_body(reservation_request)

        slots = self.api_access.find_booking_slots(body)
        logger.info(f"Returned: {slots}")

        if len(slots) == 0:
            raise NoSlotsError("No Slots Found")
        else:
            logger.info(len(slots))
            logger.info(slots)

        selected_slot = self.selector.select(slots, reservation_request)

        logger.info(selected_slot)
        details_request = build_get_slot_details_body(
            reservation_request, selected_slot
        )
        logger.info(details_request)
        token = self.api_access.get_booking_token(details_request)

        booking_request = build_book_request_body(token, self.config)

        resy_token = self.api_access.book_slot(booking_request)

        return resy_token

    def make_reservation_with_retries(
        self, reservation_request: ReservationRequest
    ) -> str:
        for _ in range(self.retry_config.n_retries):
            try:
                return self.make_reservation(reservation_request)

            except NoSlotsError:
                logger.info(
                    f"no slots, retrying; currently {datetime.now().isoformat()}"
                )

        raise ExhaustedRetriesError(
            f"Retried {self.retry_config.n_retries} times, " "without finding a slot"
        )

    def _get_drop_time(self, reservation_request: TimedReservationRequest) -> datetime:
        now = datetime.now()
        return datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=reservation_request.expected_drop_hour,
            minute=reservation_request.expected_drop_minute,
        )

    def make_reservation_at_opening_time(
        self, reservation_request: TimedReservationRequest
    ) -> str:
        """
        cycle until we hit the opening time, then run & return the reservation
        """
        drop_time = self._get_drop_time(reservation_request)
        last_check = datetime.now()

        while True:
            if datetime.now() < drop_time:
                if datetime.now() - last_check > timedelta(seconds=10):
                    logger.info(f"{datetime.now()}: still waiting")
                    last_check = datetime.now()
                continue

            logger.info(f"time reached, making a reservation now! {datetime.now()}")
            return self.make_reservation_with_retries(
                reservation_request.reservation_request
            )
        
    def make_reservation_at_opening_time_unrolled(
        self, reservation_request: TimedReservationRequest
    ) -> str:
        """
        cycle until we hit the opening time, then run & return the reservation
        this is an unrolled version of the above, optimized for maximum speed
        """
        drop_time = self._get_drop_time(reservation_request)
        last_check = datetime.now()
        res_req: ReservationRequest = reservation_request.reservation_request
        day = date.strftime(res_req.target_date, "%Y-%m-%d")
        find_request_body = build_find_request_body(res_req)
        find_request_params = find_request_body.dict()
        find_url = RESY_BASE_URL + ResyEndpoints.FIND.value
        details_url = RESY_BASE_URL + ResyEndpoints.DETAILS.value
        book_url = RESY_BASE_URL + ResyEndpoints.BOOK.value

        payment_method = PaymentMethod(id=self.config.payment_method_id)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://widgets.resy.com",
            "X-Origin": "https://widgets.resy.com",
            "Referrer": "https://widgets.resy.com/",
            "Cache-Control": "no-cache",
        }

        # Pre-build payment method string to avoid runtime overhead
        payment_method_str = payment_method.json().replace(" ", "")

        # PRE-WARM CONNECTION: Make a test request to warm up the connection
        # This eliminates the TCP handshake overhead for the critical first request
        try:
            logger.info("Pre-warming connection to Resy API...")
            # Use a lightweight endpoint or the same endpoint with a past date
            warmup_params = find_request_params.copy()
            warmup_params['day'] = '2020-01-01'  # Use past date that won't have slots
            warmup_resp = self.api_access.session.get(find_url, params=warmup_params, timeout=5)
            logger.info("Connection pre-warmed successfully")
        except Exception as e:
            logger.warning(f"Connection pre-warming failed: {e} - continuing anyway")

        while True:
            if datetime.now() < drop_time:
                if datetime.now() - last_check > timedelta(seconds=10):
                    logger.info(f"{datetime.now()}: still waiting")
                    last_check = datetime.now()
                continue
            
            # SINGLE ATTEMPT - NO RETRIES (if slots are gone, they're gone)
            try:
                logger.info(f"DROP TIME REACHED! Making reservation attempt at {datetime.now()}")
                start = time.time()
                
                # CRITICAL FIRST REQUEST - optimized for speed
                resp = self.api_access.session.get(find_url, params=find_request_params)
                
                # Fast JSON parsing without Pydantic validation during critical time
                resp_json = resp.json()
                slots = resp_json.get("results", {}).get("venues", [{}])[0].get("slots", [])
                
                if not slots:
                    logger.error("No slots found - reservation failed")
                    raise NoSlotsError("No slots available")

                # Take first available slot (fastest approach)
                selected_slot = slots[0]
                config_id = selected_slot["config"]["token"]

                # build get slot details body
                details_params = {
                    "config_id": config_id,
                    "day": day,
                    "party_size": res_req.party_size,
                }
                
                # get booking token
                resp = self.api_access.session.get(details_url, params=details_params)
                token_json = resp.json()
                book_token = token_json["book_token"]["value"]

                # build book request body
                body_dict = {
                    "book_token": book_token,
                    "struct_payment_method": payment_method_str,
                    "source_id": "resy.com-venue-details"
                }
                
                # book
                resp = self.api_access.session.post(
                    book_url,
                    data=body_dict,
                    headers=headers,
                )

                end = time.time()
                
                if not resp.ok:
                    logger.error(f"Booking failed: {resp.status_code}, {resp.text}")
                    raise HTTPError(f"Booking request failed: {resp.status_code}")

                resp_json = resp.json()
                resy_token = resp_json.get("resy_token")

                logger.info(f"Successfully booked! Slots found: {len(slots)}")
                logger.info(f"Selected slot: {selected_slot}")
                logger.info(f"Booking took {end - start:.3f} seconds")
                logger.info(f"Resy token: {resy_token}")

                return resy_token

            except Exception as e:
                logger.error(f"Reservation failed: {e}")
                raise e

    async def make_reservation_at_opening_time_async(
        self, reservation_request: TimedReservationRequest
    ) -> str:
        """
        Async version for even faster performance using aiohttp
        """
        drop_time = self._get_drop_time(reservation_request)
        last_check = datetime.now()
        res_req: ReservationRequest = reservation_request.reservation_request
        day = date.strftime(res_req.target_date, "%Y-%m-%d")
        find_request_body = build_find_request_body(res_req)
        find_request_params = find_request_body.dict()
        find_url = RESY_BASE_URL + ResyEndpoints.FIND.value
        details_url = RESY_BASE_URL + ResyEndpoints.DETAILS.value
        book_url = RESY_BASE_URL + ResyEndpoints.BOOK.value

        payment_method = PaymentMethod(id=self.config.payment_method_id)
        payment_method_str = payment_method.json().replace(" ", "")

        headers = {
            "Authorization": self.config.get_authorization(),
            "X-Resy-Auth-Token": self.config.token,
            "X-Resy-Universal-Auth": self.config.token,
            "Origin": "https://resy.com",
            "X-origin": "https://resy.com",
            "Referrer": "https://resy.com/",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Accept-Encoding": "gzip, deflate, br",
        }

        book_headers = {
            **headers,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://widgets.resy.com",
            "X-Origin": "https://widgets.resy.com",
            "Referrer": "https://widgets.resy.com/",
        }

        # PRE-WARM CONNECTION: Make a test request to warm up the connection for async
        try:
            logger.info("Pre-warming async connection to Resy API...")
            timeout = aiohttp.ClientTimeout(total=5, connect=2)
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=10,
                enable_cleanup_closed=True,
                use_dns_cache=True,
                ttl_dns_cache=300
            )
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers=headers
            ) as warmup_session:
                warmup_params = find_request_params.copy()
                warmup_params['day'] = '2020-01-01'  # Use past date that won't have slots
                async with warmup_session.get(find_url, params=warmup_params) as resp:
                    pass
            logger.info("Async connection pre-warmed successfully")
        except Exception as e:
            logger.warning(f"Async connection pre-warming failed: {e} - continuing anyway")

        # Use aiohttp for faster async requests
        timeout = aiohttp.ClientTimeout(total=10, connect=2)
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=10,
            enable_cleanup_closed=True,
            use_dns_cache=True,
            ttl_dns_cache=300
        )

        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=headers
        ) as session:

            # Wait for drop time
            while datetime.now() < drop_time:
                if datetime.now() - last_check > timedelta(seconds=10):
                    logger.info(f"{datetime.now()}: still waiting")
                    last_check = datetime.now()
                await asyncio.sleep(0.001)
            
            # SINGLE ATTEMPT - NO RETRIES (async version)
            try:
                # logger.info(f"DROP TIME REACHED! Making async reservation attempt at {datetime.now()}")
                # start = time.time()
                
                # CRITICAL FIRST REQUEST - optimized for speed
                async with session.get(find_url, params=find_request_params) as resp:
                    resp_json = await resp.json()
                    slots = resp_json["results"]["venues"][0]["slots"]
                
                # if not slots:
                #     logger.error("No slots found - async reservation failed")
                #     raise NoSlotsError("No slots available")

                # Take first available slot
                config_id = slots[0]["config"]["token"]

                # Get booking token
                details_params = {
                    "config_id": config_id,
                    "day": day,
                    "party_size": res_req.party_size,
                }
                
                async with session.get(details_url, params=details_params) as resp:
                    token_json = await resp.json()
                    book_token = token_json["book_token"]["value"]

                # Book the slot
                body_dict = {
                    "book_token": book_token,
                    "struct_payment_method": payment_method_str,
                    "source_id": "resy.com-venue-details"
                }
                
                async with session.post(
                    book_url,
                    data=body_dict,
                    headers=book_headers
                ) as resp:
                    # end = time.time()
                    
                    # if not resp.ok:
                    #     error_text = await resp.text()
                    #     logger.error(f"Booking failed: {resp.status}, {error_text}")
                    #     raise HTTPError(f"Async booking request failed: {resp.status}")

                    resp_json = await resp.json()
                    resy_token = resp_json.get("resy_token")

                    logger.info(f"Successfully booked! Slots found: {len(slots)}")
                    # logger.info(f"Selected slot: {selected_slot}")
                    # logger.info(f"Booking took {end - start:.3f} seconds")
                    logger.info(f"Resy token: {resy_token}")

                    return resy_token

            except Exception as e:
                logger.error(f"Async reservation failed: {e}")
                raise e