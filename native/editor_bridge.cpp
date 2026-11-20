// Read-only startup preflight for the pinned Twister authoring build.
#include <windows.h>
#include <winrt/Windows.Data.Json.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Security.Cryptography.h>
#include <winrt/Windows.Security.Cryptography.Core.h>
#include <winrt/Windows.Storage.Streams.h>
#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;
using namespace winrt;
using namespace Windows::Data::Json;
using Windows::Security::Cryptography::CryptographicBuffer;
using Windows::Security::Cryptography::Core::HashAlgorithmProvider;

static_assert(sizeof(void*) == 8, "The editor bridge must be built for x64");
constexpr wchar_t decoder_hash[] = L"da71fa73e838ab3e257a2a73c8f74d88a3336615930761fa494a251822e0c2d5";
constexpr wchar_t editor_hash[] = L"daf356ffae699ca830d6b2bdc3ffe2791908789f0d5671c2f8f448151b6caaa7";

std::string read_request() {
    constexpr size_t limit = 16 * 1024 * 1024;
    std::string input;
    std::array<char, 8192> block;
    while (std::cin.read(block.data(), block.size()) || std::cin.gcount()) {
        if (input.size() + std::cin.gcount() > limit)
            throw std::runtime_error("request exceeds 16 MiB");
        input.append(block.data(), static_cast<size_t>(std::cin.gcount()));
    }
    if (!std::cin.eof() || input.empty()) throw std::runtime_error("cannot read JSON request");
    return input;
}

hstring file_hash(fs::path const& path) {
    if (!fs::is_regular_file(path) || fs::canonical(path) != path)
        throw std::runtime_error("locked file missing or redirected");
    std::ifstream file(path, std::ios::binary);
    auto hash = HashAlgorithmProvider::OpenAlgorithm(L"SHA256").CreateHash();
    std::array<uint8_t, 65536> bytes;
    while (file.read(reinterpret_cast<char*>(bytes.data()), bytes.size()) || file.gcount()) {
        hash.Append(CryptographicBuffer::CreateFromByteArray(
            array_view<uint8_t const>(bytes.data(), bytes.data() + file.gcount())));
    }
    if (!file.eof()) throw std::runtime_error("cannot read locked file");
    return CryptographicBuffer::EncodeToHexString(hash.GetValueAndReset());
}

fs::path request_path(JsonObject const& request, wchar_t const* key) {
    fs::path path(request.GetNamedString(key).c_str());
    if (!path.is_absolute() || path != path.lexically_normal())
        throw std::runtime_error("roots must be canonical absolute paths");
    // The project directory is not created until preflight succeeds. Resolve
    // its existing parent directly without probing unrelated drive ancestors.
    auto existing = fs::exists(path) ? path : path.parent_path();
    if (fs::canonical(existing) != existing)
        throw std::runtime_error("redirected editor or output root");
    return path;
}

bool overlaps(fs::path const& a, fs::path const& b) {
    return std::mismatch(a.begin(), a.end(), b.begin(), b.end(),
        [](fs::path const& x, fs::path const& y) {
            return CompareStringOrdinal(x.c_str(), -1, y.c_str(), -1, TRUE) == CSTR_EQUAL;
        }).first == a.end();
}

int failure(hstring const& stage, hstring const& message, JsonObject const& diagnostics) {
    JsonObject result;
    result.Insert(L"schema_version", JsonValue::CreateNumberValue(1));
    result.Insert(L"status", JsonValue::CreateStringValue(L"error"));
    result.Insert(L"stage", JsonValue::CreateStringValue(stage));
    result.Insert(L"message", JsonValue::CreateStringValue(message));
    result.Insert(L"diagnostics", diagnostics);
    std::cout << to_string(result.Stringify()) << '\n';
    return 1;
}

int preflight(JsonObject const& request, JsonObject const& diagnostics) {
    if (request.GetNamedNumber(L"schema_version") != 1 ||
        request.GetNamedString(L"expected_decoder_sha256") != decoder_hash)
        throw std::runtime_error("unsupported request version or decoder lock");
    if (request.GetNamedNumber(L"deadline_ms") <= 0 ||
        request.GetNamedNumber(L"width") != 128 || request.GetNamedNumber(L"height") != 32 ||
        request.GetNamedNumber(L"native_shades") != 4 || !request.GetNamedArray(L"references").Size())
        throw std::runtime_error("invalid deadline or Twister fixture");

    auto editor = request_path(request, L"editor_root");
    auto project = request_path(request, L"project_root");
    auto config = request_path(request, L"config_root");
    std::array<fs::path, 4> roots{editor, project, config, LR"(C:\vPinball\ColorizingDMD)"};
    for (size_t i = 0; i < roots.size(); ++i) {
        for (size_t j = i + 1; j < roots.size(); ++j) {
            if (overlaps(roots[i], roots[j]) || overlaps(roots[j], roots[i]))
                throw std::runtime_error("editor, installation and output roots must be disjoint");
        }
    }
    if (file_hash(editor / L"ColorizingDMD.exe") != editor_hash)
        return failure(L"editor-lock", L"Staged ColorizingDMD.exe SHA-256 mismatch", diagnostics);
    auto decoder = file_hash(editor / L"serum64.dll");
    diagnostics.Insert(L"decoder_sha256", JsonValue::CreateStringValue(decoder));
    if (decoder != decoder_hash)
        return failure(L"decoder-lock", L"Staged source-tree Serum 2.1.0 SHA-256 mismatch", diagnostics);

    // CreateTextures() returns false when it cannot read this file; wWinMain
    // then exits before loading Serum or entering the message loop.
    if (!fs::is_regular_file(editor / L"textures" / L"chiffres.raw"))
        return failure(L"startup-assets", L"The staged file set lacks textures/chiffres.raw, required by CreateTextures()", diagnostics);
    return failure(L"config-isolation", L"The editor reads and writes HKCU\\SOFTWARE\\ColorizingDMD. An isolated profile is required before launch.", diagnostics);
}

int main() {
    try {
        init_apartment(apartment_type::multi_threaded);
        JsonObject diagnostics;
        diagnostics.Insert(L"editor_launched", JsonValue::CreateBooleanValue(false));
        try {
            return preflight(JsonObject::Parse(to_hstring(read_request())), diagnostics);
        } catch (hresult_error const& error) {
            return failure(L"request", error.message(), diagnostics);
        } catch (std::exception const& error) {
            return failure(L"request", to_hstring(error.what()), diagnostics);
        }
    } catch (...) {
        std::cerr << "Cannot initialize or emit the Windows JSON preflight response\n";
        return 2;
    }
}
