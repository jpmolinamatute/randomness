#! /usr/bin/env python
import sys
from os import path
import urllib
import uuid
import logging
import pkce
from flask import Flask, request, render_template, url_for, session
from randomness.config import load_config
from randomness import (
    get_access_token,
    str_to_base64,
    save_access_token,
    generate_playlist,
)

# @TODO: Improve user expierence in html pages
# @TODO: improve error handling
# @TODO: update README.md file
# @TODO: create systemd service file


app = Flask(__name__)
ROOT_DIR = path.realpath(__file__)
ROOT_DIR = path.dirname(ROOT_DIR)


def process_callback(code: str, respose_state: str, session_state: str, verifier: str) -> dict:
    config = load_config(ROOT_DIR)
    server_name = config["server"]["hostname"]
    server_port = config["server"]["port"]
    uid = config["user"]["id"]
    content = {
        "main_css": url_for("static", filename="css/main.css"),
        "main_js": url_for("static", filename="js/main.js"),
    }
    try:
        if respose_state == session_state:
            client_id = config["credentials"]["spotipy_client_id"]
            client_secret = config["credentials"]["spotipy_client_secret"]
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
    except Exception as err:
        content["template"] = "failed.jinja"
        content["reason"] = str(err)
        content["home_link"] = f"http://{server_name}:{server_port}"
    return content


@app.route("/shutdown")
def shutdown():
    try:
        kill = request.environ.get("werkzeug.server.shutdown")
        kill()
        logging.info("server was successfuly killed")
    except Exception as err:
        logging.exception(err)
    finally:
        logging.info("Calling generate_playlist()")
        generate_playlist(ROOT_DIR)
    return "<p>Bye!</p>"


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
    config = load_config(ROOT_DIR)
    server_name = config["server"]["hostname"]
    server_port = config["server"]["port"]
    client_id = config["credentials"]["spotipy_client_id"]
    scope = "playlist-read-private,playlist-modify-private,user-library-read,user-library-modify"
    params = {
        "response_type": "code",
        "code_challenge_method": "S256",
        "scope": scope,
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


def launch_server(server_name: str, server_port: int, secret: str) -> None:
    app.secret_key = secret
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = 300
    app.run(port=server_port, host=server_name, debug=True)


def main() -> None:
    config = load_config(ROOT_DIR)
    db_file = config["database"]["filename"]
    db_path = path.join(ROOT_DIR, db_file)
    if path.isfile(db_path):
        generate_playlist(ROOT_DIR)
    else:
        server_name = config["server"]["hostname"]
        server_port = config["server"]["port"]
        secret = config["security"]["secret"]
        launch_server(server_name, server_port, secret)


if __name__ == "__main__":
    exit_status = 0
    logging.basicConfig(level=logging.INFO)
    logging.info("I just started")
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Bye!")
    except Exception as e:
        logging.exception(e)
        exit_status = 2
    finally:
        sys.exit(exit_status)
