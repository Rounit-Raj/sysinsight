#pragma once
#include <sqlite3.h>
#include <iostream>
#include <string>

class Database {
public:
    ~Database() { close(); }

    bool open(const std::string& path) {
        if (sqlite3_open(path.c_str(), &db_) != SQLITE_OK) {
            std::cerr << "Cannot open database: " << sqlite3_errmsg(db_) << "\n";
            return false;
        }
        exec("PRAGMA journal_mode=WAL;");
        exec("PRAGMA synchronous=NORMAL;");
        exec("CREATE TABLE IF NOT EXISTS samples ("
             "id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, "
             "cpu_percent REAL, ram_percent REAL, load_avg_1min REAL);");
        exec("CREATE TABLE IF NOT EXISTS processes ("
             "id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, pid INTEGER, "
             "name TEXT, cpu_percent REAL, mem_mb REAL);");
        exec("CREATE TABLE IF NOT EXISTS io ("
             "id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, "
             "disk_read_mb_s REAL, disk_write_mb_s REAL, "
             "net_rx_kb_s REAL, net_tx_kb_s REAL);");
        exec("CREATE TABLE IF NOT EXISTS alerts ("
             "id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, "
             "severity TEXT, message TEXT);");
        exec("CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(timestamp);");
        exec("CREATE INDEX IF NOT EXISTS idx_processes_ts ON processes(timestamp);");
        exec("CREATE INDEX IF NOT EXISTS idx_io_ts ON io(timestamp);");

        return prepare("INSERT INTO samples (timestamp, cpu_percent, ram_percent, load_avg_1min) "
                       "VALUES (?,?,?,?);", &sSample_)
            && prepare("INSERT INTO processes (timestamp, pid, name, cpu_percent, mem_mb) "
                       "VALUES (?,?,?,?,?);", &sProc_)
            && prepare("INSERT INTO io (timestamp, disk_read_mb_s, disk_write_mb_s, "
                       "net_rx_kb_s, net_tx_kb_s) VALUES (?,?,?,?,?);", &sIo_);
    }

    void close() {
        if (sSample_) { sqlite3_finalize(sSample_); sSample_ = nullptr; }
        if (sProc_)   { sqlite3_finalize(sProc_);   sProc_ = nullptr; }
        if (sIo_)     { sqlite3_finalize(sIo_);     sIo_ = nullptr; }
        if (db_)      { sqlite3_close(db_);         db_ = nullptr; }
    }

    void begin()  { exec("BEGIN;"); }
    void commit() { exec("COMMIT;"); }

    void insertSample(const std::string& ts, double cpu, double ram, double load) {
        sqlite3_bind_text(sSample_, 1, ts.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_double(sSample_, 2, cpu);
        sqlite3_bind_double(sSample_, 3, ram);
        sqlite3_bind_double(sSample_, 4, load);
        run(sSample_);
    }

    void insertProcess(const std::string& ts, int pid, const std::string& name,
                       double cpu, double memMb) {
        sqlite3_bind_text(sProc_, 1, ts.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_int(sProc_, 2, pid);
        sqlite3_bind_text(sProc_, 3, name.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_double(sProc_, 4, cpu);
        sqlite3_bind_double(sProc_, 5, memMb);
        run(sProc_);
    }

    void insertIo(const std::string& ts, double dr, double dw, double rx, double tx) {
        sqlite3_bind_text(sIo_, 1, ts.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_double(sIo_, 2, dr);
        sqlite3_bind_double(sIo_, 3, dw);
        sqlite3_bind_double(sIo_, 4, rx);
        sqlite3_bind_double(sIo_, 5, tx);
        run(sIo_);
    }

private:
    sqlite3* db_ = nullptr;
    sqlite3_stmt* sSample_ = nullptr;
    sqlite3_stmt* sProc_ = nullptr;
    sqlite3_stmt* sIo_ = nullptr;

    bool exec(const std::string& sql) {
        char* err = nullptr;
        if (sqlite3_exec(db_, sql.c_str(), nullptr, nullptr, &err) != SQLITE_OK) {
            std::cerr << "SQL error: " << (err ? err : "unknown") << "\n";
            sqlite3_free(err);
            return false;
        }
        return true;
    }

    bool prepare(const char* sql, sqlite3_stmt** st) {
        if (sqlite3_prepare_v2(db_, sql, -1, st, nullptr) != SQLITE_OK) {
            std::cerr << "Prepare failed: " << sqlite3_errmsg(db_) << "\n";
            return false;
        }
        return true;
    }

    void run(sqlite3_stmt* st) {
        if (sqlite3_step(st) != SQLITE_DONE)
            std::cerr << "DB insert failed: " << sqlite3_errmsg(db_) << "\n";
        sqlite3_reset(st);
    }
};
