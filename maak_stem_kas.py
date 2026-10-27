# -*- coding: utf-8 -*-
# DraveKas - Copyright (C) 2026 Dravenlock (Roger & Claudio).
"""maak_stem_kas.py - Leon spreekt de getallen en zinnetjes in voor DraveKas op de telefoon. Draai: py -3.10 maak_stem_kas.py"""
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kas_data as kd

ZINNEN = {"n%d" % i: kd.onder_honderd(i) for i in range(100)}
ZINNEN.update({"honderd": "honderd", "duizend": "duizend", "euro": "euro",
               "k_deze_maand_in": "Deze maand kwam er", "k_binnen": "binnen.", "k_je_gaf": "Je gaf", "k_uit": "uit.",
               "k_nog": "Je hebt nog", "k_over": "over.", "k_let_op_tekort": "Let op: je komt", "k_tekort": "tekort."})


def main():
    from neuvoice import TTS
    uit = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stem_kas")
    os.makedirs(uit, exist_ok=True)
    tts = TTS(auto_download=True)
    namen = list(getattr(tts, "voice_style_names", []) or [])
    stijl = tts.get_voice_style("Leon" if "Leon" in namen else namen[0])
    sr = int(getattr(tts, "sample_rate", 44100) or 44100)
    for sleutel, tekst in ZINNEN.items():
        wav, _ = tts.synthesize(tekst, voice_style=stijl, total_steps=10, speed=0.9, lang="nl")
        x = np.asarray(wav, dtype=np.float32).flatten()
        drempel = 0.01 * (np.max(np.abs(x)) or 1)
        waar = np.where(np.abs(x) > drempel)[0]
        if len(waar):
            x = x[max(0, waar[0] - int(sr * 0.015)): waar[-1] + int(sr * 0.04)]
        x = np.concatenate([np.zeros(int(sr * 0.03), np.float32), x, np.zeros(int(sr * 0.03), np.float32)])
        n = int(len(x) * 22050 / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
        x = x / (np.max(np.abs(x)) or 1) * 0.9
        with wave.open(os.path.join(uit, sleutel + ".wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes((x * 32767).astype("<i2").tobytes())
    print("KLAAR", len(ZINNEN))


if __name__ == "__main__":
    main()
