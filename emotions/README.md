# Emotion animations

Two built-in face styles, chosen with `JARVIS_FACE_STYLE` in `.env`:

- **emo** (default) — big glowing eyes on a black screen, EMO-robot
  style: everything is expressed through eye shape and motion (blinks,
  crescent smiles, heart eyes, droopy tear, equalizer bars while
  listening, flickering X eyes on error).
- **classic** — round smiley faces with colored backgrounds.

Preview both live in the browser with `./jarvis-cli debug`.

JARVIS shows an animated face for each state on the Whisplay LCD:

| name | shown when |
|---|---|
| idle | waiting for the button (slow blink) |
| listening | recording your voice (wide eyes + sound waves) |
| thinking | recognizing speech / querying the brain (cycling dots) |
| answering | speaking a neutral reply (talking mouth) |
| happy / sad / surprised / love / angry | reaction picked from emoji or sentiment words in the reply |
| error | something failed (dizzy X eyes) |

All faces are drawn procedurally — no assets needed. To use your own GIF
for a state, drop it here named after the state:

    emotions/listening.gif
    emotions/happy.gif
    ...

Any size works; frames are scaled into the face area (240x170) and the
text panel stays below. Keep GIFs small (a few hundred KB) — a Pi Zero 2W
decodes them at startup.

Handy commands:

    ./jarvis-cli emotions            # list states + which have custom GIFs
    ./jarvis-cli emotions --export   # write built-in faces as _default_*.gif
    ./jarvis-cli debug               # live preview of all faces in the browser

Files starting with `_default_` are exports for reference and are ignored
as overrides.
