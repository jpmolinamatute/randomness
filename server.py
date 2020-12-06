#! /usr/bin/env python
from os import environ
import urllib
from dotenv import load_dotenv
from flask import Flask, request, render_template, url_for, session
from requests.exceptions import HTTPError
from randomness.oauth import OAuth
from randomness.client import get_access_token


PORT_NUMBER = 5842
app = Flask(__name__)
app.secret_key = "-9GntT4cV/JigA%9S8ldK<xwoi2-{|/yZ2Z;4:"


@app.route("/")
@app.route("/home")
def home():
    db = OAuth()
    new_pkce = db.create_pkce()
    myid = db.get_id()
    session["oauth_id"] = myid

    params = {
        "response_type": "code",
        "code_challenge_method": "S256",
        "scope": "playlist-read-private,playlist-modify-private,user-library-read",
        "client_id": environ["SPOTIPY_CLIENT_ID"],
        "redirect_uri": f"http://{environ['SERVER_NAME']}:{PORT_NUMBER}/callback",
        "code_challenge": new_pkce["challenge"],
        "state": new_pkce["state"],
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
    elif code:
        try:
            get_access_token(session["oauth_id"], state, code)
        except HTTPError as e:
            link = f"http://{environ['SERVER_NAME']}:{PORT_NUMBER}"
            content["template"] = "failed.jinja"
            content["reason"] = str(e)
            content["link"] = link
        except Exception as e:
            content["template"] = "failed.jinja"
            content["reason"] = str(e)

    return render_template("layout.jinja", **content)


def run():
    app.run(port=PORT_NUMBER, host=environ["SERVER_NAME"], debug=True)


if __name__ == "__main__":
    load_dotenv()
    run()
