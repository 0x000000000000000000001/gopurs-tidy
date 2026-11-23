// measure.py supplies imports and calls from the generated package layout.
package main

import (
	"encoding/json"
	"os"
	"runtime"
	"unicode/utf8"
	// GOPURS_IMPORTS
)

func main() {
	mode, input := os.Args[1], os.Args[2]
	data, err := os.ReadFile(input)
	if err != nil { panic(err) }
	source := string(data)
	if mode == "verify" {
		formatted := FORMAT_CALL(source)
		if !utf8.ValidString(formatted) { panic("Verification requires well-formed Unicode") }
		if err := os.WriteFile(os.Args[3], []byte(formatted), 0600); err != nil { panic(err) }
		json.NewEncoder(os.Stdout).Encode(map[string]any{"bytes": len(formatted), "checksum": CONSUME_CALL(formatted)})
		return
	}
	if mode != "allocations" { panic("Expected verify or allocations mode") }
	var before, after runtime.MemStats
	runtime.ReadMemStats(&before)
	checksum := 0.0
	for i := 0; i < 10; i++ { checksum += CONSUME_CALL(FORMAT_CALL(source)) }
	runtime.ReadMemStats(&after)
	json.NewEncoder(os.Stdout).Encode(map[string]any{
		"checksum": checksum,
		"total_alloc_bytes": after.TotalAlloc-before.TotalAlloc,
		"mallocs": after.Mallocs-before.Mallocs,
		"num_gc": after.NumGC-before.NumGC,
	})
}
