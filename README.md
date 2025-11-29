# Random of Randomness

Welcome! This is a personal project to create and update a playlist with random songs on Spotify on every run.

## Why This App?

1. I don't like how Spotify "randomize" my music.
2. My liked playlist occupies more storage than my phone can handle, so I couldn't download the whole playlist.
3. If I wanted to download a playlist with random songs, I would need to create/update it manually to get new songs on my phone.

## Pre-requisites

1. Docker 27.3.1+
2. Docker Compose 2.32.0+
3. Python 3.14+
4. uv (>=0.7.17) - ultra-fast Python package and environment manager ([docs](https://docs.astral.sh/uv/))
5. A `.env` file at the project root with these variables:
   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_PLAYLIST_ID`: A playlist ID that the app can use. [Instructions](https://clients.caster.fm/knowledgebase/110/How-to-find-Spotify-playlist-ID.html#:~:text=To%20find%20the%20Spotify%20playlist,Link%22%20under%20the%20Share%20menu.&text=The%20playlist%20id%20is%20the,after%20playlist/%20as%20marked%20above.)
   - `SPOTIFY_STATE`: A random URL-safe string. You can generate one with:

   ```sh
   . ./.venv/bin/activate
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   - `MONGO_INITDB_ROOT_USERNAME`: Username to be used by MongoDB and by the app
   - `MONGO_INITDB_ROOT_PASSWORD`: Password to be used by MongoDB and by the app
   - `MONGO_INITDB_DATABASE`: Database to be used by MongoDB and by the app

To create a Spotify client ID and client secret, follow [this tutorial](https://developer.spotify.com/documentation/web-api/concepts/apps). When creating the Spotify app, set `http://localhost:5000/callback` as the redirect URI.

Example `.env`:

```dotenv
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_PLAYLIST_ID=your_playlist_id
SPOTIFY_STATE=generated_random_state
MONGO_INITDB_ROOT_USERNAME=spotify
MONGO_INITDB_ROOT_PASSWORD=supersecret
MONGO_INITDB_DATABASE=randomness
```

## Start MongoDB with Docker Compose

This project uses MongoDB. Bring it up/down with Docker Compose using the provided file.

Start MongoDB (detached):

```sh
docker compose -f docker/docker-compose.yaml up -d
```

Stop MongoDB and remove containers:

```sh
docker compose -f docker/docker-compose.yaml down
```

## Install and Run with uv

1. Install project dependencies and create a local virtualenv (managed by uv):

   ```sh
   uv sync
   ```

2. Run the app using the managed environment:

   ```sh
   . ./.venv/bin/activate
   ./main.py
   ```

   You can also pass flags, for example:

   ```sh
   . ./.venv/bin/activate
   ./main.py --update-cache
   ```

## About `--update-cache`

The `--update-cache` flag forces a refresh of your Liked Songs cache from the Spotify API before generating the playlist. If you omit it, the app will use the existing cache stored in MongoDB; if the cache is empty, it will update automatically.

## About `--export`

The `--export` flag allows you to export your cached Liked Songs to a JSON file. This is useful for backing up your data or inspecting the contents of your local cache. When this flag is used, the app will perform the export and then exit without generating a playlist.

## About `--get-all-playlists`

The `--get-all-playlists` flag fetches and lists all your Spotify playlists. This can be helpful if you need to find the ID of a specific playlist to use in your `.env` file. Like the export flag, the app will exit after completing this action.

## Development & Quality Assurance

To ensure code quality, this project includes a linter script located at `scripts/linter.bash`. This script runs the following tools:

- **isort**: Sorts imports.
- **black**: Formats code.
- **mypy**: Performs static type checking.
- **pylint**: Analyzes code for errors and quality.
- **pytest**: Runs the test suite.

### Setting up the pre-commit Hook

It is recommended to set up this script as a Git pre-commit hook. This ensures that all checks pass before you can commit any changes.

To set up the hook, run the following command from the project root:

```sh
ln -sfr ./scripts/linter.bash ./.git/hooks/pre-commit
```

Now, whenever you run `git commit`, the linter script will execute automatically. If any check fails, the commit will be aborted, allowing you to fix the issues.

## Enjoy
