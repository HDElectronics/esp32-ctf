cmake_minimum_required(VERSION 3.22)
# Defuse32 game firmware (hardware/defuse32/FIRMWARE.md).
# App version (esp_app_desc); printed in the boot banner.
set(PROJECT_VER "0.1.0")

# ctf_core from the repo root (key handling, HMAC derivation) + our own components.
set(EXTRA_COMPONENT_DIRS
    "${CMAKE_CURRENT_LIST_DIR}/../../../components/ctf_core"
    "${CMAKE_CURRENT_LIST_DIR}/components")

# Build only what main pulls in (transitively). Keeps sibling components that
# main does not require yet (d32_engine, d32_modules during bring-up) out of
# the build; add them to main's REQUIRES when they are wired in.
set(COMPONENTS main)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(defuse32)
