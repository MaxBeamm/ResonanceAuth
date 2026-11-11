"""ResonanceAuth educational prototype. Not a production authentication service."""
import hashlib
import json
import sqlite3
from pathlib import Path

import librosa
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

RATE = 22050
SEGMENT_SECONDS = 5
FEATURE_VERSION = 'chroma12-mfcc13-mean-v1'


def fingerprints(path):
    audio, _ = librosa.load(str(path), sr=RATE, mono=True)
    length = RATE * SEGMENT_SECONDS
    if len(audio) < length:
        raise ValueError('Audio must be at least 5 seconds long.')
    # Normalize once per recording; handle silence safely.
    peak = np.max(np.abs(audio))
    if peak > 1e-9:
        audio = audio / peak
    out = []
    for offset in range(0, len(audio) - length + 1, length):
        clip = audio[offset:offset + length]
        chroma = librosa.feature.chroma_stft(y=clip, sr=RATE).mean(axis=1)
        mfcc = librosa.feature.mfcc(y=clip, sr=RATE, n_mfcc=13).mean(axis=1)
        v = np.concatenate([chroma, mfcc]).astype(np.float64)
        out.append([float(x) for x in np.round(v, 6)])
    return out


def encode_vector(vector):
    return json.dumps(vector, separators=(',', ':'), allow_nan=False).encode('utf-8')


def merkle_root(vectors):
    if not vectors:
        raise ValueError('No fingerprints to authenticate')
    layer = [hashlib.sha256(b'\x00' + encode_vector(v)).digest() for v in vectors]
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [hashlib.sha256(b'\x01' + layer[i] + layer[i+1]).digest()
                 for i in range(0, len(layer), 2)]
    return layer[0]


def signed_message(root, settings):
    return b'ResonanceAuth-v1\x00' + root + b'\x00' + json.dumps(
        settings, sort_keys=True, separators=(',', ':')).encode('utf-8')


def settings():
    return {'sample_rate': RATE, 'segment_seconds': SEGMENT_SECONDS,
            'feature_version': FEATURE_VERSION}


def init_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            fingerprints TEXT NOT NULL, settings TEXT NOT NULL,
            signature BLOB NOT NULL, public_key BLOB NOT NULL)''')


def register(db_path, title, audio_path):
    if not title.strip():
        raise ValueError('Please enter a title.')
    vectors = fingerprints(audio_path)
    root = merkle_root(vectors)
    config = settings()
    # DEMO ONLY: key generated per registration. Real artists must manage keys
    # independently, and public keys must be authenticated out of band.
    private_key = Ed25519PrivateKey.generate()
    signature = private_key.sign(signed_message(root, config))
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute('INSERT INTO recordings (title, fingerprints, settings, signature, public_key) VALUES (?, ?, ?, ?, ?)',
            (title.strip(), json.dumps(vectors), json.dumps(config), signature, public_key))
        return cur.lastrowid, len(vectors)


def recordings(db_path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute('SELECT id, title FROM recordings ORDER BY id DESC').fetchall()


def cosine(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 1e-12 else (1.0 if np.allclose(a, b) else 0.0)


def verify(db_path, record_id, audio_path, threshold=0.90):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute('SELECT fingerprints, settings, signature, public_key FROM recordings WHERE id=?',
                           (record_id,)).fetchone()
    if row is None:
        raise ValueError('Recording not found.')
    vectors = json.loads(row[0])
    config = json.loads(row[1])
    if config != settings():
        raise ValueError('Unsupported reference fingerprint settings.')
    root = merkle_root(vectors)
    Ed25519PublicKey.from_public_bytes(row[3]).verify(row[2], signed_message(root, config))
    incoming = fingerprints(audio_path)
    results = []
    for i in range(max(len(vectors), len(incoming))):
        score = cosine(vectors[i], incoming[i]) if i < min(len(vectors), len(incoming)) else None
        results.append({'segment': i+1, 'start_s': i*SEGMENT_SECONDS,
                        'end_s': (i+1)*SEGMENT_SECONDS, 'similarity': score,
                        'match': score is not None and score >= threshold})
    return results
