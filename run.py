#! /usr/bin/env python
import sys
from os import path
import urllib
import uuid
import logging
import pkce
from flask import Flask, request, render_template, url_for, session
from randomness import (
    get_access_token,
    str_to_base64,
    save_access_token,
    DEFAULT_SETTINGS,
    DEFAULT_DB,
    generate_playlist,
    create_settings,
    validate_settings,
    load_settings,
)

# @TODO: validate settings
# @TODO: Improve user expierence in html pages
# @TODO: update README.md file
# @TODO: create systemd service file
# @TODO: improve error handling


app = Flask(__name__)
ROOT_DIR = path.realpath(__file__)
ROOT_DIR = path.dirname(ROOT_DIR)


def process_callback(code: str, respose_state: str, session_state: str, verifier: str) -> dict:
    settings = load_settings(ROOT_DIR)
    server_name = settings["server"]["hostname"]
    server_port = settings["server"]["port"]
    uid = settings["user"]["id"]
    content = {
        "main_css": url_for("static", filename="css/main.css"),
        "main_js": url_for("static", filename="js/main.js"),
    }
    try:
        if respose_state == session_state:
            client_id = settings["credentials"]["spotipy_client_id"]
            client_secret = settings["credentials"]["spotipy_client_secret"]
            response = get_access_token(
                code,
                verifier,
                f"http://{server_name}:{server_port}/callback",
                str_to_base64(f"{client_id}:{client_secret}"),
            )
            save_access_token(response, ROOT_DIR, uid)
            content["onload"] = "closeWindow();"
            content["template"] = "run.jinja"
        else:
            msg = "ERROR: State doesn't macth "
            msg += f"we had '{session_state}' "
            msg += f"and we got '{respose_state}'"
            raise Exception(msg)
    except Exception as e:
        content["template"] = "failed.jinja"
        content["reason"] = str(e)
        content["home_link"] = f"http://{server_name}:{server_port}"
    return content


@app.route("/shutdown")
def shutdown():
    try:
        kill = request.environ.get("werkzeug.server.shutdown")
        kill()
        logging.info("server was successfuly killed")
    except Exception as e:
        logging.exception(e)
    finally:
        logging.info("Calling generate_playlist()")
        generate_playlist(ROOT_DIR)
    return "Bye!"


@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        content = {
            "main_css": url_for("static", filename="css/main.css"),
            "main_js": url_for("static", filename="js/main.js"),
            "template": "failed.jinja",
            "reason": error,
        }
    elif code and state:
        if "state" not in session:
            raise Exception("state is not found in session")
        if "verifier" not in session:
            raise Exception("verifier is not found in session")

        content = process_callback(code, state, session["state"], session["verifier"])
    return render_template("layout.jinja", **content)


@app.route("/")
@app.route("/home")
def home():
    verifier, challenge = pkce.generate_pkce_pair()
    state = str(uuid.uuid4())
    session["verifier"] = verifier
    session["challenge"] = challenge
    session["state"] = state
    settings = load_settings(ROOT_DIR)
    server_name = settings["server"]["hostname"]
    server_port = settings["server"]["port"]
    client_id = settings["credentials"]["spotipy_client_id"]
    params = {
        "response_type": "code",
        "code_challenge_method": "S256",
        "scope": "playlist-read-private,playlist-modify-private,user-library-read",
        "client_id": client_id,
        "redirect_uri": f"http://{server_name}:{server_port}/callback",
        "code_challenge": challenge,
        "state": state,
    }
    url_params = urllib.parse.urlencode(params)
    content = {
        "main_css": url_for("static", filename="css/main.css"),
        "template": "login.jinja",
        "url_params": url_params,
        "login_logo": url_for("static", filename="img/logo.png"),
    }

    return render_template("layout.jinja", **content)


def launch_server(server_name: str, server_port: int, secret: str):
    app.secret_key = secret
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 300
    app.run(port=server_port, host=server_name, debug=True)


def start():
    db_path = path.join(ROOT_DIR, DEFAULT_DB)
    settings_path = path.join(ROOT_DIR, DEFAULT_SETTINGS)
    if path.isfile(settings_path):
        if validate_settings(ROOT_DIR):
            settings = load_settings(ROOT_DIR)
            if path.isfile(db_path):
                generate_playlist(ROOT_DIR)
            else:
                server_name = settings["server"]["hostname"]
                server_port = settings["server"]["port"]
                secret = settings["security"]["secret"]
                launch_server(server_name, server_port, secret)
        else:
            raise Exception(f"setting file '{settings_path}' is invalid")
    else:
        create_settings(ROOT_DIR)
        raise Exception(f"setting file '{settings_path}' doesn't exist")


if __name__ == "__main__":
    exit_status = 0
    logging.basicConfig(level=logging.INFO)
    logging.info("I just started")
    try:
        start()
    except KeyboardInterrupt:
        logging.info("Bye!")
    except Exception as e:
        logging.exception(e)
        exit_status = 2
    finally:
        sys.exit(exit_status)
