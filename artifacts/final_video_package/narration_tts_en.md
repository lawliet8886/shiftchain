# Final English narration — TTS candidate

Target video: **3:40**. Delivery: **125–145 WPM**, calm, confident, technical, and human. Generate and review each segment separately; do not force speech to fill every window.

## 01_friction — 0:00–0:18

A single handoff is easy. A handoff of a handoff is where responsibility starts to get lost. ShiftChain turns messy human messages into a verified chain of responsibility, even when confirmation arrives late or infrastructure retries the same task.

## 02_evt001 — 0:18–0:45

First, Maya hands the shift to Liam. Gemini turns the message into a structured intent, but it cannot change the schedule. Deterministic rules check ownership, consent, and versions. Firestore readback must confirm the change before the handoff becomes verified.

## 03_evt002 — 0:45–1:10

Now Liam hands that same responsibility to Sofia. This is not an independent update. Liam can do it only because the earlier Maya-to-Liam handoff is already part of the custody chain. ShiftChain keeps the whole history instead of replacing it with the latest name.

## 04_evt003 — 1:10–1:35

Next, Noah asks Emma to take another shift, but Emma has not confirmed yet. ShiftChain does not guess. It saves a durable waiting state and schedules a real Cloud Task. Waiting is visible, safe, and persistent.

## 05_early_wake — 1:35–1:55

The first scheduled check wakes up before Emma's confirmation exists. ShiftChain reads Firestore, makes no business change, and exits safely. Nothing is lost, and nothing is invented.

## 06_evt004 — 1:55–2:20

Now Emma confirms. Gemini interprets the confirmation, ShiftChain stores it, and a new resume task is scheduled. From this moment on, I will not click anything.

**Delivery note:** hold a noticeable pause after the final sentence. This is the judge-facing zero-click boundary.

## 07_autonomous_resume — 2:20–2:42

Cloud Tasks securely wakes the workflow. ShiftChain reloads persistent state, revalidates every rule, transfers the responsibility from Noah to Emma, and independently verifies the result. The workflow finishes itself.

## 08_reliability — 2:42–3:08

Now Judge Mode runs one controlled reliability test. After the business effect is already verified, the service intentionally returns HTTP five-oh-three, simulating a lost acknowledgement. Cloud Tasks retries the same task. ShiftChain reads before repeating, finds the verified effect, keeps every version unchanged, and records no-op verified instead of applying the transfer twice.

## 09_architecture — 3:08–3:30

Under the hood, Gemini understands intent. Google A-D-K coordinates the tools. Deterministic code controls every change. Firestore stores the truth. Cloud Tasks handles time and retries. Secret Manager protects the Gemini credential.

## 10_closing — 3:30–3:40

This is the live application running on Google Cloud Run. Responsibility moves. ShiftChain keeps the truth.
