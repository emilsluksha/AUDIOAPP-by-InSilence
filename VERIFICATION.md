# Verification

Development platform: Windows 11 x64, Python 3.12.14.

- 81 pytest cases pass, including real WAV/MP3 decoding and export, damaged input,
  440 Hz pitch, all 24 tonal profiles, synthesized C-major audio, a 120 BPM rhythm,
  silence, white-noise rejection, anti-phase stereo, fragment analysis, all mastering presets, finite
  output, peak ceiling, zero-intensity bypass, cancellation, history persistence,
  language switching, settings persistence and drag/drop signal handling.
- Vocal tests cover changing notes (280 Hz → D4 and 430 Hz → A4), bit-exact 0%
  bypass, independent strength/retune controls, scale membership, BPM independence,
  six distinct presets, silence, unvoiced noise, cancellation and invalid settings.
- Source GUI integration measured the rendered corrected tone at 293.39 Hz for
  a D4 target (293.66 Hz), and exported/decoded WAV 24-bit and MP3.
- Downloader tests cover URL validation, cancel cleanup, non-overwrite behavior,
  resolution/DRM selection, actual FFmpeg MP3 encoding and MP4 video/audio muxing.
- Live preview and actual MP3 192 kbps / MP4 720p downloads succeeded for
  [Big Buck Bunny](https://www.youtube.com/watch?v=YE7VzlLtp-4), © 2008 Blender
  Foundation, [CC BY 3.0](https://peach.blender.org/about/). Downloaded media is
  excluded from the repository and distribution. Service availability may change.
- New UI controls, EN/RU and persistence are covered by the UI test.
- librosa emits expected tuning/FFT warnings for percussion-only and short synthetic
  fixtures. These are not test failures.
- PyInstaller onefile build is checked from a separate temporary directory containing only KEYWAVE.exe.
- The packaged application completed decoding в†’ analysis в†’ mastering в†’ WAV and MP3
  export в†’ decode exported MP3 в†’ playback в†’ A/B switch в†’ Russian interface.
- Synthetic C-major / 120 BPM fixture measured C major / approximately 120.03 BPM.
- Example master: original -19.44 LUFS; processed -16.18 LUFS at 60% intensity;
  measured peak -2.75 dBTP. These are test-fixture measurements, not product defaults.
- Qt playback position advanced beyond 2 seconds on this machine. This verifies the
  playback pipeline, not subjective audio quality or every output device.
- Qt-rendered layouts were exercised at 960Г—640 and 1200Г—780, EN/RU, 125%, 150%,
  and 200% scaling. This does not cover every physical monitor configuration.

Local evidence is in `artifacts/standalone-upgrade/`: `smoke-result.json`, WAV/MP3 outputs and
screenshots. Artifacts are intentionally excluded from source control. The Windows
workflow repeats tests and packaged checks and uploads its own evidence.

No clean Windows machine without Python was available; standalone testing on the
development machine does not establish that separate environment. Vocal testing
uses synthetic notes, not a labelled singer corpus or subjective listening panel.

Not established: accuracy against a labelled real-world music corpus, equivalence
to commercial key detectors, certified ITU true-peak compliance, sample-accurate
A/B switching, exhaustive codec/device compatibility, Windows 10 physical-device
testing, or a digitally signed installer. See README for processing and memory limits.

## Regression fixes 1.1.1

- Reproduced blank button labels: Qt rejects integer QFont.setWeight arguments.
  A rendered-pixel test now checks that labels are drawn and Qt raises no exception.
- Verified the native dark caption on the development desktop and the RGBA logo.
- Reproduced frozen HTTPS failure at SSLContext construction: the development
  Python requires codex-rejected-cas.pem, absent from the previous EXE. Including
  that resource fixed SSL and HTTPS in an isolated frozen diagnostic. Certificate
  verification stays enabled. Stock Python builds do not require this extra file.
- Packaged smoke now creates a verified yt-dlp SSL context, catching the issue
  without requiring network access in CI.
- Live user-supplied link -AYA25JpXLs: source MP3/MP4 download and decode succeeded.
  Packaged download checks write separate evidence under artifacts/.
