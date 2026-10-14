# motus.leap 0.5.1 — Android development build

Native Android companion for the existing HTTPS motus.leap server: Google sign-in, Dashboard, scans, playlist/channel browsing, reviewed AI sorting and encrypted session persistence.

## Validation

- Built from repository commit 9e31ecf3c9d41c7f770b5a8a52195f30b6fae9c5.
- JDK 17, Android SDK 36, Gradle 9.3.1.
- `assembleDebug lintDebug` passed. Lint reported 14 warnings and no errors.
- No installation or device-level verification was performed for this publication.

## Download

The attached APK is debug signed for personal development/sideloading and requires Android 8 or later. It needs an existing configured motus.leap server; it is not a standalone YouTube backend. Use your own Google account and server configuration.

SHA256SUMS.txt verifies the attached APK. A matching signing certificate is required to update an existing installation. Preserve app data; do not uninstall to work around a certificate mismatch.

The source tag/archives below contain the matching code. Read android/README.md for build/setup and the website help for options. This is a prerelease, not a Play Store release.
