# TTS timing sheet

Planning rate: **135 WPM**, inside the requested natural range of **125–145 WPM**. Estimates count hyphenated forms as one word and exclude headings and delivery notes. Real synthesized durations must be measured after a human chooses the voice.

| Segment | Window | Words | Estimated voiced duration | Available pause |
| ------- | ------ | ----: | ------------------------: | --------------: |
| 01_friction | 0:00–0:18 | 39 | 17.3 s | 0.7 s |
| 02_evt001 | 0:18–0:45 | 39 | 17.3 s | 9.7 s |
| 03_evt002 | 0:45–1:10 | 44 | 19.6 s | 5.4 s |
| 04_evt003 | 1:10–1:35 | 36 | 16.0 s | 9.0 s |
| 05_early_wake | 1:35–1:55 | 27 | 12.0 s | 8.0 s |
| 06_evt004 | 1:55–2:20 | 26 | 11.6 s | 13.4 s |
| 07_autonomous_resume | 2:20–2:42 | 29 | 12.9 s | 9.1 s |
| 08_reliability | 2:42–3:08 | 53 | 23.6 s | 2.4 s |
| 09_architecture | 3:08–3:30 | 32 | 14.2 s | 7.8 s |
| 10_closing | 3:30–3:40 | 16 | 7.1 s | 2.9 s |
| **Total** | **0:00–3:40** | **341** | **151.6 s (2:31.6)** | **68.4 s** |

## Natural-rate range

- At 125 WPM: approximately **163.7 seconds (2:43.7)** of voiced narration.
- At 135 WPM: approximately **151.6 seconds (2:31.6)** of voiced narration.
- At 145 WPM: approximately **141.1 seconds (2:21.1)** of voiced narration.
- Target final video duration: **220 seconds (3:40)**.

Short silence is intentional. It lets the live application, Gemini latency, Cloud Task timing, and retry evidence remain visible without misleading edits.

## Timing cautions

- **01_friction:** at exactly 125 WPM, the estimate is about 18.7 seconds. Prefer a voice near 135 WPM or start the opening line immediately; do not rush it.
- **06_evt004:** reserve at least **1.5 seconds** after “I will not click anything.” The structured plan encodes this pause.
- **08_reliability:** this is the densest segment. At 125 WPM it is about 25.4 seconds inside a 26-second window. Test clarity before changing speed or text.
- Align each approved segment to the real continuous recording. Do not accelerate, conceal, or invent backend activity to fit narration.
