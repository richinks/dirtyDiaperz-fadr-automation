# Dirty Diaperz Automation - Fadr Integration Patch

Uses a lawful local audio file. Spotify links are identifiers/metadata only and are not used as audio sources.

## Fadr workflow
The client requests a presigned upload URL, uploads the source file, creates/uses an asset, creates a stem task, polls task status, and downloads returned stem/MIDI assets. Fadr documents this overall workflow and the five primary stem outputs.

## Setup
1. Copy `.env.example` to your preferred environment configuration and set `FADR_API_KEY`.
2. Verify the endpoint paths against the endpoint page for your Fadr account/API version. They are environment-configurable because the public tutorial describes endpoint operations but may not expose every current path in searchable documentation.
3. Install Python dependencies: `python -m pip install -r requirements.txt`.
4. Run:

   `python scripts/dirty_diaperz_fadr.py --source "incoming/song.wav" --title "Song" --out "reaper-projects/Song"`

Or on Windows:

   `run_dirty_diaperz.cmd "incoming\song.wav" "Song" "reaper-projects\Song"`

## Outputs
- ORIGINAL
- VOCALS
- DRUMS
- BASS
- MELODIES
- INSTRUMENTAL
- CLICK
- CUES
- `.RPP`
- `automation-result.json`
- optional `x32-scene-requirements.json`

## Server/PWA
Run `python automation/reaper_server.py`. The SvelteKit routes use `+server.js`, input validation, structured errors, timeouts, and retry handling. Long-running song processing is not automatically retried because repeating an upload/task can create duplicate Fadr work.
