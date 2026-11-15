# Verification

Development platform: Windows 11 x64, Python 3.12.14.

- 53 pytest cases pass, including real WAV/MP3 decoding and export, damaged input,
  440 Hz pitch, all 24 tonal profiles, synthesized C-major audio, a 120 BPM rhythm,
  silence, white-noise rejection, anti-phase stereo, fragment analysis, all mastering presets, finite
  output, peak ceiling, zero-intensity bypass, cancellation, history persistence,
  language switching, settings persistence and drag/drop signal handling.
- librosa emits expected tuning/FFT warnings for percussion-only and short synthetic
  fixtures. These are not test failures.
- PyInstaller onedir build launches directly on Windows.
- The packaged application completed decoding → analysis → mastering → WAV and MP3
  export → decode exported MP3 → playback → A/B switch → Russian interface.
- Synthetic C-major / 120 BPM fixture measured C major / approximately 120.03 BPM.
- Example master: original -19.44 LUFS; processed -16.18 LUFS at 60% intensity;
  measured peak -2.75 dBTP. These are test-fixture measurements, not product defaults.
- Qt playback position advanced beyond 2 seconds on this machine. This verifies the
  playback pipeline, not subjective audio quality or every output device.
- Qt-rendered layouts were exercised at 960×640 and 1200×780, EN/RU, 125%, 150%,
  and 200% scaling. This does not cover every physical monitor configuration.

Local evidence is in `artifacts/packaged/`: `smoke-result.json`, WAV/MP3 outputs and
screenshots. Artifacts are intentionally excluded from source control. The Windows
workflow repeats tests and packaged checks and uploads its own evidence.

Not established: accuracy against a labelled real-world music corpus, equivalence
to commercial key detectors, certified ITU true-peak compliance, sample-accurate
A/B switching, exhaustive codec/device compatibility, Windows 10 physical-device
testing, or a digitally signed installer. See README for processing and memory limits.
