// UI for the pinned editor's New-from-TXT command, included by editor_bridge.cpp.
namespace editor_import {

fs::path write_dump(fs::path const& project, JsonArray const& references) {
    if (!references.Size() || references.Size() > 65535)
        throw std::runtime_error("import requires 1 through 65535 references");
    std::string text;
    for (unsigned i = 0; i < references.Size(); ++i) {
        auto pixels = references.GetObjectAt(i).GetNamedArray(L"native_pixels");
        if (pixels.Size() != 128 * 32) throw std::runtime_error("expected 128x32 import pixels");
        char timestamp[11]{};
        std::snprintf(timestamp, sizeof(timestamp), "0x%08X", static_cast<unsigned>(i * 100));
        text += timestamp;
        text += "\r\n";
        for (unsigned j = 0; j < pixels.Size(); ++j) {
            auto shade = pixels.GetNumberAt(j);
            if (!(shade >= 0 && shade <= 3 && std::floor(shade) == shade))
                throw std::runtime_error("expected integer import shades 0 through 3");
            text += static_cast<char>('0' + static_cast<int>(shade));
            if (j % 128 == 127) text += "\r\n";
        }
        text += "\r\n";
    }
    auto path = project / L"twst_405.txt";
    if (path.string().size() >= MAX_PATH) throw std::runtime_error("TXT path exceeds editor filename buffer");
    std::ofstream output(path, std::ios::binary | std::ios::out);
    output.write(text.data(), text.size());
    output.close();
    if (!output) throw std::runtime_error("could not write generated TXT");
    return path;
}

struct WindowMatch {
    DWORD pid;
    std::wstring_view klass, caption;
    int id;
    int count{};
    HWND handle{};
};

BOOL CALLBACK match(HWND window, LPARAM context) {
    auto& search = *reinterpret_cast<WindowMatch*>(context);
    DWORD pid{};
    GetWindowThreadProcessId(window, &pid);
    if (pid != search.pid || !IsWindowVisible(window)) return TRUE;
    wchar_t klass[80]{}, caption[256]{};
    GetClassNameW(window, klass, 80);
    if (search.klass != klass || (search.id != -1 && GetDlgCtrlID(window) != search.id)) return TRUE;
    if (!search.caption.empty()) {
        GetWindowTextW(window, caption, 256);
        if (search.caption != caption) return TRUE;
    }
    search.handle = window;
    ++search.count;
    return TRUE;
}

HWND find(DWORD pid, HWND parent, std::wstring_view klass, int id = -1, std::wstring_view caption = {}) {
    WindowMatch search{pid, klass, caption, id};
    if (parent) EnumChildWindows(parent, match, reinterpret_cast<LPARAM>(&search));
    else EnumWindows(match, reinterpret_cast<LPARAM>(&search));
    return search.count == 1 ? search.handle : nullptr;
}

HWND wait(ULONGLONG deadline, char const* description, auto find_expected) {
    while (GetTickCount64() < deadline) {
        if (auto window = find_expected()) return window;
        Sleep(35);
    }
    throw std::runtime_error(std::string("timed out waiting for ") + description);
}

void click(HWND button) {
    if (!button || !IsWindowEnabled(button)) throw std::runtime_error("missing enabled editor button");
    check_bool(PostMessageW(button, BM_CLICK, 0, 0));
}

DWORD_PTR send(ULONGLONG deadline, HWND control, UINT message, WPARAM word = 0, LPARAM parameter = 0) {
    auto now = GetTickCount64();
    DWORD_PTR result{};
    if (!control || now >= deadline || !SendMessageTimeoutW(control, message, word, parameter,
        SMTO_ABORTIFHUNG | SMTO_BLOCK, static_cast<UINT>((std::min)(deadline - now, 1200ULL)), &result))
        throw std::runtime_error("editor control missing or unresponsive");
    return result;
}

void submit_file(DWORD pid, wchar_t const* title, fs::path const& path, ULONGLONG deadline) {
    auto dialog = wait(deadline, "editor file chooser", [&] {
        return find(pid, nullptr, L"#32770", -1, title);
    });
    auto filename = find(pid, dialog, L"Edit", 0x480);  // Win32 common-dialog edt1 / cmb13
    if (!filename) {
        auto combo = find(pid, dialog, L"ComboBox", 0x47c);
        if (combo) filename = find(pid, combo, L"Edit");
    }
    if (!send(deadline, filename, WM_SETTEXT, 0, reinterpret_cast<LPARAM>(path.c_str())))
        throw std::runtime_error("editor rejected the generated filename");
    click(GetDlgItem(dialog, IDOK));
}

void operate(DWORD pid, fs::path const& dump, unsigned expected_references, ULONGLONG deadline, JsonObject const& evidence) {
    auto main = wait(deadline, "main editor", [&] { return find(pid, nullptr, L"ColorizingDMD"); });
    click(wait(deadline, "New toolbar button", [&] { return find(pid, main, L"Button", 1001); }));
    submit_file(pid, L"Choose the initial TXT file", dump, deadline);
    auto filters = wait(deadline, "Filter options", [&] { return find(pid, nullptr, L"#32770", -1, L"Filter options"); });
    for (auto id : {1118, 1120, 1121})
        if (send(deadline, GetDlgItem(filters, id), BM_GETCHECK) != BST_UNCHECKED)
            throw std::runtime_error("editor import filters would discard generated frames");
    click(GetDlgItem(filters, IDOK));
    wchar_t caption[512]{};
    wait(deadline, "twst_405 imported frames", [&]() -> HWND {
        GetWindowTextW(main, caption, 512);
        std::wstring_view title(caption);
        auto expected = L"current 0 / 1 selected / " + std::to_wstring(expected_references) + L" total";
        return title.find(L"ROM name: twst_405 ") != title.npos && title.find(expected) != title.npos ? main : nullptr;
    });
    evidence.Insert(L"imported_title", JsonValue::CreateStringValue(caption));
}

} // namespace editor_import
