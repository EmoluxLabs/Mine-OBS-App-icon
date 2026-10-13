# Mine OBS — Android app (WebView wrapper)

This folder contains the complete, reproducible build for **Mine OBS v1.0.0**
(`com.obsmainnet.app`), a native Android wrapper that loads
`https://app.obsmainnet.us.ci` in a full-screen hardware-accelerated WebView.

* App name: **Mine OBS**
* Package ID: **com.obsmainnet.app**
* Version: **v1.0.0** (versionCode 1)
* minSdk 21 (Android 5.0) / targetSdk 34
* Launcher icon: the exact `obsidian-app-icon-1024.png` logo from the repo root,
  downscaled with a high-quality Lanczos filter to the standard launcher
  densities (mdpi 48px … xxxhdpi 192px). The artwork itself is untouched —
  no redraw, no recolor, transparency preserved.

## Features of the wrapper

* JavaScript, DOM storage (localStorage), databases, wide viewport + zoom
  controls, media autoplay — everything a modern web app needs.
* Navigation stays inside the app; the hardware/system back button walks the
  WebView history.
* `<input type="file">` uploads work (system file picker, multi-select).
* WebView state survives rotation/process death (`saveState`/`restoreState`).
* HTTPS-only friendly; INTERNET + ACCESS_NETWORK_STATE permissions only.

## Building

No Android SDK is needed. The build uses:

| piece | tool |
|---|---|
| dex assembly | `smali.jar` (pure Java, runs on any JRE 8+) |
| JRE | any `java` on PATH, or the `jdk4py` pip package |
| binary manifest / resources | `axml.py` + `arsc.py` (pure Python writers) |
| icons | Pillow (Lanczos resize) |
| packaging + signing | `signer.py` (JAR v1 + APK Signature Scheme v2, RSA-2048/SHA-256) |

```bash
pip install pillow cryptography jdk4py
python3 fetch_tools.py                 # downloads smali.jar/baksmali.jar
JAVA_BIN=$(python -c 'import jdk4py;print(jdk4py.JAVA)') python3 build.py
python3 verify.py dist/Mine-OBS-v1.0.0.apk ../mine-obs-signing/release-cert.pem
```

`build.py` outputs `dist/Mine-OBS-v1.0.0.apk`.

### Signing key

The release key lives **outside the repository** at `../mine-obs-signing/`
(`release-key.pem` / `release-cert.pem`) so the private key is never committed.
The first build generates it; later builds reuse it, keeping upgrade
signatures consistent. If you lose it, a new key can be generated but the
package will need reinstalling (Android refuses updates signed with a
different key).

### Tool provenance

`smali.jar` / `baksmali.jar` (v2.0.6) are fetched by `fetch_tools.py` from the
public GitHub repository `TOSPlus/TPS` (`build/tools/apktool/`), which mirrors
the standard smali/baksmali releases. Framework resource IDs used in the
manifest were extracted from a public `android.jar` mirror
(`MIT-PAC/droidsafe-src`) with `classfile.py`.

## Installing the APK

Direct download (signed release binary, also committed under `release/`):
<https://github.com/EmoluxLabs/Mine-OBS-App-icon/raw/arena/7230b132-mine-obs-app-icon/release/Mine-OBS-v1.0.0.apk>

Open it on the device, or:

```bash
adb install Mine-OBS-v1.0.0.apk
```

On the phone you may need to allow "install unknown apps" for your
browser/file manager. The APK is signed with APK Signature Scheme v1+v2 and
installs on Android 5.0 through Android 15.
