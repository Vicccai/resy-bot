from enum import Enum


RESY_BASE_URL = "https://api.resy.com"
N_RETRIES = 30  # Increased from 30 for more attempts
SECONDS_TO_WAIT_BETWEEN_RETRIES = 0.05  # Reduced from 0.05 for faster retries


class ResyEndpoints(Enum):
    FIND = "/4/find"
    DETAILS = "/3/details"
    BOOK = "/3/book"
    PASSWORD_AUTH = "/3/auth/password"
