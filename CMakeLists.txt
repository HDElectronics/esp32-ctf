cmake_minimum_required(VERSION 3.22)
# App version (esp_app_desc); keep equal to CTF_FW_VERSION in ctf_platform.h.
set(PROJECT_VER "0.2.1")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32_ctf)
