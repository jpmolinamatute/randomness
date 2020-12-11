#! /usr/bin/env python
from os import environ
import urllib
import uuid
import pkce
from dotenv import load_dotenv
from flask import Flask, request, render_template, url_for, session
from randomness import client_start


PORT_NUMBER = 5842
app = Flask(__name__)


@app.route("/")
@app.route("/home")
def home():
    verifier, challenge = pkce.generate_pkce_pair()
    state = str(uuid.uuid4())
    session["verifier"] = verifier
    session["challenge"] = challenge
    session["state"] = state
    params = {
        "response_type": "code",
        "code_challenge_method": "S256",
        "scope": "playlist-read-private,playlist-modify-private,user-library-read",
        "client_id": environ["SPOTIPY_CLIENT_ID"],
        "redirect_uri": f"http://{environ['SERVER_NAME']}:{PORT_NUMBER}/callback",
        "code_challenge": challenge,
        "state": state,
    }
    url_params = urllib.parse.urlencode(params)
    content = {
        "main_css": url_for("static", filename="main.css"),
        "template": "login.jinja",
        "url_params": url_params,
    }

    return render_template("layout.jinja", **content)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")
    content = {"main_css": url_for("static", filename="main.css"), "template": "run.jinja"}
    if error:
        content["template"] = "failed.jinja"
        content["reason"] = error
    elif code and state:
        try:
            if state == session["state"]:
                client_start(code, session["verifier"])
            else:
                msg = "ERROR: State doesn't macth "
                msg += f"we had '{session['state']}' "
                msg += f"and we got '{state}'"
                raise Exception(msg)
        except Exception as e:
            link = f"http://{environ['SERVER_NAME']}:{PORT_NUMBER}"
            content["template"] = "failed.jinja"
            content["reason"] = str(e)
            content["home_link"] = link

    return render_template("layout.jinja", **content)


def run():
    app.secret_key = environ["SPOTIPY_SECRET"]
    app.run(port=PORT_NUMBER, host=environ["SERVER_NAME"], debug=True)


if __name__ == "__main__":
    load_dotenv()
    run()
