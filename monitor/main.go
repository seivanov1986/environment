package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os/exec"
	"runtime"
	"strings"
)

type Metrics struct {
	Hostname string         `json:"hostname"`
	OS       string         `json:"os"`
	CPU      float64        `json:"cpu_usage_percent"`
	RAM      map[string]any `json:"ram"`
	Disk     map[string]any `json:"disk"`
}

func getHostname() string {
	h, err := exec.Command("hostname").Output()
	if err != nil {
		return "unknown"
	}
	return strings.TrimSpace(string(h))
}

// Пример: получить загрузку CPU (за последний 1 сэмпл, *nix)
// Для реальных сценариев лучше брать с /proc/stat
func getCPU() float64 {
	out, err := exec.Command("top", "-bn1").Output()
	if err != nil {
		return -1
	}
	for _, line := range strings.Split(string(out), "\n") {
		if strings.Contains(line, "Cpu(s):") {
			parts := strings.Fields(line)
			// Легко сломать! Для продакшена — использовать gopsutil/cpu
			for i, p := range parts {
				if strings.HasPrefix(p, "id,") || (i > 0 && parts[i-1] == "Cpu(s):") {
					continue
				}
				if strings.HasSuffix(p, "us,") || strings.HasSuffix(p, "us") {
					usage := strings.TrimSuffix(p, "us,")
					usage = strings.TrimSuffix(usage, "us")
					var v float64
					fmt.Sscanf(usage, "%f", &v)
					return v
				}
			}
		}
	}
	return -1
}

func main() {
	hostname := getHostname()
	osName := runtime.GOOS

	// RAM info
	ramInfo := map[string]any{}
	out, _ := exec.Command("free", "-m").Output()
	lines := strings.Split(string(out), "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "Mem:") {
			fields := strings.Fields(line)
			ramInfo["total"] = fields[1] + "MB"
			ramInfo["used"] = fields[2] + "MB"
			ramInfo["free"] = fields[3] + "MB"
		}
	}

	// HDD
	diskInfo := map[string]any{}
	out, _ = exec.Command("df", "-h", "/").Output()
	lines = strings.Split(string(out), "\n")
	if len(lines) > 1 {
		fields := strings.Fields(lines[1])
		diskInfo["size"] = fields[1]
		diskInfo["used"] = fields[2]
		diskInfo["avail"] = fields[3]
		diskInfo["pcent"] = fields[4]
		diskInfo["mount"] = fields[5]
	}

	metrics := Metrics{
		Hostname: hostname,
		OS:       osName,
		CPU:      getCPU(),
		RAM:      ramInfo,
		Disk:     diskInfo,
	}

	payload, _ := json.Marshal(metrics)
	// Отправляем на сервер
	resp, err := http.Post("http://YOUR_BACKEND_IP:PORT/api/metrics", "application/json", bytes.NewBuffer(payload))
	if err != nil {
		fmt.Println("Ошибка HTTP:", err)
	} else {
		fmt.Println("Отправлено:", resp.Status)
	}
}
