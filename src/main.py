#! /usr/bin/env python
import sys

from src.auth import SpotifyAuth
from src.client import SpotifyClient
from src.randomness import Randomness


def main() -> None:
    sp_auth = SpotifyAuth()
    sp_client = SpotifyClient(sp_auth)
    randomness = Randomness()
    # sp_client.get_all_liked_tracks()
    randomness.get_random_item("track", 300)
    # print(randomness.get_random_item("artist", 5))
    sp_client.delete_playlist_content()
    sp_client.generate_content()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    else:
        sys.exit(0)
