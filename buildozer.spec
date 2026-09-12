[app]
title = Lunar Drift
package.name = lunardrift
package.domain = org.lunardrift

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy,numpy,android

orientation = portrait

fullscreen = 0

android.permissions = INTERNET,ACCESS_FINE_LOCATION,VIBRATE
android.features = android.hardware.sensor.accelerometer,android.hardware.sensor.gyroscope

android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True

android.logcat_filters = *:S python:D

android.archs = arm64-v8a,armeabi-v7a

android.gradle_dependencies = androidx.appcompat:appcompat:1.4.2

android.entrypoint = org.kivy.android.PythonActivity

android.add_src = src/

android.presplash = 1
android.presplash_lottie = presplash.json

android.meta_data = org.kivy.window=org.kivy.android.PythonActivity

[buildozer]
log_level = 2
warn_on_root = 1
