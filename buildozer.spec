[app]

# (str) Title of your application
title = Base64 转换工具

# (str) Package name
package.name = base64converter

# (str) Package domain (needed for android/ios packaging)
package.domain = org.operit

# (str) Source code where the main.py live
source.dir = .

# (str) Application versioning
version = 2.0.0

# (str) Requirements (python-for-android)
requirements = python3,kivy==2.3.1,kivymd==1.2.0,chardet,pyjnius,android

# (str) Orientation (one of: portrait, landscape, portrait_landscape, sensor)
orientation = portrait

# (int) Android API level to use
android.api = 34

# (int) Minimum API level
android.minapi = 21

# (int) Target API level
android.target_api = 34

# (str) Presplash of the application
presplash.filename =

# (str) Icon of the application
icon.filename =

# (str) Supported architectures
android.archs = arm64-v8a

# (str) Android NDK version
android.ndk = 27

# (str) Android SDK version
android.sdk = 34

# (str) Android SDK build tools version
android.build_tools = 34.0.0

# (bool) If True, then also try to copy files from the source directory to the
# package directory
android.copy_libs = True

# (bool) If True, use the android debug mode
android.debug = True

# (str) Log level for the application
android.log_level = 2

# (str) Entry point for the application
source.include_exts = py,png,jpg,kv,atlas,ttf

# (list) Source files to include (relative to source.dir)
source.include_patterns = main.py,base64_app/*.py

# (str) Presplash background color
presplash.color = #0a0e17

# (str) Fullscreen mode
fullscreen = 0

# (list) Permissions
# Android 6-10: READ/WRITE_EXTERNAL_STORAGE
# Android 11+:  MANAGE_EXTERNAL_STORAGE (引导用户手动设置)
# Android 13+:  READ_MEDIA_IMAGES/VIDEO/AUDIO (细粒度媒体权限)
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO

# (str) Extra Java source files to add to the Android project
# 使用 android.add_src 添加自定义 Java 代码来修改 AndroidManifest.xml
# 空值 = 不添加

# (str) Extra command line arguments for the Android build
android.extra_args = --allow-missing-permissions

[buildozer]

# (int) Log level (0-2)
log_level = 2

# (str) Path to build artifact storage
build_dir = /root/.buildozer

# (str) Path to build output (APK files)
bin_dir = ./bin