# Gujarat News Reels → Instagram (auto)

Yeh tool roz apne aap:

1. **Gemini + Google Search** se Gujarat ki asli, taaza news dhundta hai (crime, sara samachar, sarkari jaherat)
2. Us news ka ek **colourful Gujarati news card** (1080×1920 image) banata hai. Har category ki apni theme hai (crime = laal, khushkhabar = hara, sarkari = kesari/neela), aur peeche **Gemini ki banayi AI image** hoti hai
3. Image ko **15 second ki Reel** mein badalta hai (slow zoom + music)
4. **Instagram pe Reel post** karta hai (official Instagram API, password ki zaroorat nahi)

```
News (Gemini + Google Search) → AI background (Gemini image) → Card image (HTML → PNG) → Reel MP4 (FFmpeg) → Instagram API
```

## 1. Zaroori keys

| Key | Kahan se milegi |
|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Create API key. Free tier mein limit hai; AI image aur zyada posts ke liye billing on karni pad sakti hai |
| `IG_ACCESS_TOKEN` | Meta app → Instagram API → API setup with Instagram login → **Generate token** |
| `IG_USER_ID` | Usi page pe account ke neeche likha number (`17841422688299078`) |
| `PEXELS_API_KEY` | Optional, free: [pexels.com/api](https://www.pexels.com/api/). AI image na bane to backup photo yahan se aati hai |

> ⚠️ Token/keys kabhi chat, code ya GitHub pe paste mat karna. Sirf `.env` (local) ya GitHub Secrets mein.

## 2. GitHub Actions pe roz automatic chalana (recommended)

1. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**
2. Upar wali 4 keys add karo (same naam ke saath).
3. **Actions** tab → **Gujarat news reel** → **Run workflow**.
   - Pehli baar `publish` ka tick hata kar chalao. Video **Artifacts** mein milega, use download karke dekh lo.
   - Theek lage to tick laga kar chalao, Reel post ho jayegi.
4. Uske baad yeh roz **8:10, 13:10 aur 19:10 IST** pe apne aap chalega. Time badalna ho to `.github/workflows/daily-reel.yml` mein `cron` badlo (time UTC mein hota hai, IST se 5:30 ghante peeche).

### Token auto-refresh (60 din wali problem)

Instagram token 60 din mein expire hota hai. `refresh-token.yml` har hafte use naya kar deta hai. Iske liye:

1. GitHub → Settings → Developer settings → **Fine-grained personal access token** banao.
   - Sirf is repo ka access do.
   - Permission: **Secrets: Read and write**.
2. Use repo secret **`GH_PAT`** naam se save karo.

## 3. Apne computer pe chalana

```bash
pip install -r requirements.txt
python -m playwright install chromium
# ffmpeg bhi install hona chahiye (Windows: winget install ffmpeg, Mac: brew install ffmpeg)

cp .env.example .env        # .env mein keys bharo
python main.py check        # token sahi hai ya nahi
python main.py run --no-publish             # sirf video banao, output/ mein dekho
python main.py publish output/<folder>/reel.mp4 --caption-file output/<folder>/caption.txt
python main.py run                          # news → reel → post, sab ek saath
python main.py run --category government    # sirf ek category
```

Har run ka folder `output/<date-time>/` mein banta hai, usmein yeh files hoti hain:
- `research.md`: Gemini ko kaunsi news mili aur kin sources se
- `story.json`, `caption.txt`, `background.png`, `card.png`, `reel.mp4`

## 4. Music 🎵

`assets/music/` folder mein `.mp3` files daal do. Har reel mein ek random gaana lag jayega (beech ke kisi hisse se, fade in/out ke saath).

**Zaroori:** Instagram API se Instagram ki apni music library (trending audio) attach **nahi** ho sakti. Yeh Instagram ki limit hai. Isliye:
- **Bollywood ya trending film songs mat daalna.** Copyright ki wajah se Reel mute ho sakti hai, ya account pe strike aa sakti hai.
- Royalty-free music use karo, jaise [Pixabay Music](https://pixabay.com/music/), YouTube Audio Library, ya [Uppbeat](https://uppbeat.io).
- Agar trending audio hi chahiye, to `--no-publish` se video banao aur phone se manually upload karo. Upload karte waqt Instagram app mein trending audio add kar sakte ho.

## 5. Poster design

`card.style: "ai_poster"` (default): **Gemini ka image model poora poster banata hai**, jaise viral Gujarati news pages ke posters hote hain. Usmein badi headline, 3D illustration, info boxes, aur schedule/list wali news ke liye rangeen table hoti hai. Har baar style alag hota hai.

- Image models kabhi-kabhi Gujarati mein spelling ya number galat likh dete hain. Isliye har poster ko Gemini **dobara padh kar check karta hai**. Galti mile to poster dobara banta hai (`poster_attempts`, default 3).
- Teeno baar fail hua to tool apna **template card** (`src/card.py`) use karta hai, taaki galat number wala poster kabhi post na ho.
- Har try `output/<folder>/poster_try1.png`, `poster_try2.png` mein save hota hai, taaki aap dekh sako.
- `card.style: "template"` karoge to hamesha fixed template design banega.

## 6. Settings (`config.yaml`)

- `content.categories`: kaun si news chahiye (crime / good_news / government)
- `content.extra_instructions`: jaise "sirf Ahmedabad ki news" ya "exam aur job news ko priority do"
- `card.handle`: card pe dikhne wala Instagram handle
- `gemini.text_model` / `gemini.image_model`: Gemini models. Google naya model laaye ya purana band kare to yahan naam badal do
- `gemini.ai_background`: `false` karoge to AI image nahi banegi, sirf Pexels photo ya theme colours
- Colours/themes badalne hain to `src/card.py` mein `THEMES` dekho
- `video.seconds`: reel ki length (12–15 achha hai)
- `video.zoom`: slow zoom on/off

## 7. News ke niyam (built-in)

Gemini ko yeh niyam diye gaye hain:
- Sirf web pe mile **asli sources** ki baatein. Koi number ya date guess nahi karega.
- Crime news mein victim (khaaskar sexual offence ke cases) ya bachchon ki pehchaan nahi batayega. Jinka case abhi chal raha hai unhe sirf "આરોપી" kahega.
- Har card aur caption pe **source ka naam** dikhega.

Phir bhi shuru ke kuch din `--no-publish` se check karke post karna better hai. Galat news se page ki credibility aur legal dono ka risk hai.
