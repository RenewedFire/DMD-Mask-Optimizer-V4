cmake_minimum_required(VERSION 3.20)
project(editor_bridge LANGUAGES CXX)

if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "The editor bridge requires Windows x64 MSVC and the Windows SDK")
endif()

add_executable(editor_bridge editor_bridge.cpp)
# All linked worktrees share one recovery marker for this repository.
find_package(Git REQUIRED)
execute_process(COMMAND "${GIT_EXECUTABLE}" rev-parse --path-format=absolute --git-common-dir
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" OUTPUT_VARIABLE common_git_dir
    OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
get_filename_component(repo_root "${common_git_dir}" DIRECTORY)
target_compile_definitions(editor_bridge PRIVATE DMD_REPOSITORY_ROOT=L"${repo_root}")
target_compile_features(editor_bridge PRIVATE cxx_std_20)
target_compile_options(editor_bridge PRIVATE /W4 /EHsc /utf-8)
target_link_libraries(editor_bridge PRIVATE windowsapp advapi32 user32)
set_target_properties(editor_bridge PROPERTIES RUNTIME_OUTPUT_DIRECTORY "$<1:${CMAKE_BINARY_DIR}>")

add_executable(serum_worker serum_worker.cpp)
target_compile_features(serum_worker PRIVATE cxx_std_17)
target_compile_options(serum_worker PRIVATE /EHsc /utf-8)
set_target_properties(serum_worker PROPERTIES RUNTIME_OUTPUT_DIRECTORY "$<1:${CMAKE_BINARY_DIR}>")
