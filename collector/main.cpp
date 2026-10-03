#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <chrono>
#include <thread>
#include <ctime>
#include <filesystem>
#include <vector>
#include <unordered_map>
#include <algorithm>
#include <unistd.h>
#include <tuple>
#include <cctype>

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

struct ProcSample {
    long long ticks; //utime + stime
    long long rssKb; //resident memory
    std::string name;
};

struct ProcRow {
    double pct;
    int pid;
    ProcSample proc;
};

//Reads CPU ticks and memory for every running process from /proc/[pid]/stat
std::unordered_map<int, ProcSample> readAllProcesses() {
     std::unordered_map<int, ProcSample> result;
     long pageKb = sysconf(_SC_PAGESIZE) / 1024;

     for (const auto& entry : std::filesystem::directory_iterator("/proc")) {
         std::string dirName = entry.path().filename().string();
         if (dirName.empty() || !std::all_of(dirName.begin(), dirName.end(), ::isdigit)) continue;

         std::ifstream file(entry.path() / "stat");
         std::string line;
         if (!std::getline(file, line)) continue;

         // process name is in (...) and may contain spaces, so find the last ')'
         size_t open = line.find('(');
         size_t close = line.rfind(')');
         if (open == std::string::npos || close == std::string::npos) continue;

         std::string name = line.substr(open + 1, close - open -1);
         std::replace(name.begin(), name.end(), ',', '_');

         std::istringstream iss(line.substr(close + 2));
         std::vector<std::string> f;
         std::string tok;
         while (iss >> tok) f.push_back(tok);
         if (f.size() < 22) continue;

         try {
             // After the name: f[11]=utime, f[12]=stime, f[21]=rss (in pages)
             long long ticks = std::stoll(f[11]) + std::stoll(f[12]);
             long long rssKb = std::stoll(f[21]) * pageKb;
             result[std::stoi(dirName)] = {ticks, rssKb, name};
         
         } catch (...) {
             continue; // process vanished or trash(bad data)
         }
    }
    return result;
}

struct IoSample {
    long long diskReadSectors = 0, diskWriteSectors =0;
    long long netRxBytes = 0, netTxBytes = 0;
};

//Reads cumulative disk and network counters
IoSample readIo() {
    IoSample s;
     
    std::ifstream disk("/proc/diskstats");
    std::string line;
    while (std::getline(disk, line)) {
        std::istringstream iss(line);
        int major, minor;
        std::string name;
        long long rc, rm, rs, rt, wc, wm, ws;
        if (!(iss >> major >> minor >> name >> rc >> rm >> rs >> rt >> wc >> wm >> ws)) continue;

        bool whole = false;
        if (name.rfind("nvme", 0) == 0) whole = (name.find('p' , 4) == std::string::npos);
        else if (name.rfind("sd", 0) == 0 || name.rfind("vd", 0) == 0) whole = !std::isdigit(name.back());
        if (!whole) continue;
        
        s.diskReadSectors += rs;
        s.diskWriteSectors += ws;
}

std::ifstream net("/proc/net/dev");
std::getline(net, line);
    std::getline(net, line);
    while (std::getline(net, line)) {
        size_t colon = line.find(':');
        if (colon == std::string::npos) continue;
        std::string iface = line.substr(0, colon);
        iface.erase(0, iface.find_first_not_of(' '));
        if (iface == "lo") continue;

        std::istringstream iss(line.substr(colon + 1));
        long long rx, skip, tx;
        iss >> rx;
        for (int i = 0; i < 7; i++) iss >> skip;
        iss >> tx;
        s.netRxBytes += rx;
        s.netTxBytes += tx;
    }
    return s;
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

    const std::string procPath = "data/processes.csv";
    bool procIsNew = std::ifstream(procPath).peek() == std::ifstream::traits_type::eof();
    std::ofstream procCsv(procPath, std::ios::app);
    if (procIsNew) {
        procCsv << "timestamp,pid,name,cpu_percent,mem_mb\n";
    }

    const std::string ioPath = "data/io.csv";
    bool ioIsNew = std::ifstream(ioPath).peek() == std::ifstream::traits_type::eof();
    std::ofstream ioCsv(ioPath, std::ios::app);
    if (ioIsNew) {
        ioCsv << "timestamp,disk_read_mb_s,disk_write_mb_s,net_rx_kb_s,net_tx_kb_s\n";
    }

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
    auto prevProcs = readAllProcesses();
    IoSample prevIo = readIo();
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
       
        auto currProcs = readAllProcesses();
        long long totalDiff = currCpu.totalTime() - prevCpu.totalTime();
        std::vector<ProcRow> rows;
        for (const auto& kv : currProcs) {
            auto it = prevProcs.find(kv.first);
            if (it == prevProcs.end() || totalDiff <= 0) continue;
            double pct = (double)(kv.second.ticks - it->second.ticks) / (double)totalDiff * 100.0;
            rows.push_back({pct, kv.first, kv.second});
        }
        std::sort(rows.begin(), rows.end(),
                  [](const ProcRow& a, const ProcRow& b) { return a.pct > b.pct; });
        for (size_t i = 0; i < rows.size() && i < 5; i++) {
            procCsv << timestamp << "," << rows[i].pid << "," << rows[i].proc.name << ","
                    << rows[i].pct << "," << rows[i].proc.rssKb / 1024.0 << "\n";
        }
        procCsv.flush();
        prevProcs = std::move(currProcs);
        IoSample currIo = readIo();
        double diskRead  = (currIo.diskReadSectors  - prevIo.diskReadSectors)  * 512.0 / 1048576.0;
        double diskWrite = (currIo.diskWriteSectors - prevIo.diskWriteSectors) * 512.0 / 1048576.0;
        double netRx = (currIo.netRxBytes - prevIo.netRxBytes) / 1024.0;
        double netTx = (currIo.netTxBytes - prevIo.netTxBytes) / 1024.0;
        ioCsv << timestamp << "," << diskRead << "," << diskWrite << ","
              << netRx << "," << netTx << "\n";
        ioCsv.flush();
        prevIo = currIo;
        prevCpu = currCpu;
        std::this_thread::sleep_for(std::chrono::seconds(1));
    } 
    
    return 0;
}
