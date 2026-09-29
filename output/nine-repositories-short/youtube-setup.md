# YouTube upload — blocked, with the exact prerequisite

**Status: not uploaded. No `youtube-upload.json` exists.** This is a missing-prerequisite blocker,
not a failed attempt. Every local deliverable in this folder is finished and verified, including the
private-upload metadata and the upload script that will run once the prerequisite exists.

## What is missing

A deliberately configured, user-authorized YouTube API connection for channel
`UCRig_f5P4QyB_kilUs2PN8Q` (JR DEV | SWIFT | FLUTTER) does not exist in this workspace. Checked on
28 September 2026:

| Check | Result |
| --- | --- |
| `google-api-python-client` in the project venv | **not installed** |
| `google-auth-oauthlib` in the project venv | **not installed** |
| OAuth client or token files anywhere in `jdh-shorts-studio` (`client_secret*.json`, `*oauth*.json`, `token*.json`, `*youtube*.json`) | none (the only match is this task's predecessor `output/heartwoodfall-first-short/youtube-published.json`, which is a manual-publication record, not credentials) |
| `~/.config`, `~/.youtube*`, `~/Library/Application Support/*youtube*` | none |
| Existing upload code in the repository | none; searching the tree for `videos.insert`/`resumable` finds only third-party library files |
| Keychain entries mentioning YouTube/Google | only **unrelated** entries belonging to IntelliJ Platform Google Login for a different app. They were not read, exported or used. |

Because there is no authorized connection, the private upload was **not attempted**. No OAuth scope
was requested, no credential store was touched, and no browser profile or session cookie was used to
work around it. The previous video on this channel was published by hand in YouTube Studio, so there
is no working API path to inherit.

## What to configure (one-time, by you, outside this folder)

1. In Google Cloud Console create (or select) a project and enable **YouTube Data API v3**.
2. Configure the OAuth consent screen. Add **only** this scope:
   `https://www.googleapis.com/auth/youtube.upload`. Do not add broader scopes such as
   `youtube` or `youtube.force-ssl` for this task.
3. Create an OAuth client of type **Desktop app** and download the JSON. Save it where the upload
   script can read it, for example
   `~/.config/jdh/youtube-client-secret.json` (a path outside this project is fine; do not paste the
   file contents into chat).
4. If the Google account that owns `UCRig_f5P4QyB_kilUs2PN8Q` is not the account you sign in with,
   sign in with the account that has channel access. The script verifies the target channel with
   `channels.list(mine=true)` and aborts if the returned id is not `UCRig_f5P4QyB_kilUs2PN8Q`.
5. Install the client libraries in the project environment (this is a new dependency, so it is
   deliberately not done for you):

   ```sh
   cd /Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio
   uv pip install --python .venv/bin/python google-api-python-client google-auth-oauthlib
   ```

6. Run the prepared script once. It performs a resumable upload and writes the evidence file:

   ```sh
   cd /Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio/output/nine-repositories-short
   ../../.venv/bin/python upload_youtube.py --client-secret ~/.config/jdh/youtube-client-secret.json
   ```

   The script opens a browser once for consent, stores the token next to the client secret
   (mode 600), verifies the channel, uploads `final.mp4` with `privacyStatus=private`, and writes
   `youtube-upload.json` with the channel id, the **video id**, the URL, the observed privacy state
   and the processing state. Re-running it reuses the recorded video id instead of uploading a
   second copy.

## Facts that affect this upload

- **Private only.** Google's own documentation states that videos uploaded through `videos.insert`
  from unverified API projects created after 28 July 2020 are restricted to private viewing. This
  test asks for private only, so that restriction is acceptable and no audit is requested.
- **Synthetic-content disclosure.** The video resource has a
  `status.containsSyntheticMedia` boolean, settable in `videos.insert`/`videos.update`
  (YouTube Data API v3, *Videos*, checked 28 September 2026). The script sets it to `true`, because
  the narration is synthetic speech and parts of the visuals are altered article imagery.
  `selfDeclaredMadeForKids` is set to `false`.
- **Language and category.** `snippet.defaultLanguage` and `snippet.defaultAudioLanguage` are `en`;
  `snippet.categoryId` is `28` (Science & Technology).
- **No verification evidence yet.** Nothing here claims a successful upload; that would require the
  API's own video id plus processing/visibility state, which is what the script records.

## If you prefer to skip the API entirely

The render already produced a manual handoff package at `final/upload.zip`
(`final.mp4`, `captions.srt`, `upload-metadata.json`, `quality-report.json`, `upload-notes.txt`).
Uploading that by hand in YouTube Studio, setting **Private** and ticking the altered-or-synthetic
content question, produces the same private test result without any OAuth setup.
