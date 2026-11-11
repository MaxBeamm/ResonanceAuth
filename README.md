# ResonanceAuth — Windows desktop prototype

This is an initial educational implementation of the audio authentication pipeline. It is **not** production-ready and does not prove artist identity.

## Requirements
- Windows 10/11
- Python 3.11 or 3.12 (64-bit)

## Setup (PowerShell)
```powershell
cd ResonanceAuthStarter
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```
If Python 3.12 is unavailable, replace `py -3.12` with `python` after checking `python --version`.

## Try it
1. Select an original WAV file at least 5 seconds long, enter a title, and click **Register and sign recording**.
2. Choose the registered song, select the same WAV file under **Recording to check**, and click **Verify selected recording**.
3. Try a converted MP3 and inspect the segment scores. Try an edited version too.

References are stored in `%USERPROFILE%\.resonanceauth\references.sqlite3`.

## Security and correctness limitations
- **Local-only**: database fingerprints are not encrypted or remotely stored. This is an intermediate milestone before a private backend.
- **Artist identity is NOT authenticated**: the demo creates a new Ed25519 key per registration and stores its public key with the reference. An attacker who controls the database can replace both. The next milestone is independent artist-controlled keys and a trusted key registry.
- Fingerprint processing settings are covered by the signature, but song titles are not. Do not treat displayed titles as authenticated artist claims.
- Signature validation detects accidental or isolated tampering with stored fingerprint data, not a fully compromised local computer.
- Segment comparison is aligned from time zero. Insertions and deletions can shift alignment.
- The threshold 0.90 is illustrative and must be experimentally calibrated. Averaged chroma/MFCC vectors are not collision-resistant.
- The implementation ignores trailing audio shorter than five seconds; future versions should define explicit padding/length rules.
- Audio decoding depends on installed codecs. Start with WAV files.
- Audio files are processed locally; no data is uploaded.

## Next milestones
1. Separate artist signing from verification; pin trusted artist public keys.
2. Introduce a private FastAPI backend and move the SQLite fingerprint database there.
3. Have the desktop client upload audio securely for server-side matching and receive only results.
4. Add artist login, authorization, request limits, and safe upload handling before public deployment.
5. Calibrate thresholds and measure false positives, false negatives, and edit localization.
