package main

import (
	"database/sql"
	"sync"

	_ "modernc.org/sqlite"
)

type DB struct {
	conn *sql.DB
	mu   sync.Mutex
}

func NewDB(path string) (*DB, error) {
	conn, err := sql.Open("sqlite", path+"?_journal_mode=WAL")
	if err != nil {
		return nil, err
	}
	conn.SetMaxOpenConns(1)

	_, err = conn.Exec(`CREATE TABLE IF NOT EXISTS images (
		hash        TEXT PRIMARY KEY,
		path        TEXT NOT NULL,
		imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
	)`)
	if err != nil {
		conn.Close()
		return nil, err
	}

	return &DB{conn: conn}, nil
}

// TryInsert пытается вставить запись. Возвращает true если запись была новой.
func (db *DB) TryInsert(hash, path string) (bool, error) {
	db.mu.Lock()
	defer db.mu.Unlock()

	res, err := db.conn.Exec(
		"INSERT OR IGNORE INTO images (hash, path) VALUES (?, ?)", hash, path,
	)
	if err != nil {
		return false, err
	}
	rows, _ := res.RowsAffected()
	return rows > 0, nil
}

func (db *DB) Close() error {
	return db.conn.Close()
}
