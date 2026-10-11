# اپ Android همراه RS ai

این پوشه سورس پروژهٔ Android Studio است، نه APK آماده. اپ یک WebView برای اتصال به پنل RS ai روی رایانهٔ ویندوزی است؛ مدل OmniAvatar روی موبایل اجرا نمی‌شود.

## ساخت APK
1. این پوشه را در Android Studio باز کن.
2. JDK 17 و Android SDK Platform 35 را نصب کن.
3. Gradle 8.9 یا سازگار را آماده کن.
4. `BUILD_APK_WINDOWS.bat` را اجرا کن یا در این پوشه `gradle --no-daemon assembleDebug` را بزن.
5. مسیر APK: `app\build\outputs\apk\debug\app-debug.apk`.

این ساخت به اینترنت برای دریافت وابستگی‌های Gradle نیاز دارد. APK در این سورس ساخته نشده است.
