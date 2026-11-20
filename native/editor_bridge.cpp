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
#include <functional>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <system_error>
#include <vector>

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

namespace {
constexpr wchar_t settings_key[] = L"ColorizingDMD";
using Bytes = std::vector<BYTE>;
using Values = std::map<std::wstring, std::pair<DWORD, Bytes>>;
// Empty map: subtree absent. Empty relative path: the subtree's root.
using RegistryTree = std::map<std::wstring, Values>;

struct CloseKey {
    void operator()(HKEY key) const noexcept { RegCloseKey(key); }
};
using Key = std::unique_ptr<std::remove_pointer_t<HKEY>, CloseKey>;

void check_registry(LSTATUS status, char const* operation) {
    if (status != ERROR_SUCCESS)
        throw std::system_error(status, std::system_category(), operation);
}

Key open_key(HKEY parent, wchar_t const* name, bool allow_absent = false) {
    HKEY handle{};
    auto status = RegOpenKeyExW(parent, name, REG_OPTION_OPEN_LINK, KEY_READ, &handle);
    if (allow_absent && status == ERROR_FILE_NOT_FOUND) return {};
    check_registry(status, "open registry key");
    return Key(handle);
}

Key create_key(HKEY parent, std::wstring const& name) {
    HKEY handle{};
    check_registry(RegCreateKeyExW(parent, name.c_str(), 0, nullptr, REG_OPTION_NON_VOLATILE,
        KEY_READ | KEY_WRITE, nullptr, &handle, nullptr), "create registry key");
    return Key(handle);
}

void enumerate_key(HKEY key, std::wstring const& path, RegistryTree& tree) {
    DWORD max_child{}, max_name{}, max_data{};
    check_registry(RegQueryInfoKeyW(key, nullptr, nullptr, nullptr, nullptr, &max_child, nullptr,
        nullptr, &max_name, &max_data, nullptr, nullptr), "size registry key");
    std::vector<wchar_t> name(1ULL + (std::max)(max_name, max_child));
    Bytes data((std::max)(max_data, 1UL));
    auto& values = tree[path];
    for (DWORD i = 0; ; ++i) {
        DWORD length = static_cast<DWORD>(name.size()), size = static_cast<DWORD>(data.size()), type{};
        auto status = RegEnumValueW(key, i, name.data(), &length, nullptr, &type, data.data(), &size);
        if (status == ERROR_NO_MORE_ITEMS) break;
        check_registry(status, "read registry value");
        std::wstring value_name(name.data(), length);
        if (type == REG_LINK && _wcsicmp(value_name.c_str(), L"SymbolicLinkValue") == 0)
            throw std::runtime_error("registry link inside editor settings");
        values.emplace(std::move(value_name), std::make_pair(type, Bytes(data.begin(), data.begin() + size)));
    }
    for (DWORD i = 0; ; ++i) {
        DWORD length = static_cast<DWORD>(name.size());
        auto status = RegEnumKeyExW(key, i, name.data(), &length, nullptr, nullptr, nullptr, nullptr);
        if (status == ERROR_NO_MORE_ITEMS) break;
        check_registry(status, "enumerate registry subkey");
        std::wstring child(name.data(), length);
        auto subkey = open_key(key, child.c_str());
        enumerate_key(subkey.get(), path.empty() ? child : path + L"\\" + child, tree);
    }
}

RegistryTree read_settings(HKEY software) {
    RegistryTree tree;
    if (auto key = open_key(software, settings_key, true)) enumerate_key(key.get(), L"", tree);
    return tree;
}

JsonObject snapshot_json(RegistryTree const& tree) {
    JsonObject keys;
    for (auto const& [path, values] : tree) {
        JsonObject entries;
        for (auto const& [name, value] : values) {
            JsonObject entry;
            entry.Insert(L"type", JsonValue::CreateNumberValue(value.first));
            auto buffer = CryptographicBuffer::CreateFromByteArray(value.second);
            entry.Insert(L"hex", JsonValue::CreateStringValue(CryptographicBuffer::EncodeToHexString(buffer)));
            entries.Insert(name, entry);
        }
        keys.Insert(path, entries);
    }
    JsonObject snapshot;
    snapshot.Insert(L"schema_version", JsonValue::CreateNumberValue(1));
    snapshot.Insert(L"existed", JsonValue::CreateBooleanValue(!tree.empty()));
    snapshot.Insert(L"keys", keys);
    return snapshot;
}

void write_new_json(fs::path const& path, JsonObject const& json) {
    auto serialized = json.Stringify();
    auto bytes = to_string(serialized);
    if (to_hstring(bytes) != serialized || bytes.size() > MAXDWORD)
        throw std::runtime_error("cannot encode registry artifact losslessly");
    // CREATE_NEW refuses existing artifacts, including links and hard links.
    winrt::file_handle file(CreateFileW(path.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr,
        CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr));
    if (!file) throw std::system_error(GetLastError(), std::system_category(), "create registry artifact");
    DWORD length{};
    if (!WriteFile(file.get(), bytes.data(), static_cast<DWORD>(bytes.size()), &length, nullptr)
        || length != bytes.size() || !FlushFileBuffers(file.get()))
        throw std::system_error(GetLastError(), std::system_category(), "persist registry artifact");
}

void restore_settings(HKEY software, RegistryTree const& before) {
    // Refuse any links added during the editor operation before traversing a
    // subtree for deletion. All calls are anchored to the injected SOFTWARE key.
    auto current = read_settings(software);
    if (current == before) return;
    if (!current.empty())
        check_registry(RegDeleteTreeW(software, settings_key), "remove temporary editor settings");
    if (before.empty()) return;
    auto root = create_key(software, settings_key);
    for (auto const& [path, values] : before) {
        auto child = path.empty() ? Key{} : create_key(root.get(), path);
        for (auto const& [name, value] : values) {
            check_registry(RegSetValueExW(child ? child.get() : root.get(), name.c_str(), 0,
                value.first, value.second.data(), static_cast<DWORD>(value.second.size())),
                "restore registry value");
        }
    }
}
} // namespace

// The caller supplies HKCU\SOFTWARE after obtaining exclusive ownership.
// Tests supply a private app hive. There is no request-controlled registry path.
void with_registry_transaction(HKEY software, fs::path const& config,
    std::map<std::wstring, std::wstring> const& temporary_paths, JsonObject const& observations,
    std::function<void()> const& run) {
    if (!config.is_absolute() || !fs::is_directory(config) || fs::canonical(config) != config)
        throw std::runtime_error("registry artifacts require a canonical generated directory");
    for (fs::path installation : {LR"(C:\DMD Colorization\ColorizingDMD)", LR"(C:\vPinball\ColorizingDMD)"}) {
        if (overlaps(config, installation) || overlaps(installation, config))
            throw std::runtime_error("registry artifacts overlap an editor installation");
    }
    auto snapshot = config / L"registry-snapshot.json";
    auto marker = config / L"registry-incomplete.json";
    JsonObject evidence;
    evidence.Insert(L"snapshot_path", JsonValue::CreateStringValue(snapshot.native()));
    evidence.Insert(L"marker_path", JsonValue::CreateStringValue(marker.native()));
    evidence.Insert(L"verified", JsonValue::CreateBooleanValue(false));
    observations.Insert(L"registry_transaction", evidence);
    auto before = read_settings(software);
    write_new_json(snapshot, snapshot_json(before));
    JsonObject incomplete;
    incomplete.Insert(L"schema_version", JsonValue::CreateNumberValue(1));
    incomplete.Insert(L"snapshot", JsonValue::CreateStringValue(snapshot.filename().native()));
    write_new_json(marker, incomplete);

    std::exception_ptr operation_error;
    try {
        {
            auto key = create_key(software, settings_key);
            for (auto const& [name, value] : temporary_paths) {
                auto length = static_cast<DWORD>((value.size() + 1) * sizeof(wchar_t));
                check_registry(RegSetValueExW(key.get(), name.c_str(), 0, REG_SZ,
                    reinterpret_cast<BYTE const*>(value.c_str()), length), "apply temporary editor path");
            }
        }
        run();
    } catch (...) {
        operation_error = std::current_exception();
    }
    restore_settings(software, before);
    if (read_settings(software) != before)
        throw std::runtime_error("restored registry differs from snapshot");
    if (!DeleteFileW(marker.c_str()))
        throw std::system_error(GetLastError(), std::system_category(), "remove registry marker");
    evidence.SetNamedValue(L"verified", JsonValue::CreateBooleanValue(true));
    if (operation_error) std::rethrow_exception(operation_error);
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
