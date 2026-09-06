"""Google Flights adapter package (the only enabled source in v1)."""

from .adapter import GoogleFlightsAdapter
from .tfs import TFU, build_search_url, decode_tfs, encode_tfs

__all__ = ["TFU", "GoogleFlightsAdapter", "build_search_url", "decode_tfs", "encode_tfs"]
