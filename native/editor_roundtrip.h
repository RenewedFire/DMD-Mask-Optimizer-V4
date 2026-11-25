// Supported UI operations for the pinned three-reference fixture.
#include <uiautomation.h>
#include <shlobj.h>
#pragma comment(lib, "shell32.lib")
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "oleaut32.lib")
#pragma comment(lib, "uiautomationcore.lib")

namespace editor_import {

std::wstring caption(HWND window) {
    wchar_t value[512]{};
    GetWindowTextW(window, value, 512);
    return value;
}

void frame_click(HWND target, ULONGLONG deadline, int x, int y) {
    if (!target) throw std::runtime_error("GLFW child missing");
    POINT desired{x, y}, previous{};
    check_bool(GetCursorPos(&previous));
    check_bool(ClientToScreen(target, &desired));
    if (WindowFromPoint(desired) != target)
        throw std::runtime_error("GLFW pixel target is obscured; no pointer input issued");
    for (int key : {VK_SHIFT, VK_MENU, VK_CONTROL, VK_LBUTTON})
        if (GetAsyncKeyState(key) & 0x8000) throw std::runtime_error("pointer modifiers are already held");
    check_bool(SetCursorPos(desired.x, desired.y));
    struct Restore {
        POINT previous, desired;
        ~Restore() {
            POINT actual{};
            if (GetCursorPos(&actual) && actual.x == desired.x && actual.y == desired.y)
                SetCursorPos(previous.x, previous.y);
        }
    } restore{previous, desired};
    POINT actual{};
    check_bool(GetCursorPos(&actual));
    if (actual.x != desired.x || actual.y != desired.y)
        throw std::runtime_error("cursor did not reach requested target");
    send(deadline, target, WM_LBUTTONDOWN, MK_LBUTTON, MAKELPARAM(x, y));
    send(deadline, target, WM_LBUTTONUP, 0, MAKELPARAM(x, y));
}

void confirm_project_folder(DWORD pid, HWND chooser, fs::path const& project) {
    HWND tree = find(pid, chooser, L"SysTreeView32");
    com_ptr<IUIAutomation> automation;
    check_hresult(CoCreateInstance(CLSID_CUIAutomation, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(automation.put())));
    com_ptr<IUIAutomationElement> tree_element;
    check_hresult(automation->ElementFromHandle(tree, tree_element.put()));
    com_ptr<IUIAutomationSelectionPattern> selection;
    check_hresult(tree_element->GetCurrentPatternAs(UIA_SelectionPatternId, IID_PPV_ARGS(selection.put())));
    if (!selection) throw std::runtime_error("folder picker does not expose its selection");
    com_ptr<IUIAutomationElementArray> selected;
    check_hresult(selection->GetCurrentSelection(selected.put()));
    int count{};
    check_hresult(selected->get_Length(&count));
    if (count != 1) throw std::runtime_error("expected one selected first-save directory");
    com_ptr<IUIAutomationElement> item;
    check_hresult(selected->GetElement(0, item.put()));
    com_ptr<IUIAutomationTreeWalker> walker;
    check_hresult(automation->get_ControlViewWalker(walker.put()));
    PWSTR home_path{};
    check_hresult(SHGetKnownFolderPath(FOLDERID_Profile, 0, nullptr, &home_path));
    fs::path profile_dir(home_path); CoTaskMemFree(home_path);
    auto display_name = [](REFKNOWNFOLDERID id) {
        com_ptr<IShellItem> shell;
        check_hresult(SHGetKnownFolderItem(id, KF_FLAG_DEFAULT, nullptr, IID_PPV_ARGS(shell.put())));
        PWSTR name{}; check_hresult(shell->GetDisplayName(SIGDN_NORMALDISPLAY, &name));
        std::wstring label(name); CoTaskMemFree(name); return label;
    };
    auto profile_label = display_name(FOLDERID_UsersFiles);
    auto desktop_label = display_name(FOLDERID_Desktop);
    bool through_profile = false;
    auto path = project;
    for (; path != path.root_path(); path = path.parent_path()) {
        if (!item) throw std::runtime_error("incomplete folder picker path");
        BSTR name{};
        check_hresult(item->get_CurrentName(&name));
        std::wstring component(name ? name : L"");
        SysFreeString(name);
        if (path == profile_dir && component == profile_label) {
            com_ptr<IUIAutomationElement> desktop_item;
            check_hresult(walker->GetParentElement(item.get(), desktop_item.put()));
            if (!desktop_item) throw std::runtime_error("missing shell desktop root");
            BSTR label{}; check_hresult(desktop_item->get_CurrentName(&label));
            std::wstring root_label(label ? label : L""); SysFreeString(label);
            if (root_label != desktop_label) throw std::runtime_error("profile alias outside shell desktop");
            through_profile = true; break;
        }
        if (_wcsicmp(component.c_str(), path.filename().c_str()) != 0)
            throw std::runtime_error("folder picker selection does not confirm generated project path");
        com_ptr<IUIAutomationElement> parent;
        check_hresult(walker->GetParentElement(item.get(), parent.put()));
        item = std::move(parent);
    }
    if (through_profile) return;
    BSTR drive{};
    if (!item) throw std::runtime_error("folder picker drive missing");
    check_hresult(item->get_CurrentName(&drive));
    std::wstring drive_name(drive ? drive : L"");
    SysFreeString(drive);
    if (drive_name.find(L"(" + project.root_name().wstring() + L")") == std::wstring::npos)
        throw std::runtime_error("folder picker drive differs from generated project");
}

void apply_fixture_mask(DWORD pid, ULONGLONG deadline, JsonObject const& evidence) {
    auto main = find(pid, nullptr, L"ColorizingDMD");
    auto combo = find(pid, main, L"ComboBox", 1038);
    auto frame = find(pid, main, L"GLFW30", -1, L"Frame");
    auto strip = find(pid, main, L"GLFW30", -1, L"Frame Strip");
    if (!main || !combo || !frame || !strip || send(deadline, combo, CB_GETCOUNT) != 65)
        throw std::runtime_error("expected 65 comparison entries and both GLFW views");
    auto set_slot = [&] {
        if (send(deadline, combo, CB_GETCURSEL) != 0 || send(deadline, combo, CB_SETCURSEL, 1) != 1)
            throw std::runtime_error("expected initially unmasked reference");
        send(deadline, GetParent(combo), WM_COMMAND, MAKEWPARAM(1038, CBN_SELCHANGE), reinterpret_cast<LPARAM>(combo));
        if (send(deadline, combo, CB_GETCURSEL) != 1) throw std::runtime_error("first comparison slot was not selected");
    };
    set_slot();
    auto point = find(pid, main, L"Button", 1042);
    if (!point) throw std::runtime_error("comparison point tool unavailable");
    send(deadline, point, BM_CLICK);
    RECT desktop{};
    check_bool(SystemParametersInfoW(SPI_GETWORKAREA, 0, &desktop, 0));
    check_bool(SetWindowPos(main, nullptr, desktop.left, desktop.top, 0, 0, SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOSIZE));
    SetForegroundWindow(main);
    RECT rect{};
    check_bool(GetClientRect(frame, &rect));
    if (std::abs(rect.right - 4 * rect.bottom) > 4 || rect.bottom < 32)
        throw std::runtime_error("unexpected 128x32 display aspect ratio");
    frame_click(frame, deadline, (9 * rect.right) / 256, rect.bottom / 64);
    check_bool(GetClientRect(strip, &rect));
    int visible = (rect.right - 15) / (256 + 15);
    if (visible < 3) throw std::runtime_error("three reference thumbnails must be visible");
    int margin = (rect.right - (visible * (256 + 15) + 15)) / 2;
    JsonArray selected;
    evidence.Insert(L"selected_frames", selected);
    auto select_frame = [&](int ordinal) {
        frame_click(strip, deadline, margin + 15 + ordinal * (256 + 15) + 128, 52);
        auto expected = L"current " + std::to_wstring(ordinal) + L" / 1 selected / 3 total";
        wait(deadline, "selected frame", [&] { return caption(main).find(expected) != std::wstring::npos ? main : nullptr; });
        selected.Append(JsonValue::CreateStringValue(caption(main)));
    };
    select_frame(1);
    set_slot();
    select_frame(2);
    if (send(deadline, combo, CB_GETCURSEL) != 0) throw std::runtime_error("frame C mask selector is not None");
}

constexpr std::array project_names{L"twst_405.cROM", L"twst_405.cRP", L"twst_405.cRZ"};
using SaveTimes = std::array<fs::file_time_type, project_names.size()>;

SaveTimes wait_for_save(HWND main, fs::path const& project, ULONGLONG deadline, SaveTimes const* previous = nullptr) {
    SaveTimes times;
    wait(deadline, "three completed editor output files", [&]() -> HWND {
        // cRP is written last. Opening an old cROM before Save starts would
        // briefly deny the editor the write access it needs.
        auto last = project / project_names[1];
        if (!fs::is_regular_file(last) || (previous && fs::last_write_time(last) == (*previous)[1]))
            return nullptr;
        for (size_t i = 0; i < times.size(); ++i) {
            auto path = project / project_names[i];
            HANDLE reader = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
            if (reader == INVALID_HANDLE_VALUE) return nullptr;
            handle closed_to_writers(reader);
            if (!fs::file_size(path)) return nullptr;
            times[i] = fs::last_write_time(path);
            if (previous && times[i] == (*previous)[i]) return nullptr;
        }
        return main;
    });
    return times;
}

SaveTimes first_save(DWORD pid, fs::path const& project, ULONGLONG deadline) {
    auto main = find(pid, nullptr, L"ColorizingDMD");
    click(find(pid, main, L"Button", 1004));
    HWND chooser = wait(deadline, "first-save Serum directory chooser", [&]() -> HWND {
        auto dialog = find(pid, nullptr, L"#32770", -1, L"Browse For Folder");
        return dialog && find(pid, dialog, L"Static", -1, L"Please, select the Serum directory") ? dialog : nullptr;
    });
    confirm_project_folder(pid, chooser, project);
    click(GetDlgItem(chooser, IDOK));
    return wait_for_save(main, project, deadline);
}

void reopen_and_export(DWORD pid, fs::path const& project, ULONGLONG deadline,
                       SaveTimes const& previous, JsonObject const& evidence) {
    auto main = wait(deadline, "fresh editor window", [&] { return find(pid, nullptr, L"ColorizingDMD"); });
    click(find(pid, main, L"Button", 1003));
    submit_file(pid, L"Choose the project file", project / project_names[0], deadline);
    wait(deadline, "reopened three-reference project", [&]() -> HWND {
        auto title = caption(main);
        return title.find(L"ROM name: twst_405 ") != title.npos && title.find(L"/ 3 total") != title.npos ? main : nullptr;
    });
    evidence.Insert(L"reopened_title", JsonValue::CreateStringValue(caption(main)));
    click(find(pid, main, L"Button", 1004));
    wait_for_save(main, project, deadline, &previous);
    evidence.Insert(L"fresh_save_and_export", JsonValue::CreateBooleanValue(true));
}

void require_mask_fixture(JsonArray const& refs) {
    if (refs.Size() != 3) throw std::runtime_error("round trip requires three fixture references");
    for (unsigned i = 0; i < 3; ++i) {
        auto ref = refs.GetObjectAt(i);
        auto value = ref.GetNamedValue(L"ignore_bitmap");
        if (ref.GetNamedBoolean(L"shape") || (i == 2 && value.ValueType() != JsonValueType::Null))
            throw std::runtime_error("expected normal comparison and unmasked third reference");
        if (i == 2) continue;
        auto mask = value.GetArray();
        if (mask.Size() != 4096) throw std::runtime_error("expected 128x32 fixture mask");
        for (unsigned p = 0; p < mask.Size(); ++p)
            if (mask.GetNumberAt(p) != (p == 4 ? 1 : 0))
                throw std::runtime_error("supported fixture uses one shared ignored pixel at (4,0)");
    }
}

Bytes read_prefix(fs::path const& path, size_t size) {
    Bytes data(size);
    std::ifstream stream(path, std::ios::binary);
    if (!stream.read(reinterpret_cast<char*>(data.data()), size))
        throw std::runtime_error("truncated editor companion file");
    return data;
}

hstring digest(Bytes const& bytes) {
    auto buffer = CryptographicBuffer::CreateFromByteArray(bytes);
    return CryptographicBuffer::EncodeToHexString(HashAlgorithmProvider::OpenAlgorithm(L"SHA256").HashData(buffer));
}

void verify_decoder(fs::path const& editor, fs::path const& config, fs::path const& package) {
    // The DLL's public Serum_Load expects <altcolor>/<rom>/<rom>.cRZ.
    auto rom = config / L"twst_405";
    if (!fs::create_directory(rom)) throw std::runtime_error("decoder fixture directory already exists");
    auto copy = rom / package.filename();
    fs::copy_file(package, copy);
    if (file_hash(copy) != file_hash(package)) throw std::runtime_error("decoder fixture copy differs from export");
    auto library = LoadLibraryExW((editor / L"serum64.dll").c_str(), nullptr,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
    check_bool(library != nullptr);
    struct Unload { HMODULE module; ~Unload() { FreeLibrary(module); } } unload{library};
    using Load = void* (__cdecl*)(char const*, char const*, unsigned char);
    using Dispose = void (__cdecl*)();
    auto load = reinterpret_cast<Load>(GetProcAddress(library, "Serum_Load"));
    auto dispose = reinterpret_cast<Dispose>(GetProcAddress(library, "Serum_Dispose"));
    if (!load || !dispose || !load(config.string().c_str(), "twst_405", 1))
        throw std::runtime_error("pinned Serum decoder could not load exported cRZ");
    dispose();
}

JsonObject inspect_project(fs::path const& editor, fs::path const& project, fs::path const& config,
                           JsonArray const& refs, JsonObject const& diagnostics) {
    // Save_cRom writes the 64-byte ROM name, nine little-endian UINT32s,
    // one UINT16 and a BOOL. The historical length field is 80.
    constexpr size_t frames = 3, pixels = 4096, header_end = 106;
    constexpr size_t shape_offset = header_end + frames * 4;
    constexpr size_t slot_offset = shape_offset + frames, bitmap_offset = slot_offset + frames;
    auto crom = read_prefix(project / project_names[0], bitmap_offset + pixels);
    auto crp = read_prefix(project / project_names[1], 64 + frames * pixels);
    constexpr std::array<UINT32, 9> expected{80,128,32,256,64,3,4,1,0};
    if (std::memcmp(crom.data(), "twst_405", 9) || std::memcmp(crp.data(), "twst_405", 9) ||
        std::memcmp(crom.data()+64, expected.data(), sizeof(expected)) ||
        !std::all_of(crom.begin()+100, crom.begin()+header_end, [](BYTE v) { return v == 0; }))
        throw std::runtime_error("saved project header differs from three-reference fixture");
    JsonArray reopened, files;
    Bytes mask(crom.begin()+bitmap_offset, crom.end());
    for (unsigned i = 0; i < frames; ++i) {
        auto input = refs.GetObjectAt(i);
        auto source = crp.begin() + 64 + i * pixels;
        Bytes observed(source, source + pixels);
        auto source_hash = digest(observed);
        if (crom[shape_offset+i] || crom[slot_offset+i] != (i == 2 ? 255 : 0) ||
            source_hash != input.GetNamedString(L"source_sha256") ||
            (i < 2 && digest(mask) != input.GetNamedString(L"ignore_sha256")))
            throw std::runtime_error("reopened pixels, shape, shared mask or sentinel differ from input");
        JsonArray shades;
        for (auto shade : observed) shades.Append(JsonValue::CreateNumberValue(shade));
        JsonObject ref;
        ref.Insert(L"id", input.GetNamedValue(L"id"));
        ref.Insert(L"ordinal", JsonValue::CreateNumberValue(i));
        ref.Insert(L"native_pixels", shades);
        ref.Insert(L"source_sha256", JsonValue::CreateStringValue(source_hash));
        ref.Insert(L"ignore_sha256", i == 2 ? JsonValue::CreateNullValue() : JsonValue::CreateStringValue(digest(mask)));
        ref.Insert(L"shape", JsonValue::CreateBooleanValue(false));
        ref.Insert(L"slot", JsonValue::CreateNumberValue(crom[slot_offset+i]));
        reopened.Append(ref);
    }
    for (auto name : project_names) {
        auto path = project / name;
        JsonObject entry, header;
        header.Insert(L"prefix_hex", JsonValue::CreateStringValue(CryptographicBuffer::EncodeToHexString(
            CryptographicBuffer::CreateFromByteArray(read_prefix(path, 16)))));
        entry.Insert(L"path", JsonValue::CreateStringValue(name));
        entry.Insert(L"sha256", JsonValue::CreateStringValue(file_hash(path)));
        entry.Insert(L"size", JsonValue::CreateNumberValue(static_cast<double>(fs::file_size(path))));
        entry.Insert(L"header", header);
        files.Append(entry);
    }
    verify_decoder(editor, config, project / project_names[2]);
    diagnostics.Insert(L"decoder_loaded_export", JsonValue::CreateBooleanValue(true));
    JsonObject result;
    result.Insert(L"schema_version", JsonValue::CreateNumberValue(1));
    result.Insert(L"status", JsonValue::CreateStringValue(L"ok"));
    result.Insert(L"files", files);
    result.Insert(L"references", reopened);
    result.Insert(L"custom_mask_count", JsonValue::CreateNumberValue(1));
    result.Insert(L"unmasked_sentinel", JsonValue::CreateNumberValue(255));
    result.Insert(L"runtime_export", JsonValue::CreateStringValue(project_names[2]));
    result.Insert(L"sidecar_path", JsonValue::CreateStringValue(L"roundtrip.json"));
    result.Insert(L"observations", diagnostics);
    write_new_json(project / L"roundtrip.json", result);
    return result;
}

} // namespace editor_import
