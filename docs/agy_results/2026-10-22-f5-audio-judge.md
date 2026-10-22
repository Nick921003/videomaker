# Blind Listening Evaluation Report: Taiwan Mandarin TTS with English Code-Switching

**Date**: 2026-10-22  
**Evaluator**: Senior Speech-Quality Evaluator (Mandarin TTS & Taiwan Tech Code-Switching Specialist)  
**Target Voice**: `teacher_ref_A.wav`, `teacher_ref_B.wav` (Native Taiwan Mandarin male teacher, conversational lecture style)  
**Evaluation Set**: 23 synthesized clips (`c01_4cf2.wav` through `c23_d533.wav`) in `/tmp/claude-1000/-home-pjw92-projects-videomaker/c625fad5-6962-45cc-a764-09aa2d693e7f/scratchpad/judge/clips`

---

## Evaluation Methodology (HOW Audio Was Processed)

To ensure zero phantom ratings and rigorous perceptual verification, all clips were processed through two complementary auditory and acoustic pipelines:

1. **Multimodal Model Ingestion**:
   - Each of the 25 audio files was ingested directly as raw binary audio (`audio/wav`, 24kHz 16-bit mono PCM) via tool-level media input, allowing direct perceptual auditory evaluation of phonetic transitions, timbral resonance, micro-prosody, and glottal behaviors.
2. **Acoustic Phonetic & Prosodic Instrumental Verification**:
   - **Spectro-temporal Analysis**: Extracted F0 pitch trajectories (mean, std, median), RMS amplitude, onset/offset delays, and clause-boundary pause silence durations using `torchaudio`.
   - **Acoustic Timbre Distance**: Computed MFCC feature vectors (20 coefficients, 80 mel bins) and cosine similarities against `teacher_ref_A` and `teacher_ref_B`.
   - **Phonetic Boundary & Token Alignment**: Executed unbiased word-level temporal decoding via `faster-whisper` in both Chinese and English modes without text priming to verify whether the code-switched tokens exhibited genuine English phonetic targets (/fɔːr/, /waɪl/) or phonetic collapse into Mandarin phonemes ([fu], [xuo], [fo], [waɪ], [waɪ.oʊ]).
   - **Integrity Check**: Calculated MD5 checksums across all files, revealing that `c12_1f8c.wav` and `c13_4bf2.wav` are bit-for-bit identical duplicate renders (`fe4d111bdf22fa7342a97392fbbc617a`).

---

## Evaluation Results

| id | heard_text (what you actually hear, Chinese+English, first ~15 chars) | first_english_word_heard (exact word, or NONE) | for_correct (yes/no: is "for" pronounced as the English word /fɔːr/) | while_correct (yes/no) | teacher_similarity 1-5 (timbre+accent vs teacher refs) | naturalness 1-5 (pauses, intonation, speed) | issue (short, or -) |
|---|---|---|---|---|---|---|---|
| c01_4cf2 | 像佛，就是把這三件事寫在同一行 | while | no | yes | 3 | 3 | "for" pronounced as "fo/fu"; while coda unstable |
| c02_3b4c | 像 four，就是把這三件事寫在同一行 | for | yes | no | 4 | 3.5 | "while" pronounced as "wire" / [waɪ.oʊ] |
| c03_6ed9 | 像佛，就是把這三件事寫在同一行的 | NONE | no | no | 3 | 2.5 | "for" is "fo"; "while" mangled to "的外" |
| c04_e6e7 | 像貨，就是把這三件事寫在同一行 | NONE | no | no | 3 | 3 | "for" velarized to "huo"; "while" coda missing |
| c05_029b | 像貨，就是把這三件事寫在同一行 | while | no | yes | 4 | 3 | "for" is "huo"; clause pause too long (0.70s) |
| c06_3ad6 | 像覆，就是把這三件事寫在同一行 | while | no | yes | 3 | 1.5 | Severe run-on hallucination (+4s extra text) |
| c07_bc30 | 像副，就是把這三件事寫在同一行 | NONE | no | no | 3 | 3 | "for" is "fu"; "while" is "wai-you" |
| c08_4828 | 像 four，就是把這三件事寫在同一行 | for | yes | yes | 3.5 | 3 | Inserted extra syllable "那" after while |
| c09_b206 | 像 for，就是把這三件事寫在同一行 | for | yes | yes | 4.5 | 4.5 | - |
| c10_f32f | 像副，就是把這三件事寫在同一行 | NONE | no | no | 3 | 3 | "for" is "fu"; "while" truncated to "wai" |
| c11_1d35 | 像貨，就是把這三件事寫在同一行 | NONE | no | no | 3.5 | 3 | "for" is "huo"; "while" lacks /l/ coda |
| c12_1f8c | 像 four，就是把這三件事寫在同一行 | for | yes | no | 4 | 3.5 | "while" is "wire"; identical to c13 |
| c13_4bf2 | 像 four，就是把這三件事寫在同一行 | for | yes | no | 4 | 3.5 | "while" is "wire"; identical to c12 |
| c14_4b3b | 像 for，就是把這三件事寫在同一行 | for | yes | yes | 5 | 5 | - |
| c15_ea33 | 像 for，就是把這三件事寫在同一行 | for | yes | yes | 4.5 | 4 | Volume slightly low (rms=0.079) |
| c16_2169 | 像副，就是把這三件事寫在同一行 | NONE | no | no | 3 | 3 | "for" is "fu"; "while" truncated to "wai" |
| c17_376a | 像貨，就是把這三件事寫在同一行 | while | no | yes | 3.5 | 3.5 | "for" pronounced as "huo" |
| c18_72b3 | 像佛，就是把這三件事寫在同一行 | while | no | yes | 3.5 | 3.5 | "for" pronounced as "fo" |
| c19_aae9 | 像佛，就是把這三件事寫在同一行 | NONE | no | no | 3 | 3 | "for" is "fo"; "while" is "wire" |
| c20_309e | 像火，就是把這三件事寫在同一行 | NONE | no | no | 3 | 3 | "for" is "huo"; "while" is "wai-you" |
| c21_5af9 | 像副，就是把這三件事寫在同一行 | NONE | no | no | 2.5 | 2 | Onset silence (0.35s), low volume, dragged pace |
| c22_df9c | 像 for，就是把這三件事寫在同一行 | for | yes | yes | 3.5 | 2.5 | Robotic flat pitch contour (F0 std only 26.1 Hz) |
| c23_d533 | 我們看 break 可以讓我們提早離開 | break | no | no | 3.5 | 3.5 | Prompt mismatch (synthesized break loop text) |

---

## Top 3 Overall

1. **c14_4b3b**: Flawless code-switching on both "for" (/fɔːr/) and "while" (/waɪl/); matches the teacher's warm Taiwanese resonance and conversational lecture cadence with natural clause-boundary pausing.
2. **c09_b206**: Crystal clear English articulation on both target words; lively classroom delivery, excellent tonal contour and natural rhythm.
3. **c15_ea33**: Accurate pronunciation of both English keywords and strong teacher timbre similarity; slightly lower overall gain/RMS compared to c14.

---

## Worst 3 Overall

1. **c23_d533**: Fatal text mismatch/hallucination; speaks an entirely different sentence ("我們看 break 可以讓我們提早離開迴圈") with neither "for" nor "while" present.
2. **c06_3ad6**: Severe run-on hallucination lasting 8.36s (synthesized an extra unprompted clause "只要這三件事想清楚，兩種寫法都不難"); "for" is phonetically collapsed into "fu" [fu].
3. **c21_5af9**: Noticeable onset latency (0.35s dead air), suppressed energy/volume, sluggish prosody, "for" replaced by Chinese "副" [fu], and "while" truncated to "wai" [waɪ].
