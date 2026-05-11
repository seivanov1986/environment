package main

import (
	"bufio"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
)

// YOLOFilter runs a Python sidecar process that loads YOLOv8 once
// and classifies images via stdin/stdout.
// If the process crashes, it is restarted automatically (up to maxRestarts times).
type YOLOFilter struct {
	mu          sync.Mutex
	pythonBin   string
	scriptPath  string
	modelPath   string
	keepClasses string
	cmd         *exec.Cmd
	stdin       io.WriteCloser
	scanner     *bufio.Scanner
	restarts    int
	maxRestarts int
}

func NewYOLOFilter(pythonBin, scriptPath, modelPath, keepClasses string) (*YOLOFilter, error) {
	if pythonBin == "" {
		pythonBin = "python3"
	}
	f := &YOLOFilter{
		pythonBin:   pythonBin,
		scriptPath:  scriptPath,
		modelPath:   modelPath,
		keepClasses: keepClasses,
		maxRestarts: 5,
	}
	if err := f.start(); err != nil {
		return nil, err
	}
	return f, nil
}

func (f *YOLOFilter) start() error {
	cmd := exec.Command(f.pythonBin, f.scriptPath)

	env := cmd.Environ()
	if f.modelPath != "" {
		env = append(env, "YOLO_MODEL="+f.modelPath)
	}
	if f.keepClasses != "" {
		env = append(env, "YOLO_KEEP_CLASSES="+f.keepClasses)
	}
	cmd.Env = env
	cmd.Stderr = os.Stderr

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return fmt.Errorf("stdin pipe: %w", err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("stdout pipe: %w", err)
	}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start filter: %w", err)
	}

	f.cmd = cmd
	f.stdin = stdin
	f.scanner = bufio.NewScanner(stdout)
	return nil
}

// ShouldKeep returns true if the image contains a living being.
// All calls are serialized — YOLO is GPU-bound, parallelism doesn't help here.
// If the process has crashed, it is restarted and the image is retried once.
func (f *YOLOFilter) ShouldKeep(imagePath string) (bool, error) {
	f.mu.Lock()
	defer f.mu.Unlock()

	keep, err := f.query(imagePath)
	if err != nil {
		if f.restarts >= f.maxRestarts {
			return true, fmt.Errorf("filter crashed too many times, disabling: %w", err)
		}
		f.restarts++
		log.Printf("[WARN]  filter crashed on %s (restart %d/%d), skipping that file",
			filepath.Base(imagePath), f.restarts, f.maxRestarts)
		f.stdin.Close()
		f.cmd.Wait()
		if startErr := f.start(); startErr != nil {
			return true, fmt.Errorf("restart failed: %w", startErr)
		}
		// do NOT retry the crashing image — import it as-is
		return true, nil
	}
	return keep, nil
}

func (f *YOLOFilter) query(imagePath string) (bool, error) {
	if _, err := fmt.Fprintln(f.stdin, imagePath); err != nil {
		return true, fmt.Errorf("write to filter: %w", err)
	}
	if !f.scanner.Scan() {
		return true, fmt.Errorf("filter process closed unexpectedly")
	}
	result := strings.TrimSpace(f.scanner.Text())
	return result == "keep", nil
}

func (f *YOLOFilter) Close() {
	f.stdin.Close()
	f.cmd.Wait()
}
