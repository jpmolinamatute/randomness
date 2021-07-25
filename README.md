# Random of Randomness #

Welcome! this is a personal project to create & update a playlist with random songs on Spotify.

I had two reasons to create this app:

1. My liked playlist occupies way more than the storage capacity in my phone. So I couldn't download it.
2. If I wanted to download a playlist with random songs I would need to update it manually in order to get new songs on my phone.

This App uses OAuth to authenticate a user against the Spotify server and then uses REST API calls to create & update a specific playlist with random songs. Every time the app is run, a new set of songs replace all previous songs in that specific playlist.

In order to use this app, you also need Spotify developer access keys.
This app was written using Python 3.0 and tested in Linux.
If you have any questions, please open a ticket in the issues sections.

## How to run this app ##

1. Clone this repo:

    ```sh
    git clone git@github.com:jpmolinamatute/randomness.git
    ```

2. Change directory to the new repo:

    ```sh
    cd randomness
    ```

3. Create a new virtual environment:

    ```sh
    python -m venv ./.venv # Assuming 'python' is your python binary
    ```

4. Activate the virtual environment:

    ```sh
    . ./.venv/bin/activate
    ```

5. Install python packages:

    ```sh
    pip install -r ./requirements.txt
    ```

6. Run the script:

    ```sh
    ./run.py # if this is your first time running the app,
             # it will fail (this is kind of OK), please notice a new config file was created
             # please change the values and try again.
    ```

7. Enjoy!

## How to improve randomness ##

Over time I noticed my playlist wasn't as random as I would like it to be. This happens because on one hand, I have artists with one or few songs and on the other hand I have artists with too many songs. Even though I was running a random() function, artists with a higher number of songs had higher chances to get picked. This is where the “generator” key comes to play. The idea is to create mini-groups and then run the random() function in those mini-groups to level chances among artists and then create a better random playlist.

The default value for the generator key is:

```yaml
playlist:
  size: 100
generator:
    order: 0,
    min_mark: 1,
    weight: 1.0
```

This means that the code is going to create one mini-group and is going to take 100% of the songs from it.

Since we may have many mini-groups we need to keep a sequence with an “order” key. With also need some limits  "min_mark" & "max_mark" (this is optional, if omitted it will take the max value available). This limit represents the number of songs per artist. The "weight" key is the percentage we are going to pick from this given mini-group. **NOTE**: all weight from all mini-groups must add up to 1.0.

This is my config file as an example:

```yaml
playlist:
  size: 1000
generator:
  - order: 0
    min_mark: 1
    max_mark: 4
    weight: 0.3
  - order: 1
    min_mark: 4
    max_mark: 11
    weight: 0.3
  - order: 2
    min_mark: 11
    max_mark: 24
    weight: 0.25
  - order: 3
    min_mark: 24
    weight: 0.15
```
