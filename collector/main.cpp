#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <chrono>
#include <thread>
#include <ctime>

// Holds one snapshot of /proc/stst's CPU line

struct CpuTimes {
    long long user, nice, system, idle, iowait, irq, softirq, steal;

    long long idleTime() const {return idle +iowait; }
    long long totalTime() const {
        return user + nice + system + idle + iowait + irq + softirq + steal;
    }
};

//Reads the first line of /proc/stat (aggregate CPU stats including all cores)

CpuTimes readCpuTimes() {
    std::ifstream file("/proc/stat");
    std::string line;
    std::getline(file, line); //first line will start with "cpu"

    std::istringstream iss(line);
    std::string cpuLabel;
    CpuTimes t{};
    iss >> cpuLabel >> t.user >> t.nice >> t.system >> t.idle
        >> t.iowait >> t.irq >> t.softirq >> t.steal;
    return t;
}

//Computes CPU usage % between two samples taken ~1 second apart
double computeCpuUsagePercent(const CpuTimes& prev, const CpuTimes& curr) {
    long long totalDiff = curr.totalTime() - prev.totalTime();
    long long idleDiff = curr.idleTime() - prev.idleTime();
    if (totalDiff <= 0) return 0.0;
    return (1.0 - (double)idleDiff / (double)totalDiff) * 100.0;
}

//Reads proc and returns RAM usage as a percentage
double readMemUsagePercent() {
    std::ifstream file("/proc/meminfo");
    std::string key;
    long long value;
    std::string unit;

    long long memTotal = 0, memAvailable = 0;

    std::string line;
    while (std::getline(file, line)) {
        std::istringstream iss(line);
        iss >> key >> value >> unit;
        if (key == "MemTotal:") memTotal = value;
        else if (key == "MemAvailable:") memAvailable = value;
        if (memTotal && memAvailable) break;
    }

    if (memTotal == 0) return 0.0;
    long long used = memTotal - memAvailable;
    return (double)used / (double)memTotal * 100.0;
}

//Reads /proc/loadavg and returns the 1 min load average
double readLoadAverage1Min() {
    std::ifstream file("/proc/loadavg");
    double load1;
    file >> load1;
    return load1;
}

//Returns current timestamp as a string
std::string currentTimestamp() {
    std::time_t now = std::time(nullptr);
    char buf[32];
    std::strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", std::localtime(&now));
    return std::string(buf);
}

int main() {
    const std::string csvPath = "data/readings.csv";
    
    //Open in append mode if you don't have some big cojnomes
    bool fileIsNew = std::ifstream(csvPath).peek() == std::ifstream::traits_type::eof();
    std::ofstream csv(csvPath, std::ios::app);

    if (!csv.is_open()) {
        std::cerr << "Failed to open " << csvPath << " for writing.\n";
        return 1;
    }
    
    if (fileIsNew) {
        csv << "timestamp,cpu_percent,ram_percent,load_avg_1min\n";
    }

    std::cout << "SysInsight collector started. Logging to " << csvPath
              << " every 1 second. Press Ctrl+C to stop.\n";
 
    CpuTimes prevCpu = readCpuTimes();
    std::this_thread::sleep_for(std::chrono::seconds(1));

    while (true) {
        CpuTimes currCpu = readCpuTimes();
        double cpuPercent = computeCpuUsagePercent(prevCpu, currCpu);
        double ramPercent = readMemUsagePercent();
        double loadAvg = readLoadAverage1Min();
        std::string timestamp = currentTimestamp();

        csv << timestamp << "," << cpuPercent << "," << ramPercent << "," << loadAvg << "\n";
        csv.flush(); //ensure that it's fast as fuck boi

        std::cout << timestamp << " | CPU: " << cpuPercent << "% | RAM: "
                  << ramPercent << "% | Load: " << loadAvg << "\n";

        prevCpu = currCpu;
        std::this_thread::sleep_for(std::chrono::seconds(1));
    } 
    
    return 0;
}
