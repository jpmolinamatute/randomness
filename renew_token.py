#! /usr/bin/env python
import sys
from os import environ
import time
import logging
import requests
from dotenv import load_dotenv
from randomness import str_to_base64, TOKEN_URL, OAuth


def get_session():
    cred = f"{environ['SPOTIPY_CLIENT_ID']}:{environ['SPOTIPY_CLIENT_SECRET']}"
    cred_encoded = str_to_base64(cred)
    session = requests.Session()
    session.headers.update(
        {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {cred_encoded}",
        }
    )
    return session


def renew_access_token(uri: str, session, logger):
    db = OAuth(uri)
    expires = db.get_field("expires_in")
    while True:
        logger.info("Getting new access_token")
        refresh = db.get_field("refresh_token")
        data = {"grant_type": "refresh_token", "refresh_token": refresh}
        response = session.post(TOKEN_URL, data=data)
        response.raise_for_status()
        respose_dict = response.json()
        if "access_token" in respose_dict and "refresh_token" in respose_dict:
            db.update_access_token(respose_dict["access_token"], respose_dict["refresh_token"])
        else:
            raise Exception(
                "Error: we couldn't get either access_token or refresh_token from call to spotify"
            )
        time.sleep(expires - 5)


def main():
    logger = logging.getLogger("renew_access_token")
    logger.setLevel(logging.DEBUG)

    try:
        logger.info("Service just started")
        uri = environ["SPOTIPY_USER"]
        session = get_session()
        renew_access_token(uri, session, logger)
    except requests.HTTPError as e:
        logger.exception(e)
        sys.exit(2)
    except KeyboardInterrupt:
        logger.info("Bye!")
        sys.exit(0)


if __name__ == "__main__":
    load_dotenv()
    main()
