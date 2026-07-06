# movie-muse

## Cursor Cloud specific instructions

This repo is two standalone Python 3 CLI scripts (no server, no build, no automated tests):

- `download_movie_scripts.py` — scrapes movie scripts from `imsdb.com` into `movie_script_files/`. Running it directly downloads **all** ~1300 scripts (slow, hits a live third-party site). The corpus is already committed, so re-scraping is rarely needed. To smoke-test the scraper pipeline without a full crawl, run the same `requests` → `BeautifulSoup` → `html2text` steps on a single script.
- `video_transformer.py` — transfers a reference image's luminance (LAB L channel) onto every frame of a video, writing `transformed_video.mp4`.

Dependencies are installed to the user site (`pip install --user`) by the startup update script; `requirements.txt` lists them.

Non-obvious caveats:
- `video_transformer.py` is **interactive** (two `input()` prompts: video path, then image path) and calls `cv2.imshow`, which needs a display. In this headless VM, run it under a virtual display and pipe the paths, e.g.:
  `printf '/path/video.mp4\n/path/image.png\n' | xvfb-run -a python3 video_transformer.py`
  (`xvfb` is preinstalled on this VM but is NOT in the update script; reinstall with `sudo apt-get install -y xvfb` if missing.)
- Under `imshow`, OpenCV prints harmless `QFontDatabase: Cannot find font directory ...` warnings — these are cosmetic and do not affect the produced video.
- `transformed_video.mp4` is written to the repo root and is not git-ignored; delete it after testing so it isn't committed.
- There is no linter config and no test suite in this repo.
