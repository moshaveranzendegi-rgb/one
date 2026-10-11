@echo off
setlocal
cd /d "%~dp0"
echo ================================================================
echo RS ai Android APK builder
echo ================================================================
where java >nul 2>nul
if errorlevel 1 (
  echo Java/JDK 17 was not found. Install JDK 17 or Android Studio first.
  pause
  exit /b 1
)
java -version 2>&1 | findstr /c:"17." >nul
if errorlevel 1 echo NOTICE: Android Gradle Plugin 8.7.3 is tested with JDK 17. A different Java version may fail.
if not defined ANDROID_HOME if not defined ANDROID_SDK_ROOT (
  echo Android SDK path is not configured. Install Platform 35 using Android Studio SDK Manager.
  echo Then set ANDROID_HOME or ANDROID_SDK_ROOT if your installation does not set it automatically.
  pause
  exit /b 1
)
where gradle >nul 2>nul
if errorlevel 1 (
  echo Gradle command was not found.
  echo Install Gradle 8.9 or open this project in Android Studio and configure a compatible Gradle distribution.
  echo The Android SDK and internet access are required for dependency downloads.
  pause
  exit /b 1
)
gradle --no-daemon assembleDebug
if errorlevel 1 goto :fail
if not exist "app\build\outputs\apk\debug\app-debug.apk" goto :fail
for %%F in ("app\build\outputs\apk\debug\app-debug.apk") do echo APK created: %%~fF ^(%%~zF bytes^)
pause
exit /b 0
:fail
echo APK build failed. Confirm JDK 17, Android SDK Platform 35, Gradle 8.9 and internet access.
pause
exit /b 1
