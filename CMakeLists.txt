cmake_minimum_required(VERSION 3.16)
project(SYSINSIGHT LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(SQLite3 REQUIRED)
find_package(Threads REQUIRED)

add_executable(collector collector/main.cpp)
target_include_directories(collector PRIVATE collector)
target_compile_options(collector PRIVATE -Wall -Wextra -Wpedantic)
target_link_libraries(collector PRIVATE SQLite3::SQLite3 Threads::Threads)
