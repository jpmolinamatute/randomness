# Random of Randomness

Welcome! This is a personal project to create and update a playlist with random songs on Spotify on every run.

## Why This App?

1. I don't like how Spotify "randomize" my music.
2. My liked playlist occupies more storage than my phone can handle, so I couldn't download the whole playlist.
3. If I wanted to download a playlist with random songs, I would need to create/update it manually to get new songs on my phone.

## Pre-requisites

1. Docker 27.3.1+
2. Docker Compose 2.32.0+
3. [Python](./.python-version)
4. Poetry 1.8.5+
5. Create a `.env` file with the following variables:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_PLAYLIST_ID`: A playlist ID that the app can use. [Instructions](https://clients.caster.fm/knowledgebase/110/How-to-find-Spotify-playlist-ID.html#:~:text=To%20find%20the%20Spotify%20playlist,Link%22%20under%20the%20Share%20menu.&text=The%20playlist%20id%20is%20the,after%20playlist/%20as%20marked%20above.)
   - `SPOTIFY_STATE`: A random string
   - `MONGO_INITDB_ROOT_USERNAME`: Username to be used by MongoDB and by the app
   - `MONGO_INITDB_ROOT_PASSWORD`: Password to be used by MongoDB and by the app
   - `MONGO_INITDB_DATABASE`: Database to be used by MongoDB and by the app

To create a Spotify client ID and a client secret, follow [this tutorial](https://developer.spotify.com/documentation/web-api/concepts/apps). When creating the Spotify app, please set `<http://localhost:5000/callback>` as the redirect link.

## How to Run This App

1. Install Python dependencies:

   ```sh
   poetry install
   ```

2. Run the app:

   ```sh
   poetry run invoke app.run
   
   # or
   
   poetry shell
   invoke app.run
   ```

3. Enjoy!
