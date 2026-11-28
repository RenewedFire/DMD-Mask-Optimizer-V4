// Windows x64 host of the pinned Serum 2.3.1 public C ABI. One load per process.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fcntl.h>
#include <io.h>
#include <string>
#include <algorithm>

namespace {
using Byte = std::uint8_t;
using Word = std::uint16_t;
using Dword = std::uint32_t;
constexpr size_t Pixels = 128 * 32;

// Layout from ColorizingDMD/serum.h, with the public tester frameID field.
struct SerumFrame {
    Byte *frame, *palette, *rotations;
    Word *frame32;
    Dword width32;
    Word *rotations32, *rotations_in_frame32;
    Byte *modified32;
    Word *frame64;
    Dword width64;
    Word *rotations64, *rotations_in_frame64;
    Byte *modified64;
    Dword version;
    Byte flags;
    Dword colors, triggers, trigger_id, frame_id, rotation_timer;
};
static_assert(sizeof(void*) == 8 && offsetof(SerumFrame, frame_id) == 124);
struct Header { char magic[4]; Byte version, operation; Word length; };
static_assert(sizeof(Header) == 8);
enum Op : Byte { Frame = 1, Advance = 2, Shutdown = 3, Ready = 4 };
constexpr Dword NoFrame = 0xffffffff;
struct Observation { Dword result, flags, trigger, timer, id, width; };

bool send(Op op, const Observation* obs = nullptr, const Word* pixels = nullptr) {
    Word length = static_cast<Word>((obs ? sizeof(*obs) : 0) + (pixels ? Pixels * 2 : 0));
    Header header{{'D','M','D','W'}, 1, op, length};
    return fwrite(&header, 1, sizeof(header), stdout) == sizeof(header)
        && (!obs || fwrite(obs, 1, sizeof(*obs), stdout) == sizeof(*obs))
        && (!pixels || fwrite(pixels, 2, Pixels, stdout) == Pixels)
        && fflush(stdout) == 0;
}

template<typename T> T symbol(HMODULE module, const char* name) {
    return reinterpret_cast<T>(GetProcAddress(module, name));
}
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 4 || (std::wstring(argv[3]) != L"observe" && std::wstring(argv[3]) != L"production")) return 1;
    bool observe = std::wstring(argv[3]) == L"observe";
    SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
    HMODULE dll = LoadLibraryExW(argv[1], nullptr, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!dll) return 2;
    auto version = symbol<const char* (*)()>(dll, "Serum_GetVersion");
    auto load = symbol<SerumFrame* (*)(const char*, const char*, Byte)>(dll, "Serum_Load");
    auto dispose = symbol<void (*)()>(dll, "Serum_Dispose");
    auto colorize = symbol<Dword (*)(Byte*)>(dll, "Serum_Colorize");
    auto rotate = symbol<Dword (*)()>(dll, "Serum_Rotate");
    if (!version || !load || !dispose || !colorize || !rotate || strcmp(version(), "2.3.1")) return 3;
    auto root = std::filesystem::path(argv[2]).string();
    // The editor requests both resolutions. Rotate also visits its 64p buffers.
    auto* state = load(root.c_str(), "twst_405", 3);
    if (!state || state->colors != 4 || state->width32 != 128 || state->version != 2) return 4;
    struct Cleanup { void (*fn)(); ~Cleanup() { fn(); } } cleanup{dispose};
    if (!send(Ready)) return 5;
    for (;;) {
        Header header{};
        size_t read = fread(&header, 1, sizeof(header), stdin);
        if (!read && feof(stdin)) return 0;
        if (read != sizeof(header) || memcmp(header.magic, "DMDW", 4) || header.version != 1) return 6;
        if (header.operation == Shutdown && header.length == 0) return send(Shutdown) ? 0 : 5;
        Dword result;
        bool wrote_pixels;
        if (header.operation == Frame && header.length == Pixels) {
            std::array<Byte, Pixels> pixels;
            if (fread(pixels.data(), 1, Pixels, stdin) != Pixels
                || *std::max_element(pixels.begin(), pixels.end()) > 3) return 6;
            result = colorize(pixels.data());
            wrote_pixels = result != NoFrame && (state->flags & 1);
        } else if (header.operation == Advance && header.length == sizeof(Dword)) {
            Dword ms;
            if (fread(&ms, 1, sizeof(ms), stdin) != sizeof(ms) || ms > 60000) return 6;
            Sleep(ms);
            result = rotate();
            wrote_pixels = (result & 0x10000) && result != NoFrame;
        } else {
            return 6;
        }
        if (wrote_pixels && (!state->frame32 || state->width32 != 128)) return 7;
        Observation observation{result, state->flags, state->trigger_id, state->rotation_timer,
            observe && header.operation == Frame ? state->frame_id : NoFrame, state->width32};
        if (!send(static_cast<Op>(header.operation), &observation, wrote_pixels ? state->frame32 : nullptr)) return 5;
    }
}
