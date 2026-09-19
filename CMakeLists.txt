cmake_minimum_required(VERSION 3.10)
project(sysinsight_collector)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(collector collector/main.cpp)
