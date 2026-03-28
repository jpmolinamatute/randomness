# Spotify Randomness Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Ensure true randomness in Spotify playlist generation by adopting a Least-Recently-Played tracking approach embedded within the local `tracks` database, merged seamlessly with Spotify's live library via bulk upsert routines.

**Architecture:** We will maintain the single MongoDB `tracks` collection. Every track gets a new field, `played_at`, which defaults to `None`. During playlist generation, we sort ascending by `played_at`, limit to an older subset (e.g., 300 tracks), sample exactly 100 randomly, and update those 100 tracks with the current timestamp. The `--update-cache` operation will be rewritten to use a MongoDB Bulk `UpdateOne` operation with `upsert=True` + `$setOnInsert: {played_at: null}` to preserve play history while deleting tracks the user un-liked on Spotify.

**Tech Stack:** Python, MongoDB (pymongo), httpx

---

### Task 1: Update MongoDB Client Logic for Upserting Tracks

**Files:**
- Modify: `spotify/db.py`

**Step 1: Write minimal implementation for `sync_tracks`**

We will replace the simplistic `insert_tracks` dropping behavior with a solid `sync_tracks` method that handles upsert logic and prunes orphaned songs from Spotify right inside `spotify/db.py`. 

```python
    from pymongo import UpdateOne

    def sync_tracks(self, tracks: list[dict[str, Any]]) -> None:
        
        self.logger.debug("Syncing tracks to MongoDB: sum=%d", len(tracks))

        existing_uris_cursor = self.get_tracks_coll().find({}, {"uri": 1})
        existing_uris = {doc.get("uri") for doc in existing_uris_cursor if doc.get("uri")}
        incoming_uris = {t.get("uri") for t in tracks if t.get("uri")}

        uris_to_delete = existing_uris - incoming_uris
        if uris_to_delete:
            self.logger.info("Deleting %d missing tracks from DB", len(uris_to_delete))
            self.get_tracks_coll().delete_many({"uri": {"$in": list(uris_to_delete)}})

        operations = []
        for t in tracks:
            # Upsert track metadata, preserve or initialize played_at
            update_doc = {
                "$set": t,
                "$setOnInsert": {"played_at": None}
            }
            operations.append(UpdateOne({"uri": t["uri"]}, update_doc, upsert=True))

        if operations:
            self.get_tracks_coll().bulk_write(operations)
            self.logger.info("Upserted %d tracks into DB", len(operations))
```

**Step 2: Remove `reset_collection` branch for `tracks`**

Modify `reset_collection` in `spotify/db.py` to prevent wiping `tracks`.

```python
    def reset_collection(self, collection_name: str) -> None:
        self.logger.debug("Resetting collection: %s", collection_name)
        if collection_name == self.tracks_coll_name:
            self.logger.warning("tracks collection is no longer reset; use sync_tracks instead")
        elif collection_name == self.playlist_coll_name:
            self.get_playlist_coll().delete_many({})
        else:
            raise ValueError("Invalid collection name")
```

---

### Task 2: Adapt Spotify Client fetching

**Files:**
- Modify: `spotify/client.py`

**Step 1: Accumulate tracks instead of batch-inserting**

Currently `get_all_liked_tracks` inserts batches dynamically. We need to accumulate them to execute a sync against the entire collection at once.

Modify `get_all_liked_tracks` in `spotify/client.py`:
```python
    async def get_all_liked_tracks(self) -> None:
        self.logger.debug("Starting retrieval of all liked tracks")
        self.logger.info("Getting all liked tracks")
        url = f"{self.api_url}/me/tracks?offset=0&limit={self.ME_BATCH_SIZE}"

        all_tracks = []

        async with httpx.AsyncClient() as client:
            first_batch = await self.fetch_tracks_batch(client, url, "liked")
            all_tracks.extend([item.track.model_dump(by_alias=True) for item in first_batch.items])

            total = first_batch.total
            self.logger.info("Total liked tracks to fetch: %d", total)

            sem = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
            tasks = []
            for offset in range(self.ME_BATCH_SIZE, total, self.ME_BATCH_SIZE):
                next_url = f"{self.api_url}/me/tracks?offset={offset}&limit={self.ME_BATCH_SIZE}"
                tasks.append(self.fetch_with_sem(client, sem, next_url))

            if tasks:
                responses = await asyncio.gather(*tasks)
                for response_data in responses:
                    all_tracks.extend([item.track.model_dump(by_alias=True) for item in response_data.items])

        # Do a single sync at the end
        self.db.sync_tracks(all_tracks)
        self.logger.debug("Completed retrieval of liked tracks")
```

Also remove `insert_tracks_to_db` from `spotify/client.py` entirely, since we now directly use `sync_tracks`.

---

### Task 3: Implement "Oldest Window" Sampling logic

**Files:**
- Modify: `spotify/db.py`

**Step 1: Write new logic for `generate_random_tracks` and `generate_random_artists`**

In `spotify/db.py`, completely redefine `generate_random_tracks` to use the new randomized `played_at` pipeline.

```python
    MAX_SIZE_WINDOW = 300
    RATIO_WINDOW = 3
    
    def generate_random_tracks(self, no_items: int) -> None:
        self.logger.debug("Building random track pipeline: no_items=%d", no_items)
        self.logger.info("Generating a playlist with %d items using Least-Recently-Played logic", no_items)
        
        # 1. Pipeline: Sort by played_at ASC, grab the oldest window of tracks, shuffle them
        window_size = max(no_items * RATIO_WINDOW, MAX_SIZE_WINDOW) # Ensure a decent chunk
        pipeline = [
            {"$sort": {"played_at": 1}},
            {"$limit": window_size},
            {"$sample": {"size": no_items}},
            {
                "$group": {
                    "_id": ObjectId(),
                    "tracks": {"$push": "$$ROOT"},
                    "created_at": {"$first": datetime.now(UTC)},
                }
            },
            {
                "$merge": {
                    "into": self.playlist_coll_name,
                    "whenMatched": "keepExisting",
                    "whenNotMatched": "insert",
                }
            },
        ]

        cursor = self.get_tracks_coll().aggregate(pipeline)
        cursor.close()

        # 2. Extract which tracks were actually chosen to update their played_at
        latest_uris = self.get_latest_playlist_uris()
        
        # 3. Mark them as played
        if latest_uris:
            self.get_tracks_coll().update_many(
                {"uri": {"$in": latest_uris}},
                {"$set": {"played_at": datetime.now(UTC)}}
            )
            self.logger.debug("Marked %d tracks as played", len(latest_uris))
```

Update `generate_random_artists` to use the same logic, but with an extra match stage at the beginning to isolate the chosen artists.

```python
    MAX_SIZE_WINDOW = 300
    RATIO_WINDOW = 3

    def generate_random_artists(self, no_items: int) -> None:
        self.logger.debug("Selecting random artists to build playlist: no_items=%d", no_items)
        all_artists = self.get_artist_ids()
        some_artists = self._randomize(all_artists)
        
        window_size = max(no_items * RATIO_WINDOW, MAX_SIZE_WINDOW)
        pipeline = [
            {"$match": {"artists._id": {"$in": some_artists}}},
            {"$sort": {"played_at": 1}},
            {"$limit": window_size},
            {"$sample": {"size": no_items}},
            {
                "$group": {
                    "_id": ObjectId(),
                    "tracks": {"$push": "$$ROOT"},
                    "created_at": {"$first": datetime.now(UTC)},
                }
            },
            {
                "$merge": {
                    "into": self.playlist_coll_name,
                    "whenMatched": "keepExisting",
                    "whenNotMatched": "insert",
                }
            },
        ]

        cursor = self.get_tracks_coll().aggregate(pipeline)
        cursor.close()

        latest_uris = self.get_latest_playlist_uris()
        if latest_uris:
            self.get_tracks_coll().update_many(
                {"uri": {"$in": latest_uris}},
                {"$set": {"played_at": datetime.now(UTC)}}
            )
```

**Step 2: Remove `get_recent_playlist_uris`**

Since we no longer statically exclude the last 3 playlists based on URI loops, we should delete the `get_recent_playlist_uris` function to keep the DB class clean.

---

### Task 4: Fix Main Pipeline and Tests
**Files:**
- Modify: `main.py`
- Test: `tests/` with Pytest

**Step 1:`main.py` cache logic verification**
No changes strictly required for `--update-cache` logic in `main.py` since we changed `get_all_liked_tracks()` to inherently do the bulk upsert sync instead of `insert_tracks` append mode. We should ensure the `reset_collection` branch no longer causes issues.

**Step 2: Run all backend tests**

run ruff with `uv run ruff check --fix`, run ty with `uv run ty check`and finaly We will execute tests using `uv run pytest -vv` and ensure everything passes smoothly.
