# TTS voice options

Inventory and public-option check performed on **2026-08-25**. No account was created, no service was enabled, no package was installed, and no audio was generated.

## Environment inventory

- Windows local speech voices detected: **Microsoft Zira Desktop — English (United States)**, plus Microsoft Maria Desktop, Microsoft Maria, and Microsoft Daniel in Brazilian Portuguese.
- Existing local capability: .NET **System.Speech** can enumerate installed voices and export WAV.
- Existing media utilities: **ffmpeg** and **ffprobe**.
- No dedicated TTS CLI or Python TTS package was found in the project environment.

## Shortlist

| Option | Local or cloud | Cost | Login required? | WAV/MP3 export | Expected quality | Voices / accents | Ease | Risk / restriction | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Google Cloud Text-to-Speech — Chirp 3 HD** | Cloud | Usage-priced; current Google pricing lists a free monthly character allowance, with billing enabled | Yes: Google Cloud authentication and a billing-linked project | Yes | High; natural and expressive | Many English (US) and international voices | Good after API setup | Script is sent to Google Cloud; Text-to-Speech API enablement and client setup are not yet confirmed | **RECOMMENDED** for strongest fit with the existing Google Cloud demo and professional quality |
| **ElevenLabs Text to Speech** | Cloud | Free plan available with a limited credit allowance; paid tiers expand usage and formats | Yes | Yes | Very high, depending on model and voice | Broad multilingual voice catalogue | Very easy through web UI | External vendor/account; script upload and plan limits; some output options depend on tier | Strong quality alternative if the user accepts a separate service |
| **Windows System.Speech — Microsoft Zira Desktop** | Local | Free with the installed Windows voice | No | WAV directly; MP3 can be derived later with installed ffmpeg | Medium; clear but noticeably older/less natural | en-US female adult voice installed | Easiest and fully local | Robotic prosody may reduce judge-facing polish | Privacy-first fallback and timing prototype only |

## Option details

### 1. Google Cloud Text-to-Speech — Chirp 3 HD — RECOMMENDED

- Official voice catalogue: https://cloud.google.com/text-to-speech/docs/voices
- Chirp 3 HD documentation: https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd
- Official pricing: https://cloud.google.com/text-to-speech/pricing
- Output formats include MP3 and LINEAR16/WAV.
- The service matches ShiftChain's existing Google Cloud context, but it must remain a separate narration tool: it does not replace or simulate the live backend.
- **Installation required** for the simplest future Python workflow: `python -m pip install google-cloud-texttospeech`.
- Future setup may also require enabling the Text-to-Speech API in the chosen billing-linked project. Do not do this until the human selects this option.

### 2. ElevenLabs Text to Speech

- Official overview: https://elevenlabs.io/docs/overview/capabilities/text-to-speech
- Official pricing: https://elevenlabs.io/pricing
- Official download guidance: https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/how-do-i-download-generated-files-from-text-to-speech
- Suitable when maximum naturalness outweighs the need to keep the workflow in the Google ecosystem.
- No local installation is required for the web workflow, but account creation, login, and acceptance of the provider's terms are required.

### 3. Windows System.Speech — Microsoft Zira Desktop

- Official installed-voice API: https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer.getinstalledvoices
- Official WAV export API: https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer.setoutputtowavefile
- Already available locally; no external transmission, account, installation, or usage fee.
- Appropriate for timing tests after human approval, but likely below the desired naturalness for the final submission.

## Decision gate

Choose one tool and one specific English voice before any synthesis. For a fair comparison, generate only the same short approved segment with each finalist after that decision; review pronunciation, warmth, pace, and timing before producing all ten files.
