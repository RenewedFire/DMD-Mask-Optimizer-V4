// Read-only startup preflight for the pinned Twister authoring build.
#include <windows.h>
#include <sddl.h>
#include <tlhelp32.h>
#include <winrt/Windows.Data.Json.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Security.Cryptography.h>
#include <winrt/Windows.Security.Cryptography.Core.h>
#include <winrt/Windows.Storage.Streams.h>
#include <algorithm>
#include <array>
#include <charconv>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <functional>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
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

struct RegistrySnapshot {
    std::wstring root_name;
    RegistryTree keys;
    bool operator==(RegistrySnapshot const&) const = default;
};

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

std::wstring restorable_name(wchar_t const* buffer, DWORD length) {
    std::wstring name(buffer, length);
    if (name.find(L'\0') != std::wstring::npos)
        throw std::runtime_error("registry name contains an embedded NUL and cannot be restored");
    return name;
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
        auto value_name = restorable_name(name.data(), length);
        if (type == REG_LINK && _wcsicmp(value_name.c_str(), L"SymbolicLinkValue") == 0)
            throw std::runtime_error("registry link inside editor settings");
        values.emplace(std::move(value_name), std::make_pair(type, Bytes(data.begin(), data.begin() + size)));
    }
    for (DWORD i = 0; ; ++i) {
        DWORD length = static_cast<DWORD>(name.size());
        auto status = RegEnumKeyExW(key, i, name.data(), &length, nullptr, nullptr, nullptr, nullptr);
        if (status == ERROR_NO_MORE_ITEMS) break;
        check_registry(status, "enumerate registry subkey");
        auto child = restorable_name(name.data(), length);
        auto subkey = open_key(key, child.c_str());
        enumerate_key(subkey.get(), path.empty() ? child : path + L"\\" + child, tree);
    }
}

RegistrySnapshot read_settings(HKEY software) {
    RegistrySnapshot snapshot;
    auto key = open_key(software, settings_key, true);
    if (!key) return snapshot;
    // Opening a registry key ignores case. Enumerate its parent to preserve
    // the spelling that should be recreated even if the editor removes it.
    DWORD max_name{};
    check_registry(RegQueryInfoKeyW(software, nullptr, nullptr, nullptr, nullptr, &max_name,
        nullptr, nullptr, nullptr, nullptr, nullptr, nullptr), "size registry parent");
    std::vector<wchar_t> name(1ULL + max_name);
    for (DWORD i = 0; ; ++i) {
        DWORD length = static_cast<DWORD>(name.size());
        auto status = RegEnumKeyExW(software, i, name.data(), &length, nullptr, nullptr, nullptr, nullptr);
        check_registry(status, "find original editor key name");
        if (length == std::size(settings_key) - 1 &&
            CompareStringOrdinal(name.data(), length, settings_key, -1, TRUE) == CSTR_EQUAL) {
            snapshot.root_name = restorable_name(name.data(), length);
            break;
        }
    }
    enumerate_key(key.get(), L"", snapshot.keys);
    return snapshot;
}

JsonObject snapshot_json(RegistrySnapshot const& before) {
    JsonObject keys;
    for (auto const& [path, values] : before.keys) {
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
    snapshot.Insert(L"existed", JsonValue::CreateBooleanValue(!before.keys.empty()));
    snapshot.Insert(L"root_name", JsonValue::CreateStringValue(before.root_name));
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

void restore_settings(HKEY software, RegistrySnapshot const& before) {
    // Refuse any links added during the editor operation before traversing a
    // subtree for deletion. All calls are anchored to the injected SOFTWARE key.
    auto current = read_settings(software);
    if (current == before) return;
    if (!current.keys.empty())
        check_registry(RegDeleteTreeW(software, settings_key), "remove temporary editor settings");
    if (before.keys.empty()) return;
    auto root = create_key(software, before.root_name);
    for (auto const& [path, values] : before.keys) {
        auto child = path.empty() ? Key{} : create_key(root.get(), path);
        for (auto const& [name, value] : values) {
            check_registry(RegSetValueExW(child ? child.get() : root.get(), name.c_str(), 0,
                value.first, value.second.data(), static_cast<DWORD>(value.second.size())),
                "restore registry value");
        }
    }
}

void finish_restoration(HKEY software, RegistrySnapshot const& before, fs::path const& marker) {
    restore_settings(software, before);
    if (read_settings(software) != before)
        throw std::runtime_error("restored registry differs from snapshot");
    check_registry(RegFlushKey(software), "persist restored editor settings");
    if (!DeleteFileW(marker.c_str()))
        throw std::system_error(GetLastError(), std::system_category(), "remove registry marker");
}

// Open a single immutable view for both digest verification and JSON parsing.
// A dangling reparse point is an error as well, never an absent marker.
bool artifact_exists(fs::path const& path) {
    auto attrs = GetFileAttributesW(path.c_str());
    if (attrs == INVALID_FILE_ATTRIBUTES) {
        auto error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) return false;
        throw std::system_error(error, std::system_category(), "inspect registry journal");
    }
    if (attrs & FILE_ATTRIBUTE_REPARSE_POINT)
        throw std::runtime_error("redirected registry journal");
    return true;
}

JsonObject read_journal_json(fs::path const& path, hstring const* expected_hash = nullptr) {
    if (!artifact_exists(path) || !fs::is_regular_file(path) || fs::canonical(path) != path)
        throw std::runtime_error("registry journal artifact is missing or redirected");
    file_handle file(CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
        OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, nullptr));
    if (!file) throw std::system_error(GetLastError(), std::system_category(), "read registry journal");
    BY_HANDLE_FILE_INFORMATION info{};
    if (!GetFileInformationByHandle(file.get(), &info))
        throw std::system_error(GetLastError(), std::system_category(), "inspect registry artifact");
    if (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT || info.nNumberOfLinks != 1 ||
        info.nFileSizeHigh || !info.nFileSizeLow)
        throw std::runtime_error("invalid registry journal artifact");
    std::string bytes(info.nFileSizeLow, '\0');
    DWORD count{};
    if (!ReadFile(file.get(), bytes.data(), info.nFileSizeLow, &count, nullptr) || count != bytes.size())
        throw std::runtime_error("cannot read registry journal");
    if (expected_hash) {
        auto data = reinterpret_cast<uint8_t const*>(bytes.data());
        auto buffer = CryptographicBuffer::CreateFromByteArray({data, data + count});
        auto digest = HashAlgorithmProvider::OpenAlgorithm(L"SHA256").HashData(buffer);
        if (CryptographicBuffer::EncodeToHexString(digest) != *expected_hash)
            throw std::runtime_error("registry snapshot digest mismatch");
    }
    auto encoded = to_hstring(bytes);
    if (to_string(encoded) != bytes) throw std::runtime_error("invalid UTF-8 registry journal");
    return JsonObject::Parse(encoded);
}

struct RegistryNameLess {
    bool operator()(std::wstring const& a, std::wstring const& b) const {
        return CompareStringOrdinal(a.c_str(), -1, b.c_str(), -1, TRUE) == CSTR_LESS_THAN;
    }
};

RegistrySnapshot parse_snapshot(JsonObject const& json) {
    if (json.GetNamedNumber(L"schema_version") != 1) throw std::runtime_error("unsupported registry snapshot");
    bool existed = json.GetNamedBoolean(L"existed");
    auto root = json.GetNamedString(L"root_name", existed ? settings_key : L"");
    RegistrySnapshot result{restorable_name(root.c_str(), root.size()), {}};
    if (existed ? _wcsicmp(result.root_name.c_str(), settings_key) != 0 : !result.root_name.empty())
        throw std::runtime_error("invalid registry snapshot root");
    std::set<std::wstring, RegistryNameLess> paths;
    for (auto const& key : json.GetNamedObject(L"keys")) {
        auto name = key.Key();
        auto path = restorable_name(name.c_str(), name.size());
        if (!paths.insert(path).second || (!path.empty() && (path.front() == L'\\' ||
            path.back() == L'\\' || path.find(L"\\\\") != path.npos)))
            throw std::runtime_error("invalid registry snapshot subkey");
        auto& values = result.keys[path];
        std::set<std::wstring, RegistryNameLess> names;
        for (auto const& entry : key.Value().GetObject()) {
            auto raw_name = entry.Key();
            auto value_name = restorable_name(raw_name.c_str(), raw_name.size());
            auto value = entry.Value().GetObject();
            double type = value.GetNamedNumber(L"type");
            if (!names.insert(value_name).second || type < 0 || type > MAXDWORD || std::floor(type) != type ||
                (type == REG_LINK && _wcsicmp(value_name.c_str(), L"SymbolicLinkValue") == 0))
                throw std::runtime_error("invalid registry snapshot value");
            auto buffer = CryptographicBuffer::DecodeFromHexString(value.GetNamedString(L"hex"));
            com_array<uint8_t> data;
            CryptographicBuffer::CopyToByteArray(buffer, data);
            values.emplace(value_name, std::make_pair(static_cast<DWORD>(type), Bytes(data.begin(), data.end())));
        }
    }
    if (existed != !result.keys.empty() || (existed && !result.keys.contains(L"")))
        throw std::runtime_error("inconsistent registry snapshot existence");
    for (auto const& [path, values] : result.keys) {
        auto split = path.rfind(L'\\');
        if (split != path.npos && !result.keys.contains(path.substr(0, split)))
            throw std::runtime_error("missing registry snapshot parent");
    }
    return result;
}

void require_editor_stopped() {
    file_handle snapshot(CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0));
    if (!snapshot) throw std::system_error(GetLastError(), std::system_category(), "list editor processes");
    PROCESSENTRY32W process{sizeof(PROCESSENTRY32W)};
    if (!Process32FirstW(snapshot.get(), &process))
        throw std::system_error(GetLastError(), std::system_category(), "inspect editor processes");
    do {
        if (_wcsicmp(process.szExeFile, L"ColorizingDMD.exe") == 0)
            throw std::runtime_error("ColorizingDMD.exe is already running");
    } while (Process32NextW(snapshot.get(), &process));
    if (GetLastError() != ERROR_NO_MORE_FILES)
        throw std::system_error(GetLastError(), std::system_category(), "enumerate editor processes");
}

void validate_journal(fs::path const& journal) {
    if (!journal.is_absolute() || journal != journal.lexically_normal())
        throw std::runtime_error("registry journal requires a canonical directory");
    // The first run has no journal yet. Resolve its nearest existing directory
    // directly without requiring permission to enumerate the drive root.
    auto existing = journal;
    while (!artifact_exists(existing)) {
        if (existing == existing.root_path()) throw std::runtime_error("registry journal root is missing");
        existing = existing.parent_path();
    }
    if (!fs::is_directory(existing) || fs::canonical(existing) != existing)
        throw std::runtime_error("registry journal requires a canonical directory");
    for (fs::path installation : {LR"(C:\DMD Colorization\ColorizingDMD)", LR"(C:\vPinball\ColorizingDMD)"})
        if (overlaps(journal, installation) || overlaps(installation, journal))
            throw std::runtime_error("registry journal overlaps an editor installation");
}

std::wstring editor_job_name(std::wstring_view run) {
    return std::wstring(L"Global\\DMDMaskOptimizer-EditorJob-").append(run);
}

struct JobExitUnconfirmed : std::runtime_error {
    using std::runtime_error::runtime_error;
};

JOBOBJECT_BASIC_ACCOUNTING_INFORMATION job_accounting(HANDLE job) {
    JOBOBJECT_BASIC_ACCOUNTING_INFORMATION info{};
    if (!QueryInformationJobObject(job, JobObjectBasicAccountingInformation, &info, sizeof(info), nullptr))
        throw JobExitUnconfirmed("cannot confirm editor job process count");
    return info;
}

uint64_t process_creation_time(HANDLE process) {
    FILETIME creation{}, exit{}, kernel{}, user{};
    if (!GetProcessTimes(process, &creation, &exit, &kernel, &user))
        throw JobExitUnconfirmed("cannot read editor job process identity");
    return (static_cast<uint64_t>(creation.dwHighDateTime) << 32) | creation.dwLowDateTime;
}

handle open_job_process(DWORD pid) {
    handle process(OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, FALSE, pid));
    if (!process && GetLastError() != ERROR_INVALID_PARAMETER)
        throw JobExitUnconfirmed("cannot open editor job process");
    return process;
}

bool process_exited(HANDLE process, DWORD timeout) {
    DWORD result = WaitForSingleObject(process, timeout);
    if (result != WAIT_OBJECT_0 && result != WAIT_TIMEOUT)
        throw JobExitUnconfirmed("cannot confirm editor job process exit");
    return result == WAIT_OBJECT_0;
}

void require_prior_job_exited(JsonObject const& marker) {
    auto processes = marker.GetNamedValue(L"editor_processes", JsonValue::CreateNullValue());
    if (processes.ValueType() != JsonValueType::Array)
        throw JobExitUnconfirmed("interrupted editor job has no complete shutdown evidence");
    for (auto const& entry : processes.GetArray()) {
        auto identity = entry.GetObject();
        double pid = identity.GetNamedNumber(L"pid");
        auto time = to_string(identity.GetNamedString(L"creation_time"));
        uint64_t creation{};
        auto [end, error] = std::from_chars(time.data(), time.data() + time.size(), creation);
        if (!std::isfinite(pid) || pid < 1 || pid > MAXDWORD || std::floor(pid) != pid ||
            error != std::errc{} || end != time.data() + time.size() || !creation)
            throw JobExitUnconfirmed("invalid editor job process identity");
        auto process = open_job_process(static_cast<DWORD>(pid));
        if (process && process_creation_time(process.get()) == creation && !process_exited(process.get(), 0))
            throw JobExitUnconfirmed("interrupted editor job still has active processes");
    }
}

int with_editor_isolation(fs::path const& journal, wchar_t const* lock,
    std::function<HKEY()> const& software, JsonObject const& diagnostics, std::function<int()> const& run) {
    // Object lifetime, including kernel cleanup on process termination, owns the lock.
    handle owner(CreateEventW(nullptr, TRUE, FALSE, lock));
    auto status = GetLastError();
    if (!owner || status == ERROR_ALREADY_EXISTS)
        throw std::system_error(status, std::system_category(), "exclusive editor bridge ownership");
    require_editor_stopped();
    validate_journal(journal);
    auto marker = journal / L"registry-incomplete.json";
    JsonObject evidence;
    evidence.Insert(L"restored", JsonValue::CreateBooleanValue(false));
    evidence.Insert(L"marker_path", JsonValue::CreateStringValue(marker.native()));
    diagnostics.Insert(L"registry_recovery", evidence);
    if (artifact_exists(marker)) {
        auto record = read_journal_json(marker);
        auto run_id = record.GetNamedString(L"run");
        if (run_id.empty() || std::wstring_view(run_id).find_first_not_of(
            L"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_") != std::wstring_view::npos)
            throw std::runtime_error("invalid registry journal run name");
        if (record.GetNamedNumber(L"schema_version") != 1 ||
            record.GetNamedString(L"snapshot") != L"registry-snapshot.json")
            throw std::runtime_error("invalid registry journal marker");
        auto previous = journal / run_id.c_str();
        if (!artifact_exists(previous) || !fs::is_directory(previous))
            throw std::runtime_error("missing registry journal run");
        auto snapshot = previous / L"registry-snapshot.json";
        evidence.Insert(L"snapshot_path", JsonValue::CreateStringValue(snapshot.native()));
        auto digest = record.GetNamedString(L"sha256");
        auto before = parse_snapshot(read_journal_json(snapshot, &digest));
        // Closing the last job handle can remove its name before members exit.
        require_prior_job_exited(record);
        require_editor_stopped();
        // Recovery of an already published marker precedes request validation.
        // It may restore the old snapshot, never prepare a new transaction.
        finish_restoration(software(), before, marker);
        evidence.SetNamedValue(L"restored", JsonValue::CreateBooleanValue(true));
    }
    return run();
}
} // namespace

// The caller supplies HKCU\SOFTWARE after obtaining exclusive ownership.
// Tests supply a private app hive. There is no request-controlled registry path.
void with_registry_transaction(HKEY software, fs::path const& run_root, fs::path const& config,
    std::map<std::wstring, std::wstring> const& temporary_paths, JsonObject const& observations,
    std::function<void()> const& run, fs::path const& journal = {}) {
    for (auto const& dir : {run_root, config}) {
        if (!dir.is_absolute() || !fs::is_directory(dir) || fs::canonical(dir) != dir)
            throw std::runtime_error("registry artifacts require canonical generated directories");
    }
    if (std::mismatch(run_root.begin(), run_root.end(), config.begin(), config.end()).first != run_root.end())
        throw std::runtime_error("registry artifacts must be inside the generated run root");
    for (fs::path installation : {LR"(C:\DMD Colorization\ColorizingDMD)", LR"(C:\vPinball\ColorizingDMD)"}) {
        if (overlaps(config, installation) || overlaps(installation, config))
            throw std::runtime_error("registry artifacts overlap an editor installation");
    }
    auto snapshot = config / L"registry-snapshot.json";
    auto marker = (journal.empty() ? config : journal) / L"registry-incomplete.json";
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
    if (!journal.empty()) {
        incomplete.Insert(L"run", JsonValue::CreateStringValue(config.filename().native()));
        incomplete.Insert(L"sha256", JsonValue::CreateStringValue(file_hash(snapshot)));
        incomplete.Insert(L"editor_processes", JsonArray{});
    }
    // A terminated writer can leave a partial file in its own run directory.
    // Recovery sees the marker only after the complete record has been flushed.
    auto pending = config / L"registry-incomplete.pending";
    write_new_json(pending, incomplete);
    if (!MoveFileExW(pending.c_str(), marker.c_str(), MOVEFILE_WRITE_THROUGH))
        throw std::system_error(GetLastError(), std::system_category(), "publish registry marker");

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
    } catch (JobExitUnconfirmed const&) {
        // Leave both the durable marker and temporary settings intact until
        // recovery can establish that no member of the editor job remains.
        throw;
    } catch (...) {
        operation_error = std::current_exception();
    }
    finish_restoration(software, before, marker);
    evidence.SetNamedValue(L"verified", JsonValue::CreateBooleanValue(true));
    if (operation_error) std::rethrow_exception(operation_error);
}

void with_journaled_transaction(HKEY software, fs::path const& journal,
    std::map<std::wstring, std::wstring> const& temporary_paths, JsonObject const& observations,
    std::function<void(fs::path const&)> const& run) {
    validate_journal(journal);
    fs::create_directories(journal);
    std::wstring id(CryptographicBuffer::EncodeToHexString(CryptographicBuffer::GenerateRandom(16)));
    auto dir = journal / id;
    if (!fs::create_directory(dir)) throw std::runtime_error("registry journal run already exists");
    with_registry_transaction(software, journal, dir, temporary_paths, observations, [&] { run(dir); }, journal);
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

// Canonical inventory of the authoring files in twst_405.json: sorted lowercase
// editor-relative paths, one UTF-8 "path sha256\n" line per file.
void verify_launch_inventory(fs::path const& editor) {
    std::map<std::string, std::string> files;
    for (auto const& entry : fs::recursive_directory_iterator(editor)) {
        if (!artifact_exists(entry.path())) throw std::runtime_error("staged file disappeared");
        if (entry.is_directory()) continue;
        auto name = entry.path().lexically_relative(editor).generic_string();
        std::transform(name.begin(), name.end(), name.begin(), [](unsigned char c) {
            return char(c >= 'A' && c <= 'Z' ? c + ('a' - 'A') : c);
        });
        if (!files.emplace(name, to_string(file_hash(entry.path()))).second)
            throw std::runtime_error("duplicate staged editor file");
    }
    std::string inventory;
    for (auto const& [name, digest] : files) inventory += name + " " + digest + "\n";
    auto data = reinterpret_cast<uint8_t const*>(inventory.data());
    auto buffer = CryptographicBuffer::CreateFromByteArray({data, data + inventory.size()});
    auto digest = HashAlgorithmProvider::OpenAlgorithm(L"SHA256").HashData(buffer);
    if (CryptographicBuffer::EncodeToHexString(digest) !=
        L"855eb895f1c3e484bfa31b50f75a6bc0ed1c1806eba4d3c19d445ebb0c35d99f")
        throw std::runtime_error("staged editor inventory differs from the locked authoring files");
}

struct WindowObservation {
    DWORD pid;
    std::vector<std::wstring> titles;
};

BOOL CALLBACK observe_window(HWND window, LPARAM context) {
    auto& observation = *reinterpret_cast<WindowObservation*>(context);
    DWORD pid{};
    GetWindowThreadProcessId(window, &pid);
    if (pid == observation.pid && IsWindowVisible(window)) {
        wchar_t title[256]{};
        if (GetWindowTextW(window, title, 256)) observation.titles.emplace_back(title);
    }
    return TRUE;
}

void publish_job_evidence(fs::path const& run, JsonObject const& marker, wchar_t const* staging_name,
    IJsonValue const& processes) {
    marker.SetNamedValue(L"editor_processes", processes);
    auto staged = run / staging_name;
    write_new_json(staged, marker);
    auto destination = run.parent_path() / L"registry-incomplete.json";
    if (!MoveFileExW(staged.c_str(), destination.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        throw std::system_error(GetLastError(), std::system_category(), "publish editor job evidence");
}

void record_process_identity(JsonArray const& identities, DWORD pid, HANDLE process) {
    JsonObject identity;
    identity.Insert(L"pid", JsonValue::CreateNumberValue(pid));
    identity.Insert(L"creation_time", JsonValue::CreateStringValue(std::to_wstring(process_creation_time(process))));
    identities.Append(identity);
}

std::vector<handle> capture_job_processes(HANDLE job, DWORD main_pid, JsonArray const& identities) {
    // Admit zero additional runnable processes, including descendants. Record
    // the shrinking membership before initiating termination or closing the job.
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
    limits.BasicLimitInformation.ActiveProcessLimit = 0;
    if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof(limits)))
        throw JobExitUnconfirmed("cannot stop editor job process admission");

    constexpr auto offset = offsetof(JOBOBJECT_BASIC_PROCESS_ID_LIST, ProcessIdList);
    std::vector<BYTE> buffer(offset + 16 * sizeof(ULONG_PTR));
    for (;;) {
        if (QueryInformationJobObject(job, JobObjectBasicProcessIdList, buffer.data(),
            static_cast<DWORD>(buffer.size()), nullptr)) break;
        if (GetLastError() != ERROR_MORE_DATA || buffer.size() > MAXDWORD / 2)
            throw JobExitUnconfirmed("cannot enumerate editor job processes");
        buffer.resize(buffer.size() * 2);
    }
    auto const& list = *reinterpret_cast<JOBOBJECT_BASIC_PROCESS_ID_LIST const*>(buffer.data());
    if (list.NumberOfAssignedProcesses != list.NumberOfProcessIdsInList ||
        list.NumberOfProcessIdsInList > (buffer.size() - offset) / sizeof(ULONG_PTR))
        throw JobExitUnconfirmed("incomplete editor job process list");

    std::vector<handle> processes;
    for (DWORD i = 0; i < list.NumberOfProcessIdsInList; ++i) {
        ULONG_PTR pid{};
        std::memcpy(&pid, buffer.data() + offset + i * sizeof(pid), sizeof(pid));
        if (!pid || pid > MAXDWORD) throw JobExitUnconfirmed("invalid editor job process ID");
        if (pid == main_pid) continue; // The caller already owns this process handle.
        auto process = open_job_process(static_cast<DWORD>(pid));
        if (!process) continue;
        BOOL member{};
        if (!IsProcessInJob(process.get(), job, &member))
            throw JobExitUnconfirmed("cannot verify editor job process membership");
        if (!member) continue; // The recorded PID had exited and was reused.
        record_process_identity(identities, static_cast<DWORD>(pid), process.get());
        processes.push_back(std::move(process));
    }
    return processes;
}

void bounded_startup(fs::path const& editor, DWORD duration, JsonObject const& diagnostics, fs::path const& run) {
    auto job_name = editor_job_name(run.filename().native());
    handle job(CreateJobObjectW(nullptr, job_name.c_str()));
    auto status = GetLastError();
    check_bool(bool(job));
    if (status == ERROR_ALREADY_EXISTS) throw std::runtime_error("editor job already exists");
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    check_bool(SetInformationJobObject(job.get(), JobObjectExtendedLimitInformation, &limits, sizeof(limits)));
    // Assign at creation so interruption cannot leave an unowned editor.
    SIZE_T size{};
    InitializeProcThreadAttributeList(nullptr, 1, 0, &size);
    std::vector<BYTE> storage(size);
    auto attributes = reinterpret_cast<PPROC_THREAD_ATTRIBUTE_LIST>(storage.data());
    check_bool(InitializeProcThreadAttributeList(attributes, 1, 0, &size));
    struct AttributeCleanup {
        PPROC_THREAD_ATTRIBUTE_LIST list;
        ~AttributeCleanup() { DeleteProcThreadAttributeList(list); }
    } cleanup{attributes};
    HANDLE jobs[]{job.get()};
    check_bool(UpdateProcThreadAttribute(attributes, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST,
        jobs, sizeof(jobs), nullptr, nullptr));
    STARTUPINFOEXW startup{};
    startup.StartupInfo.cb = sizeof(startup);
    startup.lpAttributeList = attributes;
    PROCESS_INFORMATION child{};
    auto marker = read_journal_json(run.parent_path() / L"registry-incomplete.json");
    // Null marks the window in which a process may run but its full job
    // membership is still unknown. Recovery must retain the snapshot then.
    publish_job_evidence(run, marker, L"editor-launch.pending", JsonValue::CreateNullValue());
    check_bool(CreateProcessW((editor / L"ColorizingDMD.exe").c_str(), nullptr, nullptr, nullptr, FALSE,
        EXTENDED_STARTUPINFO_PRESENT, nullptr, editor.c_str(), &startup.StartupInfo, &child));
    handle process(child.hProcess), thread(child.hThread);
    std::exception_ptr observation_error;
    try {
        diagnostics.SetNamedValue(L"editor_launched", JsonValue::CreateBooleanValue(true));
        diagnostics.Insert(L"editor_pid", JsonValue::CreateNumberValue(child.dwProcessId));
        diagnostics.Insert(L"observation_ms", JsonValue::CreateNumberValue(duration));
        DWORD wait = WaitForSingleObject(process.get(), duration);
        if (wait != WAIT_OBJECT_0 && wait != WAIT_TIMEOUT) throw_last_error();
        diagnostics.Insert(L"running_at_deadline", JsonValue::CreateBooleanValue(wait == WAIT_TIMEOUT));
        WindowObservation observation{child.dwProcessId, {}};
        check_bool(EnumWindows(observe_window, reinterpret_cast<LPARAM>(&observation)));
        JsonArray titles;
        for (auto const& title : observation.titles) titles.Append(JsonValue::CreateStringValue(title));
        diagnostics.Insert(L"visible_window_titles", titles);
    } catch (...) {
        observation_error = std::current_exception();
    }
    // A signaled main process says nothing about descendants. Keep the job
    // handle until all members have exited, including on observation errors.
    std::vector<handle> members;
    try {
        JsonArray identities;
        record_process_identity(identities, child.dwProcessId, process.get());
        members = capture_job_processes(job.get(), child.dwProcessId, identities);
        publish_job_evidence(run, marker, L"editor-shutdown.pending", identities);
    } catch (JobExitUnconfirmed const&) {
        throw;
    } catch (...) {
        throw JobExitUnconfirmed("cannot persist complete editor job shutdown evidence");
    }
    if (!TerminateJobObject(job.get(), ERROR_PROCESS_ABORTED))
        throw JobExitUnconfirmed("cannot terminate editor job");
    auto deadline = GetTickCount64() + 5000;
    auto info = job_accounting(job.get());
    while (info.ActiveProcesses) {
        if (GetTickCount64() >= deadline) throw JobExitUnconfirmed("editor job termination timed out");
        Sleep(10);
        info = job_accounting(job.get());
    }
    // Accounting can reach zero immediately before a process handle signals.
    auto wait_for_exit = [&](HANDLE object) {
        auto now = GetTickCount64();
        DWORD remaining = now < deadline ? static_cast<DWORD>(deadline - now) : 0;
        if (!process_exited(object, remaining)) throw JobExitUnconfirmed("editor job process termination timed out");
    };
    for (auto const& member : members) wait_for_exit(member.get());
    wait_for_exit(process.get());
    diagnostics.Insert(L"job_active_processes", JsonValue::CreateNumberValue(info.ActiveProcesses));
    diagnostics.Insert(L"job_total_processes", JsonValue::CreateNumberValue(info.TotalProcesses));
    DWORD exit_code{};
    check_bool(GetExitCodeProcess(process.get(), &exit_code));
    diagnostics.Insert(L"editor_exit_code", JsonValue::CreateNumberValue(exit_code));
    diagnostics.Insert(L"editor_exited", JsonValue::CreateBooleanValue(true));
    if (observation_error) std::rethrow_exception(observation_error);
}

int preflight(JsonObject const& request, JsonObject const& diagnostics, bool launch,
              fs::path const& journal, std::function<HKEY()> const& software, hstring& stage) {
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
    std::array<fs::path, 5> roots{editor, project, config, LR"(C:\vPinball\ColorizingDMD)",
        LR"(C:\DMD Colorization\ColorizingDMD)"};
    for (size_t i = 0; i < roots.size(); ++i) {
        for (size_t j = i + 1; j < roots.size(); ++j) {
            if (overlaps(roots[i], roots[j]) || overlaps(roots[j], roots[i]))
                throw std::runtime_error("editor, installation and output roots must be disjoint");
        }
    }
    auto exe = file_hash(editor / L"ColorizingDMD.exe");
    diagnostics.Insert(L"editor_sha256", JsonValue::CreateStringValue(exe));
    if (exe != editor_hash)
        return failure(L"editor-lock", L"Staged ColorizingDMD.exe SHA-256 mismatch", diagnostics);
    auto decoder = file_hash(editor / L"serum64.dll");
    diagnostics.Insert(L"decoder_sha256", JsonValue::CreateStringValue(decoder));
    if (decoder != decoder_hash)
        return failure(L"decoder-lock", L"Staged source-tree Serum 2.1.0 SHA-256 mismatch", diagnostics);

    stage = L"startup-assets";
    auto texture = editor / L"textures" / L"chiffres.raw";
    if (!fs::is_regular_file(texture)) return failure(stage, L"Missing textures/chiffres.raw", diagnostics);
    auto texture_digest = file_hash(texture);
    auto size = fs::file_size(texture);
    JsonObject entry, assets;
    entry.Insert(L"sha256", JsonValue::CreateStringValue(texture_digest));
    entry.Insert(L"size", JsonValue::CreateNumberValue(static_cast<double>(size)));
    assets.Insert(L"textures/chiffres.raw", entry);
    diagnostics.Insert(L"startup_assets", assets);
    if (size != 1815 || texture_digest != L"9eeea44b769035c9e49fe2fe90afa1463e047073384da0411c1c7e8e9a3f9a97")
        return failure(stage, L"Staged textures/chiffres.raw lock mismatch", diagnostics);
    if (!launch) return failure(L"startup-opt-in", L"Explicit startup preflight required", diagnostics);
    stage = L"stage-verification";
    verify_launch_inventory(editor);
    if (!fs::is_directory(config) || !fs::is_empty(config) || !fs::create_directory(project))
        throw std::runtime_error("startup preflight requires fresh project and configuration directories");
    // The pinned editor reads these six REG_SZ paths at startup. Its paths
    // use the ANSI Win32 API and require room for the trailing separator/NUL.
    auto dir = config.wstring() + L"\\", projects = project.wstring() + L"\\";
    for (auto const& path : {dir, projects}) {
        BOOL substituted = FALSE;
        bool utf8 = GetACP() == CP_UTF8;
        int bytes = WideCharToMultiByte(CP_ACP, utf8 ? WC_ERR_INVALID_CHARS : WC_NO_BEST_FIT_CHARS,
            path.c_str(), -1, nullptr, 0, nullptr, utf8 ? nullptr : &substituted);
        if (bytes <= 0 || bytes > MAX_PATH || substituted)
            throw std::runtime_error("editor startup paths must be representable by the pinned ANSI editor");
    }
    auto duration = static_cast<DWORD>((std::min)(request.GetNamedNumber(L"deadline_ms"), 5000.0));
    stage = L"registry-transaction";
    require_editor_stopped();
    with_journaled_transaction(software(), journal, {{L"DIR_SERUM", projects}, {L"DIR_DUMPS", dir},
        {L"DIR_IMAGES", dir}, {L"DIR_GIFS", dir}, {L"DIR_VP", dir}, {L"DIR_AIIMG", dir}}, diagnostics,
        [&](fs::path const& run) { bounded_startup(editor, duration, diagnostics, run); });
    return failure(L"startup-observation", L"Bounded startup ended; see the observed process and windows", diagnostics);
}

fs::path production_journal() {
#ifdef DMD_REPOSITORY_ROOT
    // Never derive recovery paths from request JSON, cwd or the staged editor.
    // A shared checkout can be used by distinct Windows users with different HKCU hives.
    handle token;
    if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, token.put()))
        throw std::system_error(GetLastError(), std::system_category(), "open current user token");
    DWORD length{};
    GetTokenInformation(token.get(), TokenUser, nullptr, 0, &length);
    if (GetLastError() != ERROR_INSUFFICIENT_BUFFER)
        throw std::system_error(GetLastError(), std::system_category(), "size current user identity");
    Bytes data(length);
    if (!GetTokenInformation(token.get(), TokenUser, data.data(), length, &length))
        throw std::system_error(GetLastError(), std::system_category(), "read current user identity");
    wchar_t* sid{};
    if (!ConvertSidToStringSidW(reinterpret_cast<TOKEN_USER*>(data.data())->User.Sid, &sid))
        throw std::system_error(GetLastError(), std::system_category(), "format current user identity");
    std::unique_ptr<wchar_t, decltype(&LocalFree)> user(sid, LocalFree);
    return fs::path(DMD_REPOSITORY_ROOT) / L"artifacts" / L"editor-isolation-journal" / user.get();
#else
    throw std::runtime_error("build the production bridge with its repository recovery root");
#endif
}

int main(int argc, char** argv) {
    try {
        init_apartment(apartment_type::multi_threaded);
        JsonObject diagnostics;
        diagnostics.Insert(L"editor_launched", JsonValue::CreateBooleanValue(false));
        hstring stage = L"registry-isolation";
        try {
            Key software;
            auto journal = production_journal();
            auto owner = L"Global\\DMDMaskOptimizer-EditorIsolation-" + journal.filename().wstring();
            auto open_software = [&] {
                HKEY key{};
                check_registry(RegOpenKeyExW(HKEY_CURRENT_USER, L"SOFTWARE", 0, KEY_READ | KEY_WRITE, &key),
                    "open current user SOFTWARE for editor recovery");
                software.reset(key);
                return software.get();
            };
            return with_editor_isolation(journal, owner.c_str(), open_software, diagnostics, [&] {
                stage = L"request";
                bool launch = argc == 2 && std::string_view(argv[1]) == "--startup-preflight";
                if (argc != 1 && !launch) throw std::runtime_error("unknown editor bridge option");
                return preflight(JsonObject::Parse(to_hstring(read_request())), diagnostics,
                    launch, journal, open_software, stage);
            });
        } catch (hresult_error const& error) {
            return failure(stage, error.message(), diagnostics);
        } catch (std::exception const& error) {
            return failure(stage, to_hstring(error.what()), diagnostics);
        }
    } catch (...) {
        std::cerr << "Cannot initialize or emit the Windows JSON preflight response\n";
        return 2;
    }
}
